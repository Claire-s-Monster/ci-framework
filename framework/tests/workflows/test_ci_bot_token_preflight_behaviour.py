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
# workflow_call sites calling the action through the remote form, probe off.
REMOTE_PROBE_OFF_JOBS = [
    ("self-healing.yml", "self-healing"),
    ("cleanup-dev-files.yml", "cleanup-dev-files"),
]
PROBE_OFF_JOBS = LOCAL_JOBS + REMOTE_PROBE_OFF_JOBS

# The pre-action inline preflight, frozen as a fixture (the inline copies no
# longer exist in any workflow): the equivalence test proves the action with
# `check-code-scanning: 'false'` behaves the same as that script did.
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


def test_no_workflow_carries_an_inline_preflight_run_step():
    # The inline copies are gone: any `run:` step named like the preflight in any
    # workflow would be an unpinned, untested copy of the action's script.
    inline = [
        f"{path.name}:{job_id}"
        for path in sorted(WORKFLOWS_DIR.glob("*.yml"))
        for job_id, job in (yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        .get("jobs", {})
        .items()
        for s in (job.get("steps") or [] if isinstance(job, dict) else [])
        if isinstance(s, dict) and s.get("name") == PREFLIGHT_STEP_NAME and "run" in s
    ]
    assert not inline, inline


BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(BASH is None, reason="bash is not available")

# The fake curl only answers a request that carries the bearer header for
# CI_BOT_TOKEN; otherwise it reports an unauthenticated call on stderr (which
# run_preflight turns into a failure) so a preflight that stops sending the
# token cannot pass on the canned status alone.
#
# A status value may be a comma-separated sequence ("503,503,200"): the Nth call
# for that URL gets the Nth entry (the last one repeats), counted in a file under
# CURL_STATE. The entry "fail" simulates a failed curl process: nothing on
# stdout and exit status 7 (the script must map that to 000). With `-D <file>` the stub writes response headers there, including
# `X-OAuth-Scopes` only when FAKE_SCOPES is set (even to the empty string).
FAKE_CURL = """#!/bin/sh
auth=0
prev=""
hdr=""
for arg; do
  if [ "$prev" = "-H" ] && [ "$arg" = "Authorization: Bearer $CI_BOT_TOKEN" ]; then
    auth=1
  fi
  if [ "$prev" = "-D" ]; then
    hdr="$arg"
  fi
  case "$arg" in
    http://*|https://*) url="$arg" ;;
  esac
  prev="$arg"
done
if [ -n "$CURL_LOG" ] && [ -n "$url" ]; then
  echo "$url" >> "$CURL_LOG"
fi
if [ "$auth" != 1 ]; then
  echo "unauthenticated curl call: $url" >&2
  printf '%s' "000"
  exit 0
fi
pick() {
  counter="$CURL_STATE/count_$1"
  n=$(cat "$counter" 2>/dev/null || echo 0)
  n=$((n + 1))
  echo "$n" > "$counter"
  total=$(printf '%s' "$2" | tr ',' '\\n' | wc -l)
  total=$((total + 1))
  [ "$n" -gt "$total" ] && n="$total"
  printf '%s' "$2" | cut -d, -f"$n"
}
case "$url" in
  */rate_limit) kind=rate; list="@RATE@" ;;
  */repos/o/r/code-scanning/analyses?per_page=1) kind=cs; list="@CS@" ;;
  *) kind=other; list="999" ;;
esac
status=$(pick "$kind" "$list")
if [ "$status" = "fail" ]; then
  # A real curl failure (timeout, DNS, refused): no status on stdout, exit 7.
  echo "curl: (7) simulated failure" >&2
  exit 7
fi
if [ -n "$hdr" ]; then
  {
    printf 'HTTP/2 200\\r\\n'
    if [ -n "${FAKE_SCOPES+x}" ]; then
      printf 'X-OAuth-Scopes: %s\\r\\n' "$FAKE_SCOPES"
    fi
    printf '\\r\\n'
  } > "$hdr"
fi
printf '%s' "$status"
"""

FAKE_SLEEP = """#!/bin/sh
echo "$1" >> "$SLEEP_LOG"
"""

CURL_LOG_NAME = "curl_requests"
SLEEP_LOG_NAME = "sleep_calls"


def requested_urls(tmp_path: Path) -> list[str]:
    """URLs the fake curl was asked for, in order (empty when none)."""
    log = tmp_path / CURL_LOG_NAME
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def sleep_calls(tmp_path: Path) -> list[str]:
    """Arguments the stub `sleep` was called with, in order (empty when none)."""
    log = tmp_path / SLEEP_LOG_NAME
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def rate_limit_calls(tmp_path: Path) -> int:
    """How many times the fake curl was asked for /rate_limit."""
    return sum(u.endswith("/rate_limit") for u in requested_urls(tmp_path))


def preflight_script(file_name: str, job_id: str) -> str:
    """The script a job's preflight step runs.

    Every site is an action call (remote form in the reusable-* and workflow_call
    workflows, `./` form in the standalone ones) and runs the composite action's
    script; no inline copy remains.
    """
    doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text(encoding="utf-8"))
    step = next(
        s for s in doc["jobs"][job_id]["steps"] if s.get("name") == PREFLIGHT_STEP_NAME
    )
    assert "uses" in step, f"{file_name}:{job_id} has an inline preflight"
    assert step["uses"].startswith(ACTION_USES_PREFIX) or step["uses"] == LOCAL_USES, (
        step["uses"]
    )
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    step = next(s for s in action["runs"]["steps"] if s.get("id") == "token-preflight")
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
    scopes: str | None = None,
    api_url: str | None = None,
) -> tuple[int, str, list[str]]:
    """Run `script` with a fake curl; return (exit code, stdout, GITHUB_OUTPUT lines).

    `check_code_scanning` sets CHECK_CODE_SCANNING like the action's input does
    (None leaves it unset); `curl_available=False` leaves curl off PATH entirely.
    `rate` and `cs` may be comma-separated status sequences, one entry per call.
    `scopes` is the X-OAuth-Scopes header value the fake curl returns (None
    sends no such header, as for a fine-grained PAT; "" sends it empty). The
    stub `sleep` only logs its argument (see `sleep_calls`). `api_url` sets
    GITHUB_API_URL (None leaves it unset); the env is built from scratch, so the
    outer GITHUB_API_URL that CI sets never leaks in.
    """
    assert BASH is not None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sleep = bin_dir / "sleep"
    sleep.write_text(FAKE_SLEEP, encoding="utf-8")
    sleep.chmod(0o755)
    if curl_available:
        curl = bin_dir / "curl"
        curl.write_text(
            FAKE_CURL.replace("@RATE@", rate).replace("@CS@", cs), encoding="utf-8"
        )
        curl.chmod(0o755)
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin" if curl_available else str(bin_dir),
        "GITHUB_REPOSITORY": "o/r",
        "GITHUB_OUTPUT": str(out),
        "CI_BOT_TOKEN": token,
        "CURL_LOG": str(tmp_path / CURL_LOG_NAME),
        "CURL_STATE": str(tmp_path),
        "SLEEP_LOG": str(tmp_path / SLEEP_LOG_NAME),
    }
    if check_code_scanning is not None:
        env["CHECK_CODE_SCANNING"] = check_code_scanning
    if scopes is not None:
        env["FAKE_SCOPES"] = scopes
    if api_url is not None:
        env["GITHUB_API_URL"] = api_url
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


