"""CI Summary must fail unless every gated job ran or was meant to skip (#385).

The summary job used to fail only on `failure`, so cancelled jobs and jobs
skipped behind a failed dependency (detect-changes included) passed. Each
`check` line now pairs a job result with an *_EXPECTED value that must mirror
that job's own `if:`. The structural tests walk every `check` line against the
job graph, and the behavioural tests execute the summary script.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(".github/workflows/reusable-ci.yml")
MIN_CHECKS = 16
# Jobs the summary deliberately does not gate on (warn-only or manual).
UNGATED = {"sast-semgrep", "sast-codeql", "scorecard", "performance", "self-heal"}
CHECK_RE = re.compile(r'^\s*check "([^"]+)" "\$(\w+)" "(\$\w+|true)"$', re.MULTILINE)
RESULT_RE = re.compile(r"^\$\{\{ needs\.([\w-]+)\.result \}\}$")


def _norm(expr: str) -> str:
    expr = expr.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2]
    return " ".join(expr.split())


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def _summary_step() -> dict:
    steps = _jobs()["summary"]["steps"]
    return next(s for s in steps if s["name"] == "Generate Run Summary")


def _checks() -> list[tuple[str, str, str]]:
    return CHECK_RE.findall(_summary_step()["run"])


def _needs(job: dict) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _effective_condition(name: str, jobs: dict) -> str:
    """The condition under which a job runs, given its upstream jobs succeed."""
    job = jobs[name]
    own = job.get("if")
    deps = [d for d in _needs(job) if d != "detect-changes"]
    if own is not None and deps:
        pytest.fail(
            f"{name}: an own `if:` plus non-detect-changes needs is not modelled"
        )
    if own is not None:
        return _norm(str(own))
    if deps:
        assert len(deps) == 1, f"{name}: multiple needs are not modelled"
        return _effective_condition(deps[0], jobs)
    return "true"


def _checked_job(result_var: str) -> str:
    match = RESULT_RE.match(_summary_step()["env"][result_var])
    assert match, f"{result_var} is not a needs.<job>.result reference"
    return match.group(1)


def test_check_walk_is_not_vacuous():
    assert len(_checks()) >= MIN_CHECKS


def test_every_gated_job_is_checked():
    checked = {_checked_job(result_var) for _, result_var, _ in _checks()}
    gated = set(_needs(_jobs()["summary"])) - UNGATED
    assert checked == gated


def test_expected_mirrors_job_condition():
    jobs = _jobs()
    env = _summary_step()["env"]
    mismatches = []
    for label, result_var, expected in _checks():
        job = _checked_job(result_var)
        actual = "true" if expected == "true" else _norm(str(env[expected[1:]]))
        want = _effective_condition(job, jobs)
        if actual != want:
            mismatches.append(f"{label} ({job}): {actual!r} != {want!r}")
    assert not mismatches


def _run(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    step = _summary_step()
    env = {k: "success" for k in step["env"] if k.endswith("_RESULT")}
    env.update({k: "true" for k in step["env"] if k.endswith("_EXPECTED")})
    env["FAIL_ON_TYPECHECK"] = "false"
    env.update(overrides)
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    env["PATH"] = os.environ["PATH"]
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_success_passes(tmp_path):
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "All checks passed" in (tmp_path / "summary.md").read_text()


def test_cancelled_job_fails(tmp_path):
    proc = _run(tmp_path, TEST_RESULT="cancelled")
    assert proc.returncode == 1
    assert "Test finished with result 'cancelled'" in proc.stdout


def test_intentional_skip_passes(tmp_path):
    proc = _run(
        tmp_path,
        PYTHON_QUALITY_RESULT="skipped",
        PYTHON_DEP_AUDIT_RESULT="skipped",
        PYTHON_EXPECTED="false",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_skip_behind_failed_dependency_fails(tmp_path):
    proc = _run(tmp_path, BUILD_RESULT="skipped")
    assert proc.returncode == 1
    assert "Build was skipped but was expected to run" in proc.stdout


def test_detect_changes_failure_fails(tmp_path):
    # detect-changes failing leaves its outputs empty, so every gate renders
    # false and every dependent job is skipped. That must not read as green.
    overrides = {"DETECT_CHANGES_RESULT": "failure"}
    step = _summary_step()
    for key in step["env"]:
        if key.endswith("_EXPECTED"):
            overrides[key] = "false"
        elif key.endswith("_RESULT") and key != "DETECT_CHANGES_RESULT":
            overrides[key] = "skipped"
    proc = _run(tmp_path, **overrides)
    assert proc.returncode == 1
    assert "Detect Changes finished with result 'failure'" in proc.stdout


def test_ungated_job_does_not_fail_summary(tmp_path):
    proc = _run(tmp_path, SAST_SEMGREP_RESULT="cancelled")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_fail_on_typecheck_warns_deprecated(tmp_path):
    proc = _run(tmp_path, FAIL_ON_TYPECHECK="true")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "fail-on-typecheck is deprecated" in proc.stdout
