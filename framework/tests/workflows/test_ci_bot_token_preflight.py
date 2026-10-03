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

# The 11 jobs that consume secrets.CI_BOT_TOKEN today (c-cpp-lint no longer
# does once its dead SARIF upload is removed, #354):
#   reusable-ci.yml          sast-semgrep, sast-codeql, scorecard
#   reusable-security.yml    sast-semgrep, sast-codeql, scorecard
#   release-please.yml       release-please
#   cleanup-dev-files.yml    cleanup-dev-files
#   self-healing.yml         self-healing
#   auto-merge-release.yml   auto-merge-release
#   sync-main-to-development.yml  sync-to-development
#
# This floor EQUALS the live count by design (same convention as
# MINIMUM_EXPECTED_SITES in test_sarif_upload_auth.py): removing a consuming
# job is a deliberate act that should update this constant in the same commit,
# and the floor fails loudly if the walk or the matcher silently finds ~zero.
MINIMUM_EXPECTED_CONSUMING_JOBS = 11


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


def preflight_problems(step: dict) -> list[str]:
    """Everything wrong with a preflight step (empty list means it is sound)."""
    problems: list[str] = []
    env = step.get("env")
    env_value = env.get("CI_BOT_TOKEN") if isinstance(env, dict) else None
    if env_value != EXPECTED_ENV_VALUE:
        problems.append(f"env.CI_BOT_TOKEN must be {EXPECTED_ENV_VALUE!r}")
    run = step.get("run")
    run = run if isinstance(run, str) else ""
    for needle in ("/rate_limit", "401", "exit 1", "command -v curl"):
        if needle not in run:
            problems.append(f"run must contain {needle!r}")
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
    return preflight_problems(first)


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
    found = [job for _, _, job in all_jobs() if job_references_token(job)]
    assert len(found) >= MINIMUM_EXPECTED_CONSUMING_JOBS, (
        f"walk found {len(found)} consuming jobs, expected at least "
        f"{MINIMUM_EXPECTED_CONSUMING_JOBS}; the glob or matcher may be broken"
    )


def test_every_consuming_job_starts_with_a_sound_preflight_and_none_is_stale():
    failures = [
        f"{file_name}:{job_id}: {problem}"
        for file_name, job_id, job in all_jobs()
        for problem in job_problems(job)
    ]
    assert not failures, "\n".join(failures)


# --- Classifier self-tests (guard against a vacuously passing walk) ----------


def _preflight(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "env": {"CI_BOT_TOKEN": EXPECTED_ENV_VALUE},
        "run": (
            "command -v curl; curl https://api.github.com/rate_limit; "
            'case "$s" in 401) exit 1;; esac'
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
    assert len(problems) == 5  # env + /rate_limit + 401 + exit 1 + curl check


def test_selftest_stale_preflight_without_consumer_is_flagged():
    problems = job_problems({"steps": [_preflight(), {"run": "echo hi"}]})
    assert problems and "stale preflight" in problems[0]


def test_selftest_detector_excludes_the_preflight_step_itself():
    assert not job_references_token({"steps": [_preflight()]})
    assert job_references_token({"steps": [_preflight(), _consumer_step()]})


def test_selftest_job_not_referencing_token_is_not_flagged():
    job = {"steps": [{"run": "echo hi", "env": {"GH_TOKEN": "${{ github.token }}"}}]}
    assert job_problems(job) == []


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
