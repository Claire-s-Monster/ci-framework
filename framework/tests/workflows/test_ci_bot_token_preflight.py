"""Guard: every job that consumes `secrets.CI_BOT_TOKEN` verifies it first.

Issue #355. `${{ secrets.CI_BOT_TOKEN || github.token }}` falls back only when
the secret is EMPTY. An expired or revoked PAT is still non-empty, so it wins
the `||` and the API rejects it with HTTP 401 (Bad credentials). At the SARIF
sites (`continue-on-error: true`) that failure is silent.

The fix is an inline preflight step, `Verify CI_BOT_TOKEN is valid`, as the
FIRST step of every job that references the secret. It is inline rather than a
composite action because in-repo composite actions are referenced remotely and
pinned to a tag, where a new action would not exist, and `./` references in a
reusable workflow resolve against the CALLER's checkout (#262).

This guard enforces, for every job in every workflow and workflow template:

  * the job's first step is the preflight (by exact name);
  * the preflight passes the token through `env:` and never interpolates
    `${{ ... }}` inside `run:` (script injection);
  * the preflight probes `/rate_limit` and hard-fails (`exit 1`) on 401;
  * the preflight has neither `continue-on-error` nor `if`, so it can neither
    be swallowed nor skipped.

Like `test_sarif_upload_auth.py`, this module walks `*.yml.template` files too
(a template that consumes the token ships the gap to every consumer) and keeps
its helpers pure so the classifier self-tests exercise the exact code the real
test uses. Walk-the-tree guards can pass vacuously, hence the floor and the
self-tests below.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

PREFLIGHT_STEP_NAME = "Verify CI_BOT_TOKEN is valid"
TOKEN_REFERENCE = re.compile(r"secrets\.CI_BOT_TOKEN\b")
EXPECTED_ENV_VALUE = "${{ secrets.CI_BOT_TOKEN }}"
PREFLIGHT_STEP_ID = "token-preflight"
RUN_NEEDLES = (
    "/rate_limit",
    "401",
    "exit 1",
    "command -v curl",
    "--max-time",
)
# Extra requirements for a preflight whose job uploads SARIF (#482): it also
# probes code-scanning access and publishes the verdict as a step output.
SARIF_RUN_NEEDLES = ("code-scanning/analyses", "use_pat=", "GITHUB_OUTPUT")
# #482: SARIF uploads use the PAT only when the preflight confirmed
# code-scanning access.
USE_PAT_EXPRESSION = "steps.token-preflight.outputs.use_pat"
SARIF_ACTION_PREFIXES = (
    "github/codeql-action/upload-sarif@",
    "github/codeql-action/analyze@",
)
SARIF_WORKFLOWS = ("reusable-ci.yml", "reusable-security.yml")
MINIMUM_EXPECTED_SARIF_SITES = 4

# Jobs that consume the token but must NOT carry the preflight. The Scorecard
# job runs `ossf/scorecard-action` with `publish_results: true`, and the
# scorecard webapp verifies the workflow file itself: the job may only have
# allowlisted `uses:` steps (no `run:`). A preflight there would make the
# verification reject the job. The SAST jobs of the same workflow consume the
# same token and perform the check. See test_scorecard_publish_restrictions.py.
PREFLIGHT_EXEMPT_JOBS: frozenset[tuple[str, str]] = frozenset(
    {
        ("reusable-ci.yml", "scorecard"),
        ("reusable-security.yml", "scorecard"),
    }
)

# The 11 jobs that consume secrets.CI_BOT_TOKEN today (c-cpp-lint no longer
# does once its dead SARIF upload is removed, #354; the pixi lock refresh job
# no longer does once it runs on github.token, #387):
#   reusable-ci.yml          sast-semgrep, sast-codeql, scorecard (exempt)
#   reusable-security.yml    sast-semgrep, sast-codeql, scorecard (exempt)
#   release-please.yml       release-please
#   cleanup-dev-files.yml    cleanup-dev-files
#   self-healing.yml         self-healing
#   auto-merge-release.yml   auto-merge-release
#   sync-main-to-development.yml  sync-to-development
#
# This floor EQUALS the live count of consuming jobs that carry a preflight
# (11 - 2 exempt = 9) by design (same convention as MINIMUM_EXPECTED_SITES in
# test_sarif_upload_auth.py): removing a consuming job is a deliberate act that
# should update this constant in the same commit, and the floor fails loudly if
# the walk or the matcher silently finds ~zero.
MINIMUM_EXPECTED_CONSUMING_JOBS = 9


def workflow_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml`, `*.yaml` and `*.yml.template` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and (path.suffix in (".yml", ".yaml") or path.name.endswith(".yml.template"))
    )


def iter_strings(node: object):
    """Yield every string found anywhere in a nested dict/list structure."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from iter_strings(key)
            yield from iter_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_strings(item)


