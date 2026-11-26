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
ACTION_PATH = REPO_ROOT / ".github" / "actions" / "verify-ci-bot-token" / "action.yml"
ACTION_USES_PREFIX = "Claire-s-Monster/ci-framework/.github/actions/verify-ci-bot-token"
PREFLIGHT_STEP_NAME = "Verify CI_BOT_TOKEN is valid"
PREFLIGHT_JOBS = [
    ("reusable-ci.yml", "sast-semgrep"),
    ("reusable-ci.yml", "sast-codeql"),
    ("reusable-security.yml", "sast-semgrep"),
    ("reusable-security.yml", "sast-codeql"),
    ("reusable-ci.yml", "scorecard-token-preflight"),
    ("reusable-security.yml", "scorecard-token-preflight"),
]
# Standalone sites calling the action through the local `./` form, probe off.
LOCAL_USES = "./.github/actions/verify-ci-bot-token"
LOCAL_JOBS = [
    ("release-please.yml", "release-please"),
    ("auto-merge-release.yml", "auto-merge-release"),
    ("sync-main-to-development.yml", "sync-to-development"),
]

# The pre-action inline preflight, kept verbatim as a fixture: the equivalence
# test proves the action with `check-code-scanning: 'false'` behaves the same.
INLINE_FIXTURE = r"""if [ -z "${CI_BOT_TOKEN}" ]; then
  echo "CI_BOT_TOKEN not set; using the github.token fallback."
  exit 0
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "::warning title=CI_BOT_TOKEN not checked::curl is unavailable here; skipping the check."
  exit 0
fi
status=$(curl --connect-timeout 5 --max-time 15 -sS -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${CI_BOT_TOKEN}" \
  https://api.github.com/rate_limit) || status="000"
case "${status}" in
  200) echo "CI_BOT_TOKEN is valid." ;;
  401)
    msg="CI_BOT_TOKEN is invalid or expired (HTTP 401)."
    msg="${msg} Rotate it, or delete the secret to fall back to github.token."
    echo "::error title=CI_BOT_TOKEN invalid::${msg}"
    exit 1
    ;;
  *) echo "::warning title=CI_BOT_TOKEN unchecked::/rate_limit returned HTTP ${status}; not failing." ;;
esac
"""


def standalone_preflight_jobs() -> list[tuple[str, str]]:
    """Every (workflow, job) outside PREFLIGHT_JOBS with a `run:` preflight step.

    Found by walking `.github/workflows/`, so a workflow that copies the
    preflight is covered without editing a list. Only the two `workflow_call`
    workflows (self-healing, cleanup-dev-files) still carry one; these copies
    only run the /rate_limit check (no code-scanning probe, no GITHUB_OUTPUT).
    """
    found: list[tuple[str, str]] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_id, job in (doc.get("jobs") or {}).items():
            steps = job.get("steps") or [] if isinstance(job, dict) else []
            has_step = any(
                isinstance(s, dict)
                and s.get("name") == PREFLIGHT_STEP_NAME
                and "run" in s
                for s in steps
            )
            if has_step and (path.name, job_id) not in PREFLIGHT_JOBS:
                found.append((path.name, job_id))
    return found


STANDALONE_PREFLIGHT_JOBS = standalone_preflight_jobs()

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
    """The script a job's preflight step runs.

    An action call (the six reusable sites, remote form; the three standalone
    sites, `./` form) runs the composite action's script; an inline step (the
    two workflow_call workflows) carries its own.
    """
    doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text(encoding="utf-8"))
    step = next(
        s for s in doc["jobs"][job_id]["steps"] if s.get("name") == PREFLIGHT_STEP_NAME
    )
    if "uses" in step:
        assert (
            step["uses"].startswith(ACTION_USES_PREFIX) or step["uses"] == LOCAL_USES
        ), step["uses"]
        action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
        step = next(
            s for s in action["runs"]["steps"] if s.get("id") == "token-preflight"
        )
    run = step["run"]
    assert "${{" not in run
    return run


