"""Release-please must be able to bump every `x-release-please-version` ref.

Workflows pin this repo's own reusable workflows and actions at `@vX.Y.Z` and
tag the line with `# x-release-please-version` so release-please's generic
updater rewrites it on release. Release PR #364 bumped none of them because
release-please.yml passed `release-type: python` as an action input, and the
action ignores config-file and manifest-file whenever release-type is set
(#390). That dropped `extra-files` and `changelog-sections` silently.

The guard walks every YAML file under .github/ and actions/ for the marker
instead of using a hand-maintained list, checks each ref against the manifest
version, and keeps a floor on refs found (plus a regex self-test) so it
cannot pass vacuously.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

ROOTS = (Path(".github"), Path("actions"))
CONFIG = Path(".release-please-config.json")
MANIFEST = Path(".release-please-manifest.json")
WORKFLOW = Path(".github/workflows/release-please.yml")
MARKER = "x-release-please-version"
MIN_MARKED_REFS = 5
REF_RE = re.compile(r"uses:\s*\S+@v(\d+\.\d+\.\d+)\s+#\s*x-release-please-version")


def _marker_lines() -> list[tuple[Path, int, str]]:
    found = []
    for root in ROOTS:
        for path in sorted([*root.rglob("*.yml"), *root.rglob("*.yaml")]):
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), start=1):
                if MARKER in line:
                    found.append((path, number, line))
    return found


def _ref_lines() -> list[tuple[Path, int, str]]:
    """Return (path, line number, pinned version) for every marked ref."""
    refs = []
    for path, number, line in _marker_lines():
        match = REF_RE.search(line)
        if match:
            refs.append((path, number, match.group(1)))
    return refs


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "        uses: Claire-s-Monster/ci-framework/actions/x@v4.0.0  "
            "# x-release-please-version",
            True,
        ),
        ("        uses: owner/repo/actions/x@v4.0.0", False),
        ("        uses: owner/repo/actions/x@v4  # x-release-please-version", False),
        ("        uses: owner/repo/actions/x@main  # x-release-please-version", False),
    ],
)
def test_ref_regex_self_test(line: str, expected: bool) -> None:
    assert bool(REF_RE.search(line)) is expected


def test_marker_walk_is_not_vacuous() -> None:
    refs = _ref_lines()
    assert len(refs) >= MIN_MARKED_REFS, (
        f"found {len(refs)} marked refs, expected >= {MIN_MARKED_REFS}"
    )


def test_marked_refs_match_manifest() -> None:
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["."]
    stale = [
        f"{p}:{n} pins v{pinned}, manifest is {version}"
        for p, n, pinned in _ref_lines()
        if pinned != version
    ]
    assert not stale, "marked refs out of step with manifest:\n" + "\n".join(stale)


def test_marker_lines_are_refs_or_comments() -> None:
    bad = [
        f"{p}:{n}: {line.strip()}"
        for p, n, line in _marker_lines()
        if not REF_RE.search(line) and not line.strip().startswith("#")
    ]
    assert not bad, "marker on a line the updater cannot handle:\n" + "\n".join(bad)


def test_marked_files_are_extra_files() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    extra = {entry["path"] for entry in config["extra-files"]}
    marked = {p.as_posix() for p, _, _ in _ref_lines()}
    missing = sorted(marked - extra)
    assert not missing, f"files with marked refs not in extra-files: {missing}"


def test_release_please_step_honours_config_file() -> None:
    """#390: release-type as an input makes the action ignore config-file."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).startswith("googleapis/release-please-action")
    ]
    assert steps, "no release-please-action step found"
    for step in steps:
        inputs = step.get("with", {})
        assert "config-file" in inputs, "config-file input missing (#390)"
        assert "manifest-file" in inputs, "manifest-file input missing (#390)"
        assert "release-type" not in inputs, (
            "release-type input makes release-please-action ignore config-file, "
            "dropping extra-files and changelog-sections (#390)"
        )