@requires_bash
def test_fake_curl_logs_the_url_wherever_it_sits_in_the_arguments(tmp_path: Path):
    # The URL is identified by its scheme, not by being the last argument, so a
    # call with an option after the URL is still logged (and answered) by URL.
    url = "https://api.github.com/repos/o/r/code-scanning/analyses?per_page=1"
    script = (
        f'curl "{url}" -H "Authorization: Bearer $CI_BOT_TOKEN" -sS -o /dev/null\n'
        f'curl -sS "{url}" -H "Authorization: Bearer $CI_BOT_TOKEN"'
    )
    code, _, _ = run_preflight(script, tmp_path, "tok", "200", "200")
    assert code == 0
    assert requested_urls(tmp_path) == [url, url]


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
        ("429", "use_pat=true"),
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
    if cs == "429":
        assert "Could not verify code-scanning access" in stdout


@requires_bash
@pytest.mark.parametrize("cs", ["500", "502", "000"])
def test_code_scanning_5xx_or_000_fails_closed(script: str, tmp_path: Path, cs: str):
    code, stdout, outputs = run_preflight(script, tmp_path, "tok", "200", cs)
    assert code == 1
    assert "::error title=CI_BOT_TOKEN not checked::" in stdout
    assert outputs == []
    assert sleep_calls(tmp_path) == ["2", "4"]