def job_steps(job: object) -> list[dict]:
    """The job's steps as a list of dicts (empty for `uses:` callers)."""
    if not isinstance(job, dict):
        return []
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def job_has_preflight(job: object) -> bool:
    """True if any step of the job is named like the preflight step."""
    return any(step.get("name") == PREFLIGHT_STEP_NAME for step in job_steps(job))


def job_references_token(job: object) -> bool:
    """True if the job consumes `secrets.CI_BOT_TOKEN` outside its preflight.

    Covers step `with`/`env`/`run`/`if`, job-level `env`/`if`, and a
    `uses:`-caller's `secrets:` mapping, by scanning every string in the job.
    The preflight step itself is EXCLUDED (by exact name): it always carries
    `env.CI_BOT_TOKEN: ${{ secrets.CI_BOT_TOKEN }}`, so counting it would make
    every job with a preflight a "consumer" and a stale preflight in a job
    that no longer uses the token could never be flagged.
    """
    if isinstance(job, dict) and isinstance(job.get("steps"), list):
        job = {
            **job,
            "steps": [
                step
                for step in job["steps"]
                if not (
                    isinstance(step, dict) and step.get("name") == PREFLIGHT_STEP_NAME
                )
            ],
        }
    return any(TOKEN_REFERENCE.search(text) for text in iter_strings(job))


def preflight_problems(step: dict, sarif: bool = False) -> list[str]:
    """Everything wrong with a preflight step (empty list means it is sound).

    `sarif` marks a job that uploads SARIF with the token; its preflight must
    also probe code-scanning access and expose `use_pat` under the fixed id.
    """
    problems: list[str] = []
    env = step.get("env")
    env_value = env.get("CI_BOT_TOKEN") if isinstance(env, dict) else None
    if env_value != EXPECTED_ENV_VALUE:
        problems.append(f"env.CI_BOT_TOKEN must be {EXPECTED_ENV_VALUE!r}")
    run = step.get("run")
    run = run if isinstance(run, str) else ""
    for needle in RUN_NEEDLES:
        if needle not in run:
            problems.append(f"run must contain {needle!r}")
    if sarif:
        for needle in SARIF_RUN_NEEDLES:
            if needle not in run:
                problems.append(f"run must contain {needle!r}")
        if step.get("id") != PREFLIGHT_STEP_ID:
            problems.append(f"step must have id: {PREFLIGHT_STEP_ID}")
    if "${{" in run:
        problems.append("run must not interpolate ${{ }} (script injection)")
    if "continue-on-error" in step:
        problems.append("must not set continue-on-error")
    if "if" in step:
        problems.append("must not have an `if:`")
    return problems


def job_problems(job: object) -> list[str]:
    """Problems with a job; empty if it neither consumes the token nor has a preflight.

    A preflight in a job that no longer consumes the token is STALE and flagged.
    """
    if not job_references_token(job):
        if job_has_preflight(job):
            return ["stale preflight: job has the step but no CI_BOT_TOKEN consumer"]
        return []
    steps = job_steps(job)
    if not steps:
        return ["consumes CI_BOT_TOKEN but has no steps to host the preflight"]
    first = steps[0]
    if first.get("name") != PREFLIGHT_STEP_NAME:
        return [f"first step must be named {PREFLIGHT_STEP_NAME!r}"]
    return preflight_problems(first, sarif=bool(sarif_token_sites("", "", job)))


def exempt_aware_problems(file_name: str, job_id: str, job: object) -> list[str]:
    """Problems with a job, honouring PREFLIGHT_EXEMPT_JOBS.

    An exempt job must NOT carry the preflight (re-adding it breaks Scorecard
    `publish_results` verification); every other job goes through `job_problems`.
    """
    if (file_name, job_id) in PREFLIGHT_EXEMPT_JOBS:
        if job_has_preflight(job):
            return ["exempt job must not carry the preflight (breaks publish_results)"]
        return []
    return job_problems(job)


def sarif_token_sites(
    file_name: str, job_id: str, job: object
) -> list[tuple[str, str]]:
    """(label, token expression) of each SARIF upload step that sets a token.

    Covers `upload-sarif` steps and `analyze` steps with `token:` (those upload
    natively). Exempt jobs (scorecard) are skipped: they cannot host a preflight.
    """
    if (file_name, job_id) in PREFLIGHT_EXEMPT_JOBS:
        return []
    sites: list[tuple[str, str]] = []
    for index, step in enumerate(job_steps(job)):
        uses = step.get("uses")
        with_ = step.get("with")
        if not isinstance(uses, str) or not uses.startswith(SARIF_ACTION_PREFIXES):
            continue
        if not isinstance(with_, dict) or "token" not in with_:
            continue
        label = f"{file_name}:{job_id}:step[{index}]"
        sites.append((label, str(with_["token"])))
    return sites


