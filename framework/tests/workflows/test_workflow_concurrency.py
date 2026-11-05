"""Guards for workflow `concurrency:` blocks.

Rapid pushes (a release does two pushes to main within minutes) used to run
every workflow in full in parallel. Each directly triggered workflow now has a
concurrency group. Reusable (`workflow_call`) workflows must not use
`github.workflow` in a top-level group: inside a called workflow it resolves to
the caller's name, so unrelated callers would collide.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(".github/workflows")
CLEANUP = "cleanup-dev-files.yml"


def _get_on(doc: dict):
    """Return the `on:` mapping; PyYAML parses an unquoted `on:` as `True`."""
    if "on" in doc:
        return doc["on"]
    return doc.get(True, {})


def _load(name: str) -> dict:
    doc = yaml.safe_load((WORKFLOWS_DIR / name).read_text())
    assert isinstance(doc, dict), f"{name} did not parse to a mapping"
    return doc


def _is_reusable(doc: dict) -> bool:
    trigger = _get_on(doc)
    if isinstance(trigger, dict | list | str):
        return "workflow_call" in trigger
    return False


def _collides_in_callers(doc: dict) -> bool:
    """Reusable workflow with a top-level group built from `github.workflow`."""
    if not _is_reusable(doc):
        return False
    concurrency = doc.get("concurrency")
    if concurrency is None:
        return False
    group = concurrency if isinstance(concurrency, str) else concurrency.get("group")
    return "github.workflow" in str(group)


def _top_level_concurrency(name: str) -> dict:
    concurrency = _load(name).get("concurrency")
    assert isinstance(concurrency, dict), f"{name} has no top-level concurrency"
    assert str(concurrency.get("group", "")).strip(), f"{name} has an empty group"
    return concurrency


def test_direct_workflows_have_concurrency_group():
    for name in ("ci.yml", "release-please.yml", "sync-main-to-development.yml"):
        _top_level_concurrency(name)


def test_release_and_sync_never_cancel():
    for name in ("release-please.yml", "sync-main-to-development.yml"):
        concurrency = _top_level_concurrency(name)
        assert concurrency["cancel-in-progress"] is False, name


def test_ci_cancels_only_pull_requests():
    """Protected-branch pushes and schedules must never be cancelled."""
    expr = str(_top_level_concurrency("ci.yml")["cancel-in-progress"])
    assert "pull_request" in expr, expr


def test_cleanup_is_job_level_only():
    doc = _load(CLEANUP)
    assert "concurrency" not in doc, "reusable workflow must not have top-level"
    concurrency = doc["jobs"]["cleanup-dev-files"].get("concurrency")
    assert isinstance(concurrency, dict), "cleanup job has no concurrency"
    assert "matrix.branch" in str(concurrency.get("group", ""))
    assert concurrency.get("cancel-in-progress") is False


def test_reusable_workflows_do_not_group_on_github_workflow():
    files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    assert files, "no workflow files found"
    offenders = [
        p.name
        for p in files
        if isinstance(doc := yaml.safe_load(p.read_text()), dict)
        and _collides_in_callers(doc)
    ]
    assert not offenders, (
        f"{offenders} are workflow_call workflows with a top-level concurrency "
        "group using github.workflow, which collides across callers"
    )


def test_classifier_detects_offending_reusable():
    doc = yaml.safe_load(
        """
        on:
          workflow_call:
        concurrency:
          group: ${{ github.workflow }}-${{ github.ref }}
        jobs: {}
        """
    )
    assert _collides_in_callers(doc)


def test_classifier_accepts_compliant_workflows():
    reusable_no_block = yaml.safe_load("on:\n  workflow_call:\njobs: {}\n")
    direct_with_block = yaml.safe_load(
        """
        on:
          push:
        concurrency:
          group: ${{ github.workflow }}-${{ github.ref }}
        jobs: {}
        """
    )
    assert not _collides_in_callers(reusable_no_block)
    assert not _collides_in_callers(direct_with_block)