@requires_bash
def test_code_scanning_retry_recovers(script: str, tmp_path: Path):
    code, _, outputs = run_preflight(script, tmp_path, "tok", "200", "502,200")
    assert code == 0
    assert outputs == ["use_pat=true"]
    assert sleep_calls(tmp_path) == ["2"]


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
    code, _, outputs = run_preflight(script, tmp_path, "tok", "429", "404")
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


@pytest.fixture(params=PROBE_OFF_JOBS, ids=lambda p: f"{p[0]}:{p[1]}")
def local_script(request: pytest.FixtureRequest) -> str:
    return preflight_script(*request.param)


def _preflight_step(file_name: str, job_id: str) -> dict:
    doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text(encoding="utf-8"))
    return next(
        s for s in doc["jobs"][job_id]["steps"] if s.get("name") == PREFLIGHT_STEP_NAME
    )


def test_probe_off_sites_call_the_action_with_the_probe_off():
    assert len(LOCAL_JOBS) == 3
    assert len(REMOTE_PROBE_OFF_JOBS) == 2
    for file_name, job_id in LOCAL_JOBS:
        step = _preflight_step(file_name, job_id)
        assert step["uses"] == LOCAL_USES
        assert step["with"]["check-code-scanning"] == "false"
        assert "run" not in step
    for file_name, job_id in REMOTE_PROBE_OFF_JOBS:
        step = _preflight_step(file_name, job_id)
        assert step["uses"].startswith(ACTION_USES_PREFIX + "@v")
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
    # Only /rate_limit was requested: a probe whose answer is ignored still fails.
    assert [u.rsplit("/", 1)[-1] for u in requested_urls(tmp_path)] == ["rate_limit"]


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
        local_script, tmp_path, "tok", "429", "404", check_code_scanning="false"
    )
    assert code == 0
    assert "::warning title=CI_BOT_TOKEN unchecked::" in stdout
    assert rate_limit_calls(tmp_path) == 1
    assert sleep_calls(tmp_path) == []


@requires_bash
def test_local_503_retries_then_fails_closed(local_script: str, tmp_path: Path):
    code, stdout, outputs = run_preflight(
        local_script, tmp_path, "tok", "503,503,503", "404", check_code_scanning="false"
    )
    assert code == 1
    assert "::error title=CI_BOT_TOKEN not checked::" in stdout
    assert outputs == []
    assert rate_limit_calls(tmp_path) == 3
    assert sleep_calls(tmp_path) == ["2", "4"]


@requires_bash
@pytest.mark.parametrize(
    ("api_url", "expected_base"),
    [
        pytest.param(None, "https://api.github.com", id="unset-uses-default"),
        pytest.param(
            "https://ghe.example.com/api/v3",
            "https://ghe.example.com/api/v3",
            id="ghes",
        ),
        pytest.param(
            "https://ghe.example.com/api/v3/",
            "https://ghe.example.com/api/v3",
            id="trailing-slash-stripped",
        ),
        pytest.param(
            "https://api.github.com/", "https://api.github.com", id="default-slash"
        ),
    ],
)
def test_both_probes_use_github_api_url(
    tmp_path: Path, api_url: str | None, expected_base: str
):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", "200", api_url=api_url
    )
    assert code == 0
    assert outputs == ["use_pat=true"]
    assert requested_urls(tmp_path) == [
        f"{expected_base}/rate_limit",
        f"{expected_base}/repos/o/r/code-scanning/analyses?per_page=1",
    ]


