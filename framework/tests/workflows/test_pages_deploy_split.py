"""Guard: Pages artifact upload and deploy never share a job (#487).

Upstream actions/deploy-pages#451: when upload-pages-artifact and deploy-pages
run in one job, deploy-pages' ListArtifacts can return 0 shortly after the
artifact is finalised, and a re-run then duplicates the github-pages artifact.
Every job using actions/deploy-pages must therefore be a separate job that
`needs` the job doing the upload, with minimal permissions on both sides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

DEPLOY = "actions/deploy-pages@"
UPLOAD = "actions/upload-pages-artifact@"
DEPLOY_PERMISSIONS = {"pages": "write", "id-token": "write"}


def _uses(job: dict[str, Any], prefix: str) -> bool:
    return any(
        str(step.get("uses", "")).startswith(prefix) for step in job.get("steps") or []
    )


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _effective_permissions(
    job: dict[str, Any], workflow_perms: Any
) -> dict[str, str] | str | None:
    """A job-level block replaces the workflow-level one entirely."""
    return job["permissions"] if "permissions" in job else workflow_perms


def check_job(
    name: str,
    job: dict[str, Any],
    jobs: dict[str, Any],
    workflow_perms: Any = None,
) -> list[str]:
    """Return violations for one job that uses actions/deploy-pages."""
    problems: list[str] = []
    if _uses(job, UPLOAD):
        problems.append(f"{name}: uploads and deploys in the same job")
    uploaders = [n for n, j in jobs.items() if n != name and _uses(j, UPLOAD)]
    if not uploaders:
        problems.append(f"{name}: no job uploads the pages artifact")
    for uploader in uploaders:
        if uploader not in _needs(job):
            problems.append(f"{name}: needs does not include {uploader}")
        perms = _effective_permissions(jobs[uploader], workflow_perms)
        if isinstance(perms, dict) and "id-token" in perms:
            problems.append(f"{uploader}: upload job has id-token permission")
        if isinstance(perms, str):
            problems.append(f"{uploader}: upload job uses blanket permissions")
    perms = _effective_permissions(job, workflow_perms)
    if perms != DEPLOY_PERMISSIONS:
        problems.append(f"{name}: permissions {perms!r} != {DEPLOY_PERMISSIONS!r}")
    return problems


def _scan() -> tuple[int, list[str]]:
    found = 0
    problems: list[str] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jobs = doc.get("jobs") or {}
        for name, job in jobs.items():
            if isinstance(job, dict) and _uses(job, DEPLOY):
                found += 1
                problems += [
                    f"{path.name}: {p}"
                    for p in check_job(name, job, jobs, doc.get("permissions"))
                ]
    return found, problems


def test_deploy_jobs_found_non_vacuous() -> None:
    found, _ = _scan()
    assert found >= 2, f"expected release-please + deploy-pages.yml, found {found}"


def test_pages_upload_and_deploy_are_split() -> None:
    _, problems = _scan()
    assert not problems, "\n".join(problems)


def _good() -> dict[str, Any]:
    return {
        "build": {
            "permissions": {"contents": "read", "pages": "write"},
            "steps": [{"uses": f"{UPLOAD}abc"}],
        },
        "deploy": {
            "needs": ["build"],
            "permissions": dict(DEPLOY_PERMISSIONS),
            "steps": [{"uses": f"{DEPLOY}abc"}],
        },
    }


def test_selftest_good_shape_passes() -> None:
    jobs = _good()
    assert check_job("deploy", jobs["deploy"], jobs) == []


def test_selftest_same_job_upload_and_deploy_flagged() -> None:
    job = {
        "permissions": dict(DEPLOY_PERMISSIONS),
        "steps": [{"uses": f"{UPLOAD}abc"}, {"uses": f"{DEPLOY}abc"}],
    }
    assert any("same job" in p for p in check_job("d", job, {"d": job}))


def test_selftest_missing_needs_flagged() -> None:
    jobs = _good()
    del jobs["deploy"]["needs"]
    assert any("needs" in p for p in check_job("deploy", jobs["deploy"], jobs))


@pytest.mark.parametrize(
    "perms",
    [
        {"pages": "write", "id-token": "write", "contents": "read"},
        {"pages": "write"},
        None,
    ],
)
def test_selftest_wrong_deploy_permissions_flagged(perms: Any) -> None:
    jobs = _good()
    if perms is None:
        del jobs["deploy"]["permissions"]
    else:
        jobs["deploy"]["permissions"] = perms
    assert any("permissions" in p for p in check_job("deploy", jobs["deploy"], jobs))


def test_selftest_upload_with_id_token_flagged() -> None:
    jobs = _good()
    jobs["build"]["permissions"]["id-token"] = "write"
    assert any("id-token" in p for p in check_job("deploy", jobs["deploy"], jobs))