def run_preflight(
    script: str,
    tmp_path: Path,
    token: str,
    rate: str,
    cs: str,
    check_code_scanning: str | None = None,
    curl_available: bool = True,
) -> tuple[int, str, list[str]]:
    """Run `script` with a fake curl; return (exit code, stdout, GITHUB_OUTPUT lines).

    `check_code_scanning` sets CHECK_CODE_SCANNING like the action's input does
    (None leaves it unset); `curl_available=False` leaves curl off PATH entirely.
    """
    assert BASH is not None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if curl_available:
        curl = bin_dir / "curl"
        curl.write_text(FAKE_CURL.format(rate=rate, cs=cs), encoding="utf-8")
        curl.chmod(0o755)
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin" if curl_available else str(bin_dir),
        "GITHUB_REPOSITORY": "o/r",
        "GITHUB_OUTPUT": str(out),
        "CI_BOT_TOKEN": token,
    }
    if check_code_scanning is not None:
        env["CHECK_CODE_SCANNING"] = check_code_scanning
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
        line for line in script.splitlines() if "Authorization: Bearer" not in line
    )
    assert stripped != script
    with pytest.raises(AssertionError, match="unauthenticated curl call"):
        run_preflight(stripped, tmp_path, "tok", "200", "200")


@pytest.fixture(params=STANDALONE_PREFLIGHT_JOBS, ids=lambda p: f"{p[0]}:{p[1]}")
def standalone_script(request: pytest.FixtureRequest) -> str:
    return preflight_script(*request.param)


@requires_bash
def test_standalone_empty_token_uses_fallback(standalone_script: str, tmp_path: Path):
    code, stdout, _ = run_preflight(standalone_script, tmp_path, "", "200", "200")
    assert code == 0
    assert "not set; using the github.token fallback" in stdout


@requires_bash
def test_standalone_valid_token_passes(standalone_script: str, tmp_path: Path):
    code, stdout, _ = run_preflight(standalone_script, tmp_path, "tok", "200", "200")
    assert code == 0
    assert "CI_BOT_TOKEN is valid." in stdout


@requires_bash
def test_standalone_invalid_token_fails_hard(standalone_script: str, tmp_path: Path):
    code, stdout, _ = run_preflight(standalone_script, tmp_path, "tok", "401", "200")
    assert code == 1
    assert "::error title=CI_BOT_TOKEN invalid::" in stdout


@requires_bash
def test_standalone_other_status_warns_without_failing(
    standalone_script: str, tmp_path: Path
):
    code, stdout, _ = run_preflight(standalone_script, tmp_path, "tok", "503", "200")
    assert code == 0
    assert "::warning title=CI_BOT_TOKEN unchecked::" in stdout


@requires_bash
def test_standalone_probe_without_bearer_header_is_rejected(
    standalone_script: str, tmp_path: Path
):
    stripped = "\n".join(
        line
        for line in standalone_script.splitlines()
        if "Authorization: Bearer" not in line
    )
    assert stripped != standalone_script
    with pytest.raises(AssertionError, match="unauthenticated curl call"):
        run_preflight(stripped, tmp_path, "tok", "200", "200")


def test_standalone_preflight_jobs_are_found():
    # Non-vacuity floor: exactly the two workflow_call copies (self-healing,
    # cleanup-dev-files) must be found, otherwise the parametrised inline tests
    # above would silently run zero cases.
    assert sorted(STANDALONE_PREFLIGHT_JOBS) == [
        ("cleanup-dev-files.yml", "cleanup-dev-files"),
        ("self-healing.yml", "self-healing"),
    ]


@pytest.fixture(params=LOCAL_JOBS, ids=lambda p: f"{p[0]}:{p[1]}")
def local_script(request: pytest.FixtureRequest) -> str:
    return preflight_script(*request.param)


def test_local_sites_call_the_action_with_the_probe_off():
    assert len(LOCAL_JOBS) == 3
    for file_name, job_id in LOCAL_JOBS:
        doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text(encoding="utf-8"))
        step = next(
            s
            for s in doc["jobs"][job_id]["steps"]
            if s.get("name") == PREFLIGHT_STEP_NAME
        )
        assert step["uses"] == LOCAL_USES
        assert step["with"]["check-code-scanning"] == "false"
        assert "run" not in step


