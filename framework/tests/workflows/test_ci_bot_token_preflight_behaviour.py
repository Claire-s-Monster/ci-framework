"""Behavioural tests for the `Verify CI_BOT_TOKEN is valid` preflight (#482).

The real `run:` script is pulled out of each reusable workflow and executed with
`bash --noprofile --norc -eo pipefail -c` (GitHub's default shell invocation)
against a fake `curl` that answers per URL. The static guard lives in
test_ci_bot_token_preflight.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
PREFLIGHT_STEP_NAME = "Verify CI_BOT_TOKEN is valid"
PREFLIGHT_JOBS = [
    ("reusable-ci.yml", "sast-semgrep"),
    ("reusable-ci.yml", "sast-codeql"),
    ("reusable-security.yml", "sast-semgrep"),
    ("reusable-security.yml", "sast-codeql"),
    ("reusable-ci.yml", "scorecard-token-preflight"),
    ("reusable-security.yml", "scorecard-token-preflight"),
]

BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(BASH is None, reason="bash is not available")

# The fake curl only answers a request that carries the bearer header for
# CI_BOT_TOKEN; otherwise it reports an unauthenticated call on stderr (which
# run_preflight turns into a failure) so a preflight that stops sending the
# token cannot pass on the canned status alone.
FAKE_CURL = """#!/bin/sh
auth=0
prev=""
for arg; do
  if [ "$prev" = "-H" ] && [ "$arg" = "Authorization: Bearer $CI_BOT_TOKEN" ]; then
    auth=1
  fi
  prev="$arg"
  last="$arg"
done
if [ "$auth" != 1 ]; then
  echo "unauthenticated curl call: $last" >&2
  printf '%s' "000"
  exit 0
fi
case "$last" in
  */rate_limit) printf '%s' "{rate}" ;;
  */repos/o/r/code-scanning/analyses?per_page=1) printf '%s' "{cs}" ;;
  *) printf '%s' "999" ;;
esac
"""


def preflight_script(file_name: str, job_id: str) -> str:
    doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text(encoding="utf-8"))
    step = next(
        s for s in doc["jobs"][job_id]["steps"] if s.get("name") == PREFLIGHT_STEP_NAME
    )
    run = step["run"]
    assert "${{" not in run
    return run


def run_preflight(
    script: str, tmp_path: Path, token: str, rate: str, cs: str
) -> tuple[int, str, list[str]]:
    """Run `script` with a fake curl; return (exit code, stdout, GITHUB_OUTPUT lines)."""
    assert BASH is not None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL.format(rate=rate, cs=cs), encoding="utf-8")
    curl.chmod(0o755)
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "GITHUB_REPOSITORY": "o/r",
        "GITHUB_OUTPUT": str(out),
        "CI_BOT_TOKEN": token,
    }
    proc = subprocess.run(  # noqa: S603
        [BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert "unauthenticated curl call" not in proc.stderr, proc.stderr
    return proc.returncode, proc.stdout, out.read_text(encoding="utf-8").splitlines()


@pytest.fixture(params=PREFLIGHT_JOBS, ids=lambda p: f"{p[0]}:{p[1]}")
def script(request: pytest.FixtureRequest) -> str:
    return preflight_script(*request.param)


@requires_bash
def test_empty_token_uses_fallback(script: str, tmp_path: Path):
    code, _, outputs = run_preflight(script, tmp_path, "", "200", "200")
    assert code == 0
    assert outputs == ["use_pat=false"]


@requires_bash
def test_invalid_token_fails_hard(script: str, tmp_path: Path):
    code, stdout, outputs = run_preflight(script, tmp_path, "tok", "401", "200")
    assert code == 1
    assert "::error title=CI_BOT_TOKEN invalid::" in stdout
    assert "use_pat=true" not in outputs


@requires_bash
@pytest.mark.parametrize(
    ("cs", "expected"),
    [
        ("200", "use_pat=true"),
        ("404", "use_pat=false"),
        ("403", "use_pat=false"),
        ("500", "use_pat=true"),
    ],
)
def test_code_scanning_probe_decides_pat_use(
    script: str, tmp_path: Path, cs: str, expected: str
):
    code, stdout, outputs = run_preflight(script, tmp_path, "tok", "200", cs)
    assert code == 0
    assert outputs == [expected]
    if cs in ("403", "404"):
        assert f"can't reach the code-scanning API (HTTP {cs})" in stdout
    if cs == "500":
        assert "Could not verify code-scanning access" in stdout


@requires_bash
def test_code_scanning_401_fails_hard(script: str, tmp_path: Path):
    # /rate_limit passes but the code-scanning probe rejects the PAT: an
    # invalid token must never silently select the PAT (or the fallback).
    code, stdout, outputs = run_preflight(script, tmp_path, "tok", "200", "401")
    assert code == 1
    assert "::error title=CI_BOT_TOKEN invalid::" in stdout
    assert outputs == []


@requires_bash
def test_rate_limit_other_status_still_probes_code_scanning(
    script: str, tmp_path: Path
):
    code, _, outputs = run_preflight(script, tmp_path, "tok", "503", "404")
    assert code == 0
    assert outputs == ["use_pat=false"]


@requires_bash
def test_probes_without_bearer_header_are_rejected(script: str, tmp_path: Path):
    # Mutation check for the fake curl: drop the Authorization header from the
    # real script and the harness must notice the unauthenticated probe.
    stripped = "\n".join(
        line
        for line in script.splitlines()
        if "Authorization: Bearer" not in line
    )
    assert stripped != script
    with pytest.raises(AssertionError, match="unauthenticated curl call"):
        run_preflight(stripped, tmp_path, "tok", "200", "200")


def test_preflight_jobs_are_found():
    assert len(PREFLIGHT_JOBS) == 6
    for file_name, job_id in PREFLIGHT_JOBS:
        assert "code-scanning/analyses" in preflight_script(file_name, job_id)