@requires_bash
@pytest.mark.parametrize("first", ["000", "fail"])
def test_curl_failure_then_success_retries_once(
    local_script: str, tmp_path: Path, first: str
):
    # "fail" is a nonzero curl exit with no status; "000" is the status string.
    code, stdout, outputs = run_preflight(
        local_script,
        tmp_path,
        "tok",
        f"{first},200",
        "404",
        check_code_scanning="false",
    )
    assert code == 0
    assert "CI_BOT_TOKEN is valid." in stdout
    assert outputs == ["use_pat=true"]
    assert rate_limit_calls(tmp_path) == 2
    assert sleep_calls(tmp_path) == ["2"]


@requires_bash
@pytest.mark.parametrize("failure", ["000", "fail"])
def test_persistent_curl_failure_fails_closed(
    local_script: str, tmp_path: Path, failure: str
):
    code, stdout, outputs = run_preflight(
        local_script, tmp_path, "tok", failure, "404", check_code_scanning="false"
    )
    assert code == 1
    assert "::error title=CI_BOT_TOKEN not checked::" in stdout
    assert outputs == []
    assert rate_limit_calls(tmp_path) == 3
    assert sleep_calls(tmp_path) == ["2", "4"]


@requires_bash
def test_code_scanning_curl_failure_then_success_retries(tmp_path: Path):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(script, tmp_path, "tok", "200", "fail,200")
    assert code == 0
    assert outputs == ["use_pat=true"]
    assert sleep_calls(tmp_path) == ["2"]


@requires_bash
def test_curl_missing_fails_closed_without_retry(local_script: str, tmp_path: Path):
    code, stdout, outputs = run_preflight(
        local_script,
        tmp_path,
        "tok",
        "200",
        "200",
        check_code_scanning="false",
        curl_available=False,
    )
    assert code == 1
    assert "::error title=CI_BOT_TOKEN not checked::" in stdout
    assert outputs == []
    assert sleep_calls(tmp_path) == []
    assert requested_urls(tmp_path) == []


@requires_bash
@pytest.mark.parametrize("probe", ["false", "true"])
@pytest.mark.parametrize("scopes", ["read:org", ""])
def test_classic_read_only_pat_falls_back(tmp_path: Path, probe: str, scopes: str):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, stdout, outputs = run_preflight(
        script, tmp_path, "tok", "200", "200", check_code_scanning=probe, scopes=scopes
    )
    assert code == 0
    assert "::warning title=CI_BOT_TOKEN read-only::" in stdout
    assert (scopes or "none") in stdout
    assert outputs == ["use_pat=false"]
    assert not any("code-scanning" in u for u in requested_urls(tmp_path))


@requires_bash
@pytest.mark.parametrize(
    ("scopes", "probe", "expected"),
    [
        ("repo", "false", "use_pat=true"),
        ("repo", "true", "use_pat=true"),
        ("public_repo, workflow", "false", "use_pat=true"),
        ("public_repo, workflow", "true", "use_pat=true"),
        ("read:org,repo", "true", "use_pat=true"),
        ("security_events", "true", "use_pat=true"),
    ],
)
def test_classic_write_scope_proceeds(
    tmp_path: Path, scopes: str, probe: str, expected: str
):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, stdout, outputs = run_preflight(
        script, tmp_path, "tok", "200", "200", check_code_scanning=probe, scopes=scopes
    )
    assert code == 0
    assert "read-only" not in stdout
    assert outputs == [expected]
    probed = any("code-scanning" in u for u in requested_urls(tmp_path))
    assert probed == (probe == "true")


