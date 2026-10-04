"""Guard: Scorecard jobs with `publish_results: true` obey the webapp restrictions.

With `publish_results: true`, the OpenSSF Scorecard webapp re-reads the workflow
file and rejects the run if the `scorecard-action` job (or its workflow) breaks
the allowed shape. In a reusable workflow it verifies the reusable file itself.
Sources: ossf/scorecard-webapp `app/server/verify_workflow.go`
(`verifyScorecardWorkflow`) and the scorecard-action README, "Workflow
Restrictions". The restrictions enforced here:

  * every step of the job has `uses:` (a `run:` step is `errEmptyStepUses`:
    "scorecard job must only have steps with `uses`");
  * every `uses:` (version/ref stripped) is in the allowlist
    `actions/checkout`, `ossf/scorecard-action`, `actions/upload-artifact`,
    `github/codeql-action/upload-sarif`, `step-security/harden-runner`;
  * the job has no `container`, `services`, `env` or `defaults`;
  * `runs-on` is a single `ubuntu-*` label;
  * the workflow has no top-level `env`, `defaults` or write permission grant.

This is why the CI_BOT_TOKEN preflight (#355) is deliberately absent from the
Scorecard job. The helpers are pure so the self-tests exercise the exact code
the real test uses; the floor below stops the walk passing vacuously.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

SCORECARD_ACTION = "ossf/scorecard-action"
ALLOWED_USES = frozenset(
    {
        "actions/checkout",
        SCORECARD_ACTION,
        "actions/upload-artifact",
        "github/codeql-action/upload-sarif",
        "step-security/harden-runner",
    }
)
FORBIDDEN_JOB_KEYS = ("container", "services", "env", "defaults")
FORBIDDEN_WORKFLOW_KEYS = ("env", "defaults")

# Both reusable workflows publish Scorecard results today.
MINIMUM_EXPECTED_PUBLISHING_JOBS = 2


def strip_ref(uses: str) -> str:
    """`owner/repo/path@ref` -> `owner/repo/path`."""
    return uses.split("@", 1)[0]


def job_steps(job: object) -> list[dict]:
    """The job's steps as a list of dicts (empty for `uses:` callers)."""
    if not isinstance(job, dict) or not isinstance(job.get("steps"), list):
        return []
    return [step for step in job["steps"] if isinstance(step, dict)]