def load_jobs(path: Path) -> dict:
    """The `jobs:` mapping of a workflow file (empty if absent or unparsable shape)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    return jobs if isinstance(jobs, dict) else {}


def all_jobs() -> list[tuple[str, str, object]]:
    """(file name, job id, job) for every job in every workflow file."""
    return [
        (path.name, job_id, job)
        for path in workflow_files()
        for job_id, job in load_jobs(path).items()
    ]


# --- Real-tree tests ---------------------------------------------------------


def test_walk_finds_the_expected_number_of_consuming_jobs():
    found = [
        job
        for _, _, job in all_jobs()
        if job_references_token(job) and job_has_preflight(job)
    ]
    assert len(found) >= MINIMUM_EXPECTED_CONSUMING_JOBS, (
        f"walk found {len(found)} consuming jobs with a preflight, expected at "
        f"least {MINIMUM_EXPECTED_CONSUMING_JOBS}; the glob or matcher may be broken"
    )


def test_every_consuming_job_starts_with_a_sound_preflight_and_none_is_stale():
    failures = [
        f"{file_name}:{job_id}: {problem}"
        for file_name, job_id, job in all_jobs()
        for problem in exempt_aware_problems(file_name, job_id, job)
    ]
    assert not failures, "\n".join(failures)


def test_exempt_jobs_are_exactly_the_consumers_without_a_preflight():
    unprotected = {
        (file_name, job_id)
        for file_name, job_id, job in all_jobs()
        if job_references_token(job) and not job_has_preflight(job)
    }
    assert unprotected == PREFLIGHT_EXEMPT_JOBS, (
        f"consuming jobs without a preflight: {sorted(unprotected)}; "
        f"exemptions: {sorted(PREFLIGHT_EXEMPT_JOBS)} (stale or missing exemption)"
    )


def _sarif_sites() -> list[tuple[str, str]]:
    return [
        site
        for path in workflow_files()
        if path.name in SARIF_WORKFLOWS
        for job_id, job in load_jobs(path).items()
        for site in sarif_token_sites(path.name, job_id, job)
    ]


def test_walk_finds_the_sarif_upload_sites():
    sites = _sarif_sites()
    assert len(sites) >= MINIMUM_EXPECTED_SARIF_SITES, (
        f"walk found {len(sites)} SARIF token sites, expected at least "
        f"{MINIMUM_EXPECTED_SARIF_SITES}; the walk or matcher may be broken"
    )


def test_every_sarif_upload_uses_pat_only_when_preflight_confirms_access():
    failures = [
        f"{label}: token is {token!r}"
        for label, token in _sarif_sites()
        if USE_PAT_EXPRESSION not in token
        or "secrets.CI_BOT_TOKEN" not in token
        or "github.token" not in token
    ]
    assert not failures, "\n".join(failures)


# --- Classifier self-tests (guard against a vacuously passing walk) ----------


def _preflight(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "env": {"CI_BOT_TOKEN": EXPECTED_ENV_VALUE},
        "run": (
            "command -v curl; curl --max-time 15 https://api.github.com/rate_limit; "
            "curl /code-scanning/analyses; "
            'case "$s" in 401) exit 1;; esac; echo "use_pat=true" >> "$GITHUB_OUTPUT"'
        ),
    }
    step.update(overrides)
    return step


def _consumer_step() -> dict:
    return {
        "uses": "actions/checkout@v7",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }


def test_selftest_sound_job_is_not_flagged():
    assert job_problems({"steps": [_preflight(), _consumer_step()]}) == []


def test_selftest_job_without_preflight_is_flagged():
    problems = job_problems({"steps": [_consumer_step()]})
    assert problems and "first step" in problems[0]


def test_selftest_preflight_not_first_is_flagged():
    job = {"steps": [{"run": "true"}, _preflight(), _consumer_step()]}
    assert job_problems(job)


def test_selftest_uses_caller_job_without_steps_is_flagged():
    job = {
        "uses": "o/r/.github/workflows/w.yml@v1",
        "secrets": {"CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"},
    }
    assert job_problems(job)


def test_selftest_interpolation_inside_run_is_flagged():
    run = 'curl /rate_limit; echo "${{ secrets.CI_BOT_TOKEN }}"; 401 exit 1'
    problems = job_problems({"steps": [_preflight(run=run), _consumer_step()]})
    assert any("script injection" in problem for problem in problems)


def test_selftest_continue_on_error_is_flagged():
    step = _preflight(**{"continue-on-error": True})
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert any("continue-on-error" in problem for problem in problems)


def test_selftest_if_on_preflight_is_flagged():
    problems = job_problems(
        {"steps": [_preflight(**{"if": "always()"}), _consumer_step()]}
    )
    assert any("`if:`" in problem for problem in problems)


def test_selftest_wrong_env_and_missing_markers_are_flagged():
    step = _preflight(env={"CI_BOT_TOKEN": "x"}, run="true")
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert len(problems) == 1 + len(RUN_NEEDLES)  # env + every run marker


def _sarif_upload_step() -> dict:
    return {
        "uses": "github/codeql-action/upload-sarif@abc",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }


def test_selftest_sarif_job_requires_probe_output_and_id():
    step = _preflight(id="other", run=_preflight()["run"].replace("use_pat=", "x="))
    problems = job_problems({"steps": [step, _sarif_upload_step()]})
    assert any("id:" in problem for problem in problems)
    assert any("use_pat=" in problem for problem in problems)


def test_selftest_non_sarif_job_needs_no_probe_or_id():
    step = _preflight(
        id="other", run="command -v curl; curl --max-time 1 /rate_limit; 401 exit 1"
    )
    assert job_problems({"steps": [step, _consumer_step()]}) == []


def test_selftest_sound_sarif_job_is_not_flagged():
    assert job_problems({"steps": [_preflight(), _sarif_upload_step()]}) == []


def test_selftest_sarif_site_matcher_flags_bare_token_and_skips_exempt():
    upload = {
        "uses": "github/codeql-action/upload-sarif@abc",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }
    no_token = {"uses": "github/codeql-action/analyze@abc", "with": {"upload": False}}
    job = {"steps": [_preflight(), no_token, upload]}
    sites = sarif_token_sites("other.yml", "j", job)
    assert len(sites) == 1 and USE_PAT_EXPRESSION not in sites[0][1]
    assert sarif_token_sites(*next(iter(PREFLIGHT_EXEMPT_JOBS)), job) == []


def test_selftest_curl_without_max_time_is_flagged():
    step = _preflight(
        run="command -v curl; curl https://api.github.com/rate_limit; "
        'curl /code-scanning/analyses; echo use_pat= >> "$GITHUB_OUTPUT"; '
        'case "$s" in 401) exit 1;; esac'
    )
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert any("--max-time" in problem for problem in problems)


def test_selftest_stale_preflight_without_consumer_is_flagged():
    problems = job_problems({"steps": [_preflight(), {"run": "echo hi"}]})
    assert problems and "stale preflight" in problems[0]


def test_selftest_detector_excludes_the_preflight_step_itself():
    assert not job_references_token({"steps": [_preflight()]})
    assert job_references_token({"steps": [_preflight(), _consumer_step()]})


def test_selftest_job_not_referencing_token_is_not_flagged():
    job = {"steps": [{"run": "echo hi", "env": {"GH_TOKEN": "${{ github.token }}"}}]}
    assert job_problems(job) == []


def test_selftest_exempt_job_without_preflight_passes():
    pair = next(iter(PREFLIGHT_EXEMPT_JOBS))
    assert exempt_aware_problems(*pair, {"steps": [_consumer_step()]}) == []


def test_selftest_exempt_job_with_preflight_fails():
    pair = next(iter(PREFLIGHT_EXEMPT_JOBS))
    job = {"steps": [_preflight(), _consumer_step()]}
    problems = exempt_aware_problems(*pair, job)
    assert problems and "exempt job" in problems[0]


def test_selftest_non_exempt_job_without_preflight_fails():
    problems = exempt_aware_problems(
        "other.yml", "some-job", {"steps": [_consumer_step()]}
    )
    assert problems and "first step" in problems[0]


def test_selftest_reference_detector_finds_token_in_every_location():
    expr = "${{ secrets.CI_BOT_TOKEN || github.token }}"
    locations = {
        "with": {"steps": [{"uses": "x", "with": {"token": expr}}]},
        "env": {"steps": [{"run": "true", "env": {"T": expr}}]},
        "run": {"steps": [{"run": f"echo {expr}"}]},
        "step if": {"steps": [{"run": "true", "if": f"{expr} != ''"}]},
        "job if": {"if": f"{expr} != ''", "steps": [{"run": "true"}]},
        "job env": {"env": {"T": expr}, "steps": [{"run": "true"}]},
    }
    for label, job in locations.items():
        assert job_references_token(job), label
    assert not job_references_token({"steps": [{"run": "echo secrets.OTHER"}]})
    assert not job_references_token({"steps": [{"run": "secrets.CI_BOT_TOKEN_X"}]})
