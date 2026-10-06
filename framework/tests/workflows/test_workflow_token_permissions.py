"""Guard: no workflow grants a penalised write scope at its top level.

Issue #359. OpenSSF Scorecard's Token-Permissions check penalises a workflow
whose top-level `permissions:` block grants write on a sensitive scope, or has
no top-level block at all (the default token may then be read-write). The fix
is a non-write top level (`contents: read`) with writes scoped to the jobs that
need them.

Reusable (`workflow_call`) workflows are the exception. A consumer probe proved
that a top-level `permissions:` block in a workflow_call workflow REPLACES the
caller's grant for every job that has no block of its own, so adding one would
silently strip SARIF uploads, git push and pypi publish from callers:
https://github.com/Claire-s-Monster/ci-framework/issues/359#issuecomment-6002017040
Those workflows therefore stay WITHOUT a top-level block, and
INHERIT_EXEMPT_WORKFLOWS pins that set exactly so a stale exemption fails.

Walk-the-tree guards can pass vacuously, hence the non-vacuity floor and the
classifier self-tests, which exercise the exact function the real test uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Scorecard's Token-Permissions does not penalise top-level pages, issues,
# pull-requests or id-token writes, so those are deliberately absent here.
PENALISED_WRITE_SCOPES = frozenset(
    {
        "contents",
        "actions",
        "checks",
        "deployments",
        "packages",
        "security-events",
        "statuses",
    }
)

# workflow_call workflows that must have NO top-level `permissions:` block: one
# would replace the caller's grant for every inheriting job (SARIF uploads, git
# push, pypi publish). Probe:
# https://github.com/Claire-s-Monster/ci-framework/issues/359#issuecomment-6002017040
INHERIT_EXEMPT_WORKFLOWS = frozenset(
    {
        "reusable-ci.yml",
        "reusable-code-policy.yml",
        "reusable-quality.yml",
        "reusable-release.yml",
        "reusable-security.yml",
        "self-healing.yml",
    }
)


def workflow_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml` and `*.yaml` directly under `directory` (flat, like GitHub)."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def load_workflow(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}


def triggers(workflow: dict) -> set[str]:
    """Event names in `on:`; PyYAML parses the bare key `on` as boolean True."""
    if True in workflow:
        on = workflow[True]
    else:
        on = workflow.get("on")
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(event) for event in on}
    if isinstance(on, dict):
        return {str(event) for event in on}
    return set()


def top_level_permission_violation(workflow: dict) -> str | None:
    """None if the top-level `permissions:` is acceptable, else the reason."""
    if "permissions" not in workflow:
        return "no top-level permissions"
    perms = workflow["permissions"]
    if isinstance(perms, str):
        if perms == "read-all":
            return None
        if perms == "write-all":
            return "top-level permissions is write-all"
        return f"unrecognised top-level permissions value {perms!r}"
    if not perms:
        return None
    if isinstance(perms, dict):
        written = sorted(
            scope
            for scope, level in perms.items()
            if scope in PENALISED_WRITE_SCOPES and level == "write"
        )
        if written:
            return "top-level write on " + ", ".join(written)
        return None
    return f"unrecognised top-level permissions value {perms!r}"


# --- Real-tree tests ---------------------------------------------------------


def test_walker_is_not_vacuous():
    names = {path.name for path in workflow_files()}
    required = {"ci.yml", "branch-policy.yml", "reusable-ci.yml", "self-healing.yml"}
    assert names, "walk found no workflow files"
    assert required <= names, f"walk is missing {sorted(required - names)}"


def test_every_non_exempt_workflow_has_a_non_write_top_level():
    failures = []
    for path in workflow_files():
        if path.name in INHERIT_EXEMPT_WORKFLOWS:
            continue
        reason = top_level_permission_violation(load_workflow(path))
        if reason:
            failures.append(f"{path.name}: {reason}")
    assert not failures, "\n".join(failures)


def test_inherit_exemptions_are_exact():
    for name in sorted(INHERIT_EXEMPT_WORKFLOWS):
        path = WORKFLOWS_DIR / name
        assert path.is_file(), f"{name}: exempt workflow does not exist"
        doc = load_workflow(path)
        assert triggers(doc) == {"workflow_call"}, (
            f"{name}: exempt but triggers are {sorted(triggers(doc))}"
        )
        assert "permissions" not in doc, (
            f"{name}: stale exemption, it has a top-level permissions block"
        )
    actual = set()
    for path in workflow_files():
        doc = load_workflow(path)
        if triggers(doc) == {"workflow_call"} and "permissions" not in doc:
            actual.add(path.name)
    assert actual == INHERIT_EXEMPT_WORKFLOWS, (
        f"workflow_call-only workflows without a top-level block: {sorted(actual)}; "
        f"exemptions: {sorted(INHERIT_EXEMPT_WORKFLOWS)}"
    )


# --- Classifier self-tests (guard against a vacuously passing walk) ----------


@pytest.mark.parametrize(
    ("workflow", "violates"),
    [
        ({}, True),
        ({"permissions": "read-all"}, False),
        ({"permissions": "write-all"}, True),
        ({"permissions": "something-else"}, True),
        ({"permissions": {}}, False),
        ({"permissions": None}, False),
        ({"permissions": {"contents": "read"}}, False),
        ({"permissions": {"contents": "write"}}, True),
        ({"permissions": {"security-events": "write"}}, True),
        # `id-token` is a scope name that trips detect-secrets' keyword heuristic.
        # pragma: allowlist nextline secret
        ({"permissions": {"pages": "write", "id-token": "write"}}, False),
        ({"permissions": {"issues": "write", "pull-requests": "write"}}, False),
        ({"permissions": {"contents": "read", "statuses": "write"}}, True),
        # The ORIGINAL auto-merge-release.yml top-level block.
        ({"permissions": {"contents": "write", "pull-requests": "write"}}, True),
    ],
)
def test_classifier_self_test(workflow, violates):
    assert (top_level_permission_violation(workflow) is not None) is violates


@pytest.mark.parametrize(
    ("workflow", "expected"),
    [
        ({True: {"workflow_call": None}}, {"workflow_call"}),
        ({"on": {"push": None, "workflow_call": None}}, {"push", "workflow_call"}),
        ({True: "pull_request"}, {"pull_request"}),
        ({True: ["push", "schedule"]}, {"push", "schedule"}),
        ({}, set()),
    ],
)
def test_triggers_self_test(workflow, expected):
    assert triggers(workflow) == expected