def _is_truthy(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def publishes_results(job: object) -> bool:
    """True if a step uses scorecard-action with a truthy `publish_results`."""
    for step in job_steps(job):
        uses = step.get("uses")
        if not isinstance(uses, str) or strip_ref(uses) != SCORECARD_ACTION:
            continue
        with_ = step.get("with")
        if isinstance(with_, dict) and _is_truthy(with_.get("publish_results")):
            return True
    return False


def _has_write_grant(permissions: object) -> bool:
    if isinstance(permissions, str):
        return "write" in permissions
    if isinstance(permissions, dict):
        return any(value == "write" for value in permissions.values())
    return False


def job_problems(job: object) -> list[str]:
    """Violations of the job-level restrictions (empty list means compliant)."""
    problems: list[str] = []
    job = job if isinstance(job, dict) else {}
    for index, step in enumerate(job_steps(job)):
        uses = step.get("uses")
        if not isinstance(uses, str):
            problems.append(f"step {index} has no `uses:` (only `uses` steps allowed)")
        elif strip_ref(uses) not in ALLOWED_USES:
            problems.append(f"step {index} uses {uses!r}, not in the allowlist")
    problems.extend(
        f"job must not set `{key}`" for key in FORBIDDEN_JOB_KEYS if key in job
    )
    runs_on = job.get("runs-on")
    if not (isinstance(runs_on, str) and runs_on.startswith("ubuntu-")):
        problems.append(f"runs-on must be a single ubuntu-* label, got {runs_on!r}")
    return problems


def workflow_problems(doc: object) -> list[str]:
    """Violations of the workflow-level restrictions."""
    doc = doc if isinstance(doc, dict) else {}
    problems = [
        f"workflow must not set top-level `{key}`"
        for key in FORBIDDEN_WORKFLOW_KEYS
        if key in doc
    ]
    if _has_write_grant(doc.get("permissions")):
        problems.append("workflow must not have a top-level write permission")
    return problems


def publishing_jobs() -> list[tuple[str, str, dict, object]]:
    """(file name, job id, workflow doc, job) for every publishing Scorecard job."""
    found: list[tuple[str, str, dict, object]] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = doc.get("jobs") if isinstance(doc, dict) else None
        if not isinstance(jobs, dict):
            continue
        found.extend(
            (path.name, job_id, doc, job)
            for job_id, job in jobs.items()
            if publishes_results(job)
        )
    return found


# --- Real-tree tests ---------------------------------------------------------


def test_walk_finds_the_publishing_scorecard_jobs():
    found = publishing_jobs()
    assert len(found) >= MINIMUM_EXPECTED_PUBLISHING_JOBS, (
        f"walk found {len(found)} publish_results jobs, expected at least "
        f"{MINIMUM_EXPECTED_PUBLISHING_JOBS}; the glob or matcher may be broken"
    )


def test_publishing_scorecard_jobs_meet_the_webapp_restrictions():
    failures = [
        f"{file_name}:{job_id}: {problem}"
        for file_name, job_id, doc, job in publishing_jobs()
        for problem in [*job_problems(job), *workflow_problems(doc)]
    ]
    assert not failures, "\n".join(failures)


# --- Classifier self-tests ---------------------------------------------------


def _compliant_job() -> dict:
    return {
        "runs-on": "ubuntu-latest",
        "steps": [
            {"uses": "actions/checkout@v7"},
            {"uses": "ossf/scorecard-action@v2.4.4", "with": {"publish_results": True}},
            {"uses": "github/codeql-action/upload-sarif@v4"},
        ],
    }


def test_selftest_compliant_shape_passes():
    job = _compliant_job()
    assert publishes_results(job)
    assert job_problems(job) == []
    assert workflow_problems({"permissions": {"contents": "read"}, "jobs": {}}) == []


def test_selftest_run_step_fails():
    job = _compliant_job()
    job["steps"].insert(0, {"run": "true"})
    assert any("no `uses:`" in problem for problem in job_problems(job))


def test_selftest_non_allowlisted_uses_fails():
    job = _compliant_job()
    job["steps"].append({"uses": "some/other-action@v1"})
    assert any("allowlist" in problem for problem in job_problems(job))


def test_selftest_job_env_fails():
    job = {**_compliant_job(), "env": {"A": "b"}}
    assert any("`env`" in problem for problem in job_problems(job))


def test_selftest_job_container_services_defaults_fail():
    for key in ("container", "services", "defaults"):
        job = {**_compliant_job(), key: {}}
        assert any(f"`{key}`" in problem for problem in job_problems(job)), key


def test_selftest_non_ubuntu_or_multi_label_runs_on_fails():
    for runs_on in ("windows-latest", ["ubuntu-latest", "x"], None):
        job = {**_compliant_job(), "runs-on": runs_on}
        assert any("runs-on" in problem for problem in job_problems(job)), runs_on


def test_selftest_workflow_defaults_env_and_write_grant_fail():
    assert workflow_problems({"defaults": {"run": {"shell": "bash"}}})
    assert workflow_problems({"env": {"A": "b"}})
    assert workflow_problems({"permissions": {"contents": "write"}})
    assert workflow_problems({"permissions": "write-all"})


def test_selftest_publish_detection():
    def job(value: object) -> dict:
        step = {"uses": "ossf/scorecard-action@v2", "with": {"publish_results": value}}
        return {"steps": [step]}

    assert publishes_results(job(True))
    assert publishes_results(job("true"))
    assert not publishes_results(job(False))
    assert not publishes_results(job("false"))
    assert not publishes_results({"steps": [{"uses": "ossf/scorecard-action@v2"}]})