@requires_bash
def test_security_events_scope_probe_off_is_read_only(tmp_path: Path):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, stdout, outputs = run_preflight(
        script,
        tmp_path,
        "tok",
        "200",
        "200",
        check_code_scanning="false",
        scopes="security_events",
    )
    assert code == 0
    assert "::warning title=CI_BOT_TOKEN read-only::" in stdout
    assert outputs == ["use_pat=false"]


@requires_bash
def test_security_events_scope_probe_on_reaches_code_scanning(tmp_path: Path):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", "404", scopes="security_events"
    )
    assert code == 0
    assert outputs == ["use_pat=false"]
    assert any("code-scanning" in u for u in requested_urls(tmp_path))


@requires_bash
@pytest.mark.parametrize("probe", ["false", "true"])
def test_missing_scopes_header_leaves_a_fine_grained_token_unchecked(
    tmp_path: Path, probe: str
):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, stdout, outputs = run_preflight(
        script, tmp_path, "tok", "200", "200", check_code_scanning=probe, scopes=None
    )
    assert code == 0
    assert "read-only" not in stdout
    assert outputs == ["use_pat=true"]


@requires_bash
def test_scopes_header_is_only_read_on_a_200(tmp_path: Path):
    # A 429 with a read-only scopes header must keep the warn-and-continue path.
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, stdout, outputs = run_preflight(
        script,
        tmp_path,
        "tok",
        "429",
        "200",
        check_code_scanning="false",
        scopes="read:org",
    )
    assert code == 0
    assert "read-only" not in stdout
    assert outputs == ["use_pat=true"]


@requires_bash
@pytest.mark.parametrize("cs", ["200", "401", "403", "404", "500"])
def test_probe_off_ignores_the_code_scanning_answer(tmp_path: Path, cs: str):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", cs, check_code_scanning="false"
    )
    assert code == 0
    assert outputs == ["use_pat=true"]
    assert not any("code-scanning" in u for u in requested_urls(tmp_path))


@requires_bash
@pytest.mark.parametrize("flag", [None, "true"])
def test_probe_on_by_default_and_when_true(tmp_path: Path, flag: str | None):
    script = preflight_script(*PREFLIGHT_JOBS[0])
    code, _, outputs = run_preflight(
        script, tmp_path, "tok", "200", "404", check_code_scanning=flag
    )
    assert code == 0
    assert outputs == ["use_pat=false"]


# 503, 000 and curl-missing are deliberately absent: the action now fails closed
# there (retry then exit 1; curl missing exits 1) while the frozen inline copy
# warns and continues. The new behaviour is asserted by the tests above.
EQUIVALENCE_CASES = [
    pytest.param("", "200", {}, id="empty-token"),
    pytest.param("tok", "200", {}, id="200"),
    pytest.param("tok", "401", {}, id="401"),
]


@requires_bash
@pytest.mark.parametrize("api_url", [None, "https://api.github.com"])
@pytest.mark.parametrize(("token", "rate", "extra"), EQUIVALENCE_CASES)
def test_probe_off_action_matches_the_old_inline_copy(
    tmp_path: Path, token: str, rate: str, extra: dict, api_url: str | None
):
    # Same stubbed curl for both; the code-scanning answer (401) would change the
    # outcome if the action probed, so equal results prove the probe is skipped.
    action_script = preflight_script(*PREFLIGHT_JOBS[0])
    inline_dir = tmp_path / "inline"
    action_dir = tmp_path / "action"
    inline_dir.mkdir()
    action_dir.mkdir()
    inline_code, inline_out, _ = run_preflight(
        INLINE_FIXTURE, inline_dir, token, rate, "401", api_url=api_url, **extra
    )
    action_code, action_out, _ = run_preflight(
        action_script,
        action_dir,
        token,
        rate,
        "401",
        check_code_scanning="false",
        api_url=api_url,
        **extra,
    )
    assert action_code == inline_code
    assert action_out == inline_out


def test_preflight_jobs_are_found():
    assert len(PREFLIGHT_JOBS) == 6
    for file_name, job_id in PREFLIGHT_JOBS:
        assert "code-scanning/analyses" in preflight_script(file_name, job_id)
