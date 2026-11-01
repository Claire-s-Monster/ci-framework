"""Gemini AI jobs must degrade gracefully on quota or billing refusals.

When the Gemini API refuses a request with 402, 429 or RESOURCE_EXHAUSTED the
PR author cannot fix it, so the job must warn and exit 0. Every other error
must still fail the job.

The guard walks every `generate_content` call in reusable-gemini-ai.yml
(extracted from the heredoc script bodies) rather than relying on a
hand-maintained list, and a floor on the number of sites found keeps it from
passing vacuously.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(".github/workflows/reusable-gemini-ai.yml")
MIN_CALL_SITES = 4
HEREDOC_RE = re.compile(r"<< 'PYTHON'\n(.*?)\n\s*PYTHON\n", re.DOTALL)

STUB_ERRORS = """
class APIError(Exception):
    def __init__(self, code, status):
        super().__init__(f"{code} {status}")
        self.code = code
        self.status = status


class ClientError(APIError):
    pass
"""

STUB_GENAI = """
import os
from google.genai import errors


class _Models:
    def generate_content(self, **kwargs):
        raise errors.ClientError(
            int(os.environ["STUB_CODE"]), os.environ["STUB_STATUS"]
        )


class Client:
    def __init__(self, **kwargs):
        self.models = _Models()
"""


def _scripts() -> list[tuple[str, str, str]]:
    """Return (job, step name, script body) for every PYTHON heredoc."""
    doc = yaml.safe_load(WORKFLOW.read_text())
    found = []
    for job_name, job in doc["jobs"].items():
        for step in job["steps"]:
            match = HEREDOC_RE.search(step.get("run", "") + "\n")
            if match:
                found.append((job_name, step["name"], match.group(1)))
    return found


def _is_generate_content(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate_content"
    )


def _call_sites(tree: ast.AST) -> list[ast.Call]:
    return [
        n for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_generate_content(n)
    ]


def _guarded(tree: ast.AST, call: ast.Call) -> bool:
    """True if the call sits in a try body whose APIError handler delegates."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        in_body = any(call in ast.walk(stmt) for stmt in node.body)
        if not in_body:
            continue
        for handler in node.handlers:
            catches = "errors.APIError" in ast.unparse(handler.type or ast.Pass())
            delegates = any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "skip_if_quota"
                for n in ast.walk(handler)
            )
            if catches and delegates:
                return True
    return False


def test_call_site_walk_is_not_vacuous():
    total = sum(len(_call_sites(ast.parse(body))) for _, _, body in _scripts())
    assert total >= MIN_CALL_SITES


def test_every_generate_content_call_is_guarded():
    for job, step, body in _scripts():
        tree = ast.parse(body)
        for call in _call_sites(tree):
            assert _guarded(tree, call), f"{job}/{step}: unguarded generate_content"


def test_helper_covers_402_429_and_resource_exhausted():
    for job, step, body in _scripts():
        assert "(402, 429)" in body, f"{job}/{step}"
        assert "RESOURCE_EXHAUSTED" in body, f"{job}/{step}"


def test_no_expression_interpolation_in_script_bodies():
    for job, step, body in _scripts():
        assert "${{" not in body, f"{job}/{step}"


def test_downstream_steps_skip_when_gemini_unavailable():
    doc = yaml.safe_load(WORKFLOW.read_text())
    checked = 0
    for job_name, job in doc["jobs"].items():
        steps = job["steps"]
        for i, step in enumerate(steps):
            if not HEREDOC_RE.search(step.get("run", "") + "\n"):
                continue
            assert step.get("id"), f"{job_name}/{step['name']} needs an id"
            guard = f"steps.{step['id']}.outputs.skipped != 'true'"
            consumers = [
                s for s in steps[i + 1 :] if "if" in s and guard in str(s["if"])
            ]
            has_consumer = any(
                s.get("uses", "").startswith("actions/github-script")
                or "GITHUB_STEP_SUMMARY" in s.get("run", "")
                for s in steps[i + 1 :]
            )
            if has_consumer:
                assert consumers, f"{job_name}: consumer step lacks skip guard"
                checked += 1
    assert checked >= MIN_CALL_SITES


def _run_script(tmp_path: Path, body: str, code: int, status: str):
    stub = tmp_path / "stub"
    (stub / "google" / "genai").mkdir(parents=True)
    (stub / "google" / "__init__.py").write_text("")
    (stub / "google" / "genai" / "__init__.py").write_text(STUB_GENAI)
    (stub / "google" / "genai" / "errors.py").write_text(STUB_ERRORS)

    work = tmp_path / "work"
    work.mkdir()
    for name in ("pr_diff_truncated.txt", "changed.txt", "files.txt"):
        (work / name).write_text("x")
    script = work / "script.py"
    script.write_text(body.replace("'/tmp/", f"'{work}/"))

    summary = tmp_path / "summary.md"
    output = tmp_path / "output.txt"
    env = {
        **os.environ,
        "PYTHONPATH": str(stub),
        "GEMINI_API_KEY": "k",
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_OUTPUT": str(output),
        "STUB_CODE": str(code),
        "STUB_STATUS": status,
    }
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc, summary, output, work


@pytest.mark.parametrize(
    ("code", "status"),
    [(402, "RESOURCE_EXHAUSTED"), (429, "TOO_MANY"), (400, "RESOURCE_EXHAUSTED")],
)
@pytest.mark.parametrize("script", _scripts(), ids=lambda s: f"{s[0]}")
def test_quota_errors_exit_zero_with_warning(tmp_path, script, code, status):
    proc, summary, output, work = _run_script(tmp_path, script[2], code, status)
    assert proc.returncode == 0, proc.stderr
    assert "::warning title=Gemini unavailable::" in proc.stdout
    assert f"{code} {status}" in proc.stdout
    assert "skipped" in summary.read_text()
    assert "skipped=true" in output.read_text()
    assert not list(work.glob("*.md")) and not (work / "triage.json").exists()


@pytest.mark.parametrize("code", [400, 401, 403, 404, 500, 503])
@pytest.mark.parametrize("script", _scripts(), ids=lambda s: f"{s[0]}")
def test_other_api_errors_still_fail(tmp_path, script, code):
    proc, _, output, _ = _run_script(tmp_path, script[2], code, "UNAUTHENTICATED")
    assert proc.returncode != 0
    assert "::warning" not in proc.stdout
    assert not output.exists()