@requires_bash
def test_local_empty_token_uses_fallback(local_script: str, tmp_path: Path):
    code, stdout, outputs = run_preflight(
        local_script, tmp_path, "", "200", "200", check_code_scanning="false"
    )
    assert code == 0
    assert "not set; using the github.token fallback" in stdout
    assert outputs == ["use_pat=false"]


@requires_bash
def test_local_valid_token_skips_the_probe(local_script: str, tmp_path: Path):
    # cs=401 would fail the run if the code-scanning probe were issued.
    code, stdout, outputs = run_preflight(
        local_script, tmp_path, "tok", "200", "401", check_code_scanning="false"
    )
    assert code == 0
    assert "CI_BOT_TOKEN is valid." in stdout
    assert outputs == ["use_pat=true"]


@requires_bash
def test_local_invalid_token_fails_hard(local_script: str, tmp_path: Path):
    code, stdout, outputs = run_preflight(
        local_script, tmp_path, "tok", "401", "200", check_code_scanning="false"
    )
    assert code == 1
    assert "::error title=CI_BOT_TOKEN invalid::" in stdout
    assert outputs == []


@requires_bash
def test_local_other_status_warns_without_failing(local_script: str, tmp_path: Path):
    code, stdout, _ = run_preflight(
        local_script, tmp_path, "tok", "503", "404", check_code_scanning="false"
    )
    assert code == 0
    assert "::warning title=CI_BOT_TOKEN unchecked::" in stdout


@requires_bash
@pytest.mark.parametrize("cs", ["200", "401", "403", "404", "500"])
def test_probe_off_ignores_the_code_scanning_answer(tmp_path: Path, cs: str):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", cs, check_code_scanning="false"
    )
    assert code == 0
    assert outputs == ["use_pat=true"]


@requires_bash
@pytest.mark.parametrize("flag", [None, "true"])
def test_probe_on_by_default_and_when_true(tmp_path: Path, flag: str | None):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", "404", check_code_scanning=flag
    )
    assert code == 0
    assert outputs == ["use_pat=false"]


EQUIVALENCE_CASES = [
    pytest.param("", "200", {}, id="empty-token"),
    pytest.param("tok", "200", {}, id="200"),
    pytest.param("tok", "401", {}, id="401"),
    pytest.param("tok", "503", {}, id="503"),
    pytest.param("tok", "000", {}, id="000"),
    pytest.param("tok", "200", {"curl_available": False}, id="curl-missing"),
]


@requires_bash
@pytest.mark.parametrize(("token", "rate", "extra"), EQUIVALENCE_CASES)
def test_probe_off_action_matches_the_old_inline_copy(
    tmp_path: Path, token: str, rate: str, extra: dict
):
    # Same stubbed curl for both; the code-scanning answer (401) would change the
    # outcome if the action probed, so equal results prove the probe is skipped.
    action_script = preflight_script(*PREFLIGHT_JOBS[0])
    inline_dir = tmp_path / "inline"
    action_dir = tmp_path / "action"
    inline_dir.mkdir()
    action_dir.mkdir()
    inline_code, inline_out, _ = run_preflight(
        INLINE_FIXTURE, inline_dir, token, rate, "401", **extra
    )
    action_code, action_out, _ = run_preflight(
        action_script,
        action_dir,
        token,
        rate,
        "401",
        check_code_scanning="false",
        **extra,
    )
    assert action_code == inline_code
    assert action_out == inline_out


def test_inline_fixture_matches_the_remaining_inline_copies():
    # The fixture must stay the exact script the two workflow_call workflows run.
    for file_name, job_id in STANDALONE_PREFLIGHT_JOBS:
        assert preflight_script(file_name, job_id) == INLINE_FIXTURE, file_name


def test_preflight_jobs_are_found():
    assert len(PREFLIGHT_JOBS) == 6
    for file_name, job_id in PREFLIGHT_JOBS:
        assert "code-scanning/analyses" in preflight_script(file_name, job_id)
