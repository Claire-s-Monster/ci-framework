"""Guards against `uses: ./actions/<name>` refs in templates/ pointing nowhere.

Files under `templates/` are scaffolding shipped into consumer projects. When
a step in one references `./actions/<name>`, that path is meant to mirror
this repo's own `actions/` tree, so it must resolve to a real action
directory here - not just look plausible. A renamed, moved, or deleted
action directory silently breaks every template that still references the
old name, and nothing short of manually copying a template out and running
it would otherwise catch that.

This guard is data-driven: it walks every `*.yml`/`*.yaml` file under
`templates/` (recursively) and every `uses:` value found anywhere in it,
rather than hardcoding which templates or actions exist. A hand-maintained
list is exactly the kind of thing that goes stale (#255, #261).
"""

from __future__ import annotations

from pathlib import Path

import yaml

TEMPLATES_DIR = Path("templates")
ACTIONS_DIR = Path("actions")
ACTION_MANIFEST_NAMES = ("action.yml", "action.yaml")
LOCAL_ACTION_PREFIX = "./actions/"


def _template_files() -> list[Path]:
    return sorted(TEMPLATES_DIR.rglob("*.yml")) + sorted(TEMPLATES_DIR.rglob("*.yaml"))


def _iter_uses_values(node):
    """Recursively yield every `uses:` value found anywhere in the document.

    A step's `uses:` can appear at any depth under `jobs.<id>.steps[]`, and
    this walks the whole parsed document rather than assuming a fixed shape,
    so it also naturally ignores the YAML 1.1 quirk where an unquoted `on:`
    key parses as the boolean `True` - that key is just another dict entry
    to recurse into, never a `uses:` value itself.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from _iter_uses_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses_values(item)


def _safe_load(path: Path):
    """Parse a template file as YAML, tolerating files that aren't standalone YAML.

    Some templates under templates/ carry Jinja2 placeholders (e.g.
    `{{ python_pr_limit | default(5) }}` in dependabot.yml) that only become
    valid YAML after template rendering. This mirrors the `.yml.template`
    exclusion documented in pixi_meta.py's `shipped_workflow_files`: such a
    file is scaffolding, not standalone parseable YAML, in its committed
    form. A file that fails to parse here is excluded from this pass rather
    than crashing it - raw templated text can't be a GitHub Actions workflow
    with resolvable `./actions/` refs anyway, so there is nothing to check.
    """
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return None


def _local_action_refs(doc) -> list[str]:
    """Every `./actions/`-relative `uses:` value in a parsed document."""
    if not isinstance(doc, dict):
        return []
    return [
        uses for uses in _iter_uses_values(doc) if uses.startswith(LOCAL_ACTION_PREFIX)
    ]


def _has_action_manifest(directory: Path) -> bool:
    return directory.is_dir() and any(
        (directory / name).is_file() for name in ACTION_MANIFEST_NAMES
    )


def _existing_action_names() -> list[str]:
    """Names of directories under actions/ that have an action.yml manifest."""
    if not ACTIONS_DIR.is_dir():
        return []
    return sorted(d.name for d in ACTIONS_DIR.iterdir() if _has_action_manifest(d))


def _resolve_ref_dir(uses: str) -> Path:
    """Resolve a `./actions/<name>[/...]` uses: value to its action directory.

    A `uses:` value may point deeper than the action root (e.g.
    `./actions/foo/subdir`), but the action itself always lives at
    `./actions/<name>`, so only the first segment after the prefix matters.
    Built via string splitting rather than `Path(uses).parts` since pathlib
    silently normalizes away a leading `./` and that normalization is not
    something this helper wants to depend on.
    """
    remainder = uses[len("./") :]  # 'actions/<name>/...'
    name = remainder.split("/")[1]
    return ACTIONS_DIR / name


def test_template_local_action_refs_resolve():
    """Every `./actions/<name>` uses: in templates/ must resolve to a real action.

    Reports every violation at once - file, the referenced path, and the
    action directories that actually exist - rather than stopping at the
    first, since more than one template or ref can be broken simultaneously.
    """
    existing = _existing_action_names()
    violations = []
    for path in _template_files():
        doc = _safe_load(path)
        for uses in _local_action_refs(doc):
            ref_dir = _resolve_ref_dir(uses)
            if not _has_action_manifest(ref_dir):
                violations.append((str(path), uses))

    assert not violations, (
        "template(s) reference ./actions/<name> directories that do not "
        f"exist or lack an action.yml/action.yaml manifest: {violations}. "
        f"Action directories that DO exist: {existing}."
    )


def test_guard_is_not_vacuous():
    """The walk must cover real template files and find at least one ./actions/ ref."""
    files = _template_files()
    assert files, (
        f"expected at least one template file, found none under {TEMPLATES_DIR}"
    )

    refs_found = any(_local_action_refs(_safe_load(path)) for path in files)
    assert refs_found, (
        "no template references any ./actions/ path - the guard would "
        "silently check nothing"
    )


def test_guard_detects_a_missing_action_directory():
    """Self-test: a constructed document referencing a nonexistent action is flagged.

    Proves the helpers actually fire on a bad ref, not just that the
    parametrization touches real files - a bug in `_iter_uses_values` or
    `_resolve_ref_dir` (e.g. mishandling the `on:` -> `True` key quirk, or
    off-by-one segment splitting) could otherwise leave every real-file check
    silently passing. Built via `yaml.safe_load` on real YAML text, the same
    parsing path real template files take.
    """
    doc = yaml.safe_load(
        """
        on:
          push:
        jobs:
          build:
            steps:
              - uses: ./actions/definitely-does-not-exist
        """
    )

    refs = _local_action_refs(doc)
    assert refs == ["./actions/definitely-does-not-exist"], (
        f"expected the ./actions/ uses: to be picked up as a ref, got {refs}"
    )

    ref_dir = _resolve_ref_dir(refs[0])
    assert not _has_action_manifest(ref_dir), (
        "self-test action name unexpectedly exists on disk with a manifest - "
        "pick a name guaranteed not to collide"
    )


def test_guard_does_not_over_fire_on_a_real_action_directory():
    """Self-test: a constructed document referencing a real action is NOT flagged.

    Mirrors `test_guard_does_not_over_fire_on_non_reusable_relative_uses` in
    the sibling reusable-workflow guard: without this, a guard that flags
    every ./actions/ ref regardless of whether it resolves would look correct
    but reject legitimate templates too.
    """
    existing = _existing_action_names()
    assert existing, "expected at least one real action directory under actions/"
    real_name = existing[0]

    doc = yaml.safe_load(
        f"""
        on:
          push:
        jobs:
          build:
            steps:
              - uses: ./actions/{real_name}
        """
    )

    refs = _local_action_refs(doc)
    assert refs == [f"./actions/{real_name}"]

    ref_dir = _resolve_ref_dir(refs[0])
    assert _has_action_manifest(ref_dir), (
        f"real action directory {ref_dir} was not recognized as valid - "
        "the guard would over-fire on legitimate refs"
    )
