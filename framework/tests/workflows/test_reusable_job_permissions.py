"""Guard: job-level permission blocks in reusable-ci/security stay read-only.

A job block in a workflow_call workflow can only lower the caller's grant and
REPLACES it (unlisted scopes become none). Non-SARIF jobs carry a narrowing
`contents: read` block; the SARIF jobs and the jobs needing writes or
pull-requests: read inherit on purpose (see test_sarif_upload_auth.py).

Walk-the-tree guards can pass vacuously, hence the non-vacuity floor and the
walker self-test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
TARGETS = ("reusable-ci.yml", "reusable-security.yml")

ALLOWED_GRANTS = {("contents", "read"), ("actions", "read")}

# Jobs that must NOT have a block. SARIF/scorecard keep the caller's
# security-events/id-token grant; the others need writes or
# pull-requests: read, or create check runs.
MUST_INHERIT = {
    "reusable-ci.yml": {
        "sast-semgrep",
        "sast-codeql",
        "scorecard",
        "detect-changes",
        "c-cpp-lint",
        "rust-dep-audit",
    },
    "reusable-security.yml": {
        "sast-semgrep",
        "sast-codeql",
        "scorecard",
        "rust-dep-audit",
    },
}

MIN_BLOCKS = {"reusable-ci.yml": 15, "reusable-security.yml": 6}


def jobs_with_blocks(doc: dict) -> dict[str, object]:
    """Map job name to its `permissions:` value, for jobs that have one."""
    jobs = doc.get("jobs") or {}
    return {
        name: job["permissions"]
        for name, job in jobs.items()
        if isinstance(job, dict) and "permissions" in job
    }


def violations(blocks: dict[str, object]) -> list[str]:
    """Return a message per block granting anything outside ALLOWED_GRANTS."""
    bad = []
    for name, perms in blocks.items():
        if not isinstance(perms, dict) or not perms:
            bad.append(f"{name}: not a non-empty scope map ({perms!r})")
            continue
        for scope, level in perms.items():
            if (scope, level) not in ALLOWED_GRANTS:
                bad.append(f"{name}: {scope}: {level}")
    return bad


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TARGETS)
def test_job_blocks_are_read_only(name: str) -> None:
    assert violations(jobs_with_blocks(load(name))) == []


@pytest.mark.parametrize("name", TARGETS)
def test_walker_finds_job_blocks(name: str) -> None:
    """Non-vacuity: the walker must see the narrowed jobs."""
    assert len(jobs_with_blocks(load(name))) >= MIN_BLOCKS[name]


@pytest.mark.parametrize("name", TARGETS)
def test_must_inherit_jobs_have_no_block(name: str) -> None:
    doc = load(name)
    jobs = doc["jobs"]
    assert MUST_INHERIT[name] <= set(jobs), "stale MUST_INHERIT entry"
    assert MUST_INHERIT[name].isdisjoint(jobs_with_blocks(doc))


@pytest.mark.parametrize("name", TARGETS)
def test_no_top_level_block(name: str) -> None:
    assert "permissions" not in load(name)


def test_violation_classifier_self_test() -> None:
    assert violations({"a": {"contents": "read", "actions": "read"}}) == []
    assert violations({"a": {"contents": "write"}})
    assert violations({"a": {"pull-requests": "read"}})
    assert violations({"a": {"security-events": "write"}})
    assert violations({"a": "write-all"})
    assert violations({"a": {}})
    assert jobs_with_blocks({"jobs": {"a": {"permissions": {}}, "b": {}}}) == {"a": {}}
