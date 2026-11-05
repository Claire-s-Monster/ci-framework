"""Guards against running the repo cleanup twice per push.

cleanup-caller-example.yml (which calls cleanup-dev-files.yml@main) and
cleanup-dev-files.yml's own push trigger both fired on every push, and the
caller ran MAIN's copy on development pushes. After the release PR merged,
main's copy pinned an action at a tag that did not exist yet (runs #668,
#669, #703). Exactly one workflow in this repo may run cleanup on `push`.

The guard walks every workflow file instead of hardcoding names, and has a
classifier self-test so it can prove it is able to fail.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(".github/workflows")
CLEANUP = "cleanup-dev-files.yml"
CALLER = WORKFLOWS_DIR / "cleanup-caller-example.yml"


def _get_on(doc: dict):
    """Return the `on:` mapping; PyYAML parses an unquoted `on:` as `True`."""
    if "on" in doc:
        return doc["on"]
    return doc.get(True, {})


def _triggers_on_push(doc: dict) -> bool:
    trigger = _get_on(doc)
    if isinstance(trigger, dict | list | str):
        return "push" in trigger
    return False


def _runs_cleanup(name: str, doc: dict) -> bool:
    if name == CLEANUP:
        return True
    jobs = doc.get("jobs") or {}
    return any(
        isinstance(job, dict) and CLEANUP in str(job.get("uses", ""))
        for job in jobs.values()
    )


def _is_push_cleanup(name: str, doc: dict) -> bool:
    """Workflow runs cleanup on push: push trigger AND cleanup itself/caller."""
    return _triggers_on_push(doc) and _runs_cleanup(name, doc)


def _load(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text())
    assert isinstance(doc, dict), f"{path} did not parse to a mapping"
    return doc


def _push_cleanup_workflows() -> list[str]:
    files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    return [
        p.name
        for p in files
        if isinstance(doc := yaml.safe_load(p.read_text()), dict)
        and _is_push_cleanup(p.name, doc)
    ]


def test_exactly_one_workflow_runs_cleanup_on_push():
    """Only cleanup-dev-files.yml may run cleanup on push (runs #668/#669)."""
    found = _push_cleanup_workflows()
    assert found == [CLEANUP], (
        f"expected exactly [{CLEANUP!r}] to run cleanup on push, got {found}. "
        "A caller with a push trigger double-runs cleanup and, pinned @main, "
        "runs main's copy on development pushes."
    )


def test_classifier_counts_push_caller():
    """Self-test: a synthetic push-triggered caller must be counted."""
    doc = yaml.safe_load(
        """
        on:
          push:
            branches: [main]
        jobs:
          cleanup:
            uses: Claire-s-Monster/ci-framework/.github/workflows/cleanup-dev-files.yml@main
        """
    )
    assert _is_push_cleanup("some-caller.yml", doc)


def test_classifier_ignores_non_push_caller():
    """Self-test: a dispatch-only caller must not be counted."""
    doc = yaml.safe_load(
        """
        on:
          workflow_dispatch:
        jobs:
          cleanup:
            uses: Claire-s-Monster/ci-framework/.github/workflows/cleanup-dev-files.yml@main
        """
    )
    assert not _is_push_cleanup("some-caller.yml", doc)


def test_release_commit_skip_condition():
    """The cleanup job must skip this repo's release commit (run #703).

    The release commit bumps self-pinned refs before release-please creates
    the tag, so the job cannot resolve its own actions.
    """
    doc = _load(WORKFLOWS_DIR / CLEANUP)
    condition = str(doc["jobs"]["cleanup-dev-files"].get("if", ""))
    for needle in (
        "chore(main): release",
        "head_commit.message",
        "Claire-s-Monster/ci-framework",
    ):
        assert needle in condition, f"job `if:` is missing {needle!r}: {condition!r}"


def test_caller_example_stays_a_valid_template():
    """The example keeps workflow_dispatch and still calls the reusable workflow."""
    doc = _load(CALLER)
    assert "workflow_dispatch" in _get_on(doc)
    assert _runs_cleanup(CALLER.name, doc)
