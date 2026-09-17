"""Guard: `[tool.pixi.project]` is deprecated in favour of `[tool.pixi.workspace]`.

Pixi deprecated the `[tool.pixi.project]` table in favour of
`[tool.pixi.workspace]` (same keys: name, version, channels, platforms, ...).
This repo's own declarations and docs must use the new table; only code that
READS a *consumer's* pixi config may still accept the legacy form, because
consumers may not have migrated yet (see `framework/actions/quality_gates.py`,
`scripts/local-ci/package-detection.py`, `scripts/generate_compatibility_report.py`).

This guard walks `pyproject.toml`, `templates/**/*`, `README.md`, and
`docs/**/*.md` for the literal `[tool.pixi.project]` table header and fails,
listing every file:line, if any survive. It deliberately does NOT walk
`framework/tests/` — several test files there use `[tool.pixi.project]` on
purpose as legacy-form fixtures.

The walk is programmatic (`pathlib.rglob`), not a hand-written file list, so
a new doc or template picking up the deprecated table is caught rather than
silently shipped.
"""

from __future__ import annotations

import re
from pathlib import Path

# Same depth as the sibling `test_sarif_upload_auth.py` guard in this
# directory: framework/tests/workflows/<this file> -> repo root is 3 parents up.
REPO_ROOT = Path(__file__).resolve().parents[3]

LEGACY_PIXI_PROJECT_PATTERN = re.compile(r"\[tool\.pixi\.project\]")
WORKSPACE_PIXI_PATTERN = re.compile(r"\[tool\.pixi\.workspace\]")


def _corpus_paths() -> list[Path]:
    """First-party files consumers copy or read as authoritative examples."""
    paths = [REPO_ROOT / "pyproject.toml", REPO_ROOT / "README.md"]
    templates_dir = REPO_ROOT / "templates"
    if templates_dir.is_dir():
        paths.extend(sorted(p for p in templates_dir.rglob("*") if p.is_file()))
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.is_dir():
        paths.extend(sorted(docs_dir.rglob("*.md")))
    return paths


def _matches(path: Path, pattern: re.Pattern[str]) -> list[int]:
    """1-based line numbers in `path` where `pattern` is found."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [i + 1 for i, line in enumerate(text.splitlines()) if pattern.search(line)]


CORPUS_PATHS = _corpus_paths()


def test_classifier_flags_legacy_table_only(tmp_path: Path) -> None:
    """Self-test: the matcher flags `[tool.pixi.project]` only, not
    `[tool.pixi.workspace]` or the unrelated PEP 621 `[project]` table."""
    sample = tmp_path / "sample.toml"
    sample.write_text(
        "[project]\n"
        "name = 'x'\n"
        "[tool.pixi.project]\n"
        "name = 'x'\n"
        "[tool.pixi.workspace]\n"
        "name = 'y'\n"
    )

    assert _matches(sample, LEGACY_PIXI_PROJECT_PATTERN) == [3]
    assert _matches(sample, WORKSPACE_PIXI_PATTERN) == [5]


def test_corpus_walk_is_not_vacuous() -> None:
    """A broken/empty walk must not make the guard below pass silently."""
    assert REPO_ROOT / "pyproject.toml" in CORPUS_PATHS

    docs_dir = REPO_ROOT / "docs"
    docs_hits = [p for p in CORPUS_PATHS if docs_dir in p.parents]
    assert docs_hits, "expected at least one docs/**/*.md file in the corpus"

    workspace_hits = [
        f"{path.relative_to(REPO_ROOT)}:{line}"
        for path in CORPUS_PATHS
        for line in _matches(path, WORKSPACE_PIXI_PATTERN)
    ]
    assert workspace_hits, (
        "expected `[tool.pixi.workspace]` to appear at least once in the "
        "corpus; if it doesn't, the walk itself is broken"
    )


def test_no_legacy_pixi_project_table_in_first_party_corpus() -> None:
    """pyproject.toml, templates/, README.md, and docs/ must all declare
    `[tool.pixi.workspace]`, never the deprecated `[tool.pixi.project]`."""
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line}"
        for path in CORPUS_PATHS
        for line in _matches(path, LEGACY_PIXI_PROJECT_PATTERN)
    ]
    assert not offenders, (
        "found deprecated `[tool.pixi.project]` table(s); pixi replaced this "
        "with `[tool.pixi.workspace]` (same keys):\n" + "\n".join(offenders)
    )
