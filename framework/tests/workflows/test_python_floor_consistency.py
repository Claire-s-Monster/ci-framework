"""Tests guarding the consistency of this repo's declared Python floor.

Issue #281: `tomllib` is stdlib only from Python 3.11, and this repo imports
it in fifteen places - including two shipped composite actions
(`actions/quality-gates/action.yml`, `actions/performance-benchmark/action.yml`)
whose inline Python runs on the *consumer's* runner, not ours. Nothing
declared that floor: `[project]` had no `requires-python`, and
`[tool.pixi.dependencies]` pins `python = "3.12.*"`, so no local or CI run
ever exercises 3.10. Per #251, the `python-versions` matrix would not catch
it either, because every leg tests the same interpreter.

This repo takes option 1 from #281: declare 3.11+ and leave every
`import tomllib` bare. These tests keep the two halves consistent, in
whichever direction a future change moves them:

  - every `tomllib` site is bare **and** `requires-python` admits nothing
    below 3.11, or
  - every site carries a `tomli` fallback **and** `tomli` is in the manifest.

The failure mode #281 calls out is a *subset* fix: guarding some files and
not others leaves the framework equally broken on 3.10 while reading as
protected. When this guard was written the tree was in exactly that state -
ten bare sites and five guarded ones - so a mixed result is an explicit
failure here, not a tolerated middle ground.

Sites are discovered by walking the tree (the #255/#261-shaped guard) rather
than from a hand-written file list, so a new import in a new file is caught
rather than silently shipped.

Issue #284 widened this guard: `test_python_floor_is_declared` checked only
that `[project] requires-python` existed, but `[tool.ruff] target-version`
and `[tool.mypy] python_version` were both pinned to 3.10 regardless - one
third of "the python floor" was covered while the test's name claimed
authority over the whole thing. `test_tool_configs_track_the_declared_floor`
below now compares all three declarations against each other.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(".")
PYPROJECT = Path("pyproject.toml")

# VCS internals, the pixi environment cache, JS deps, caches, and gitignored
# agent-worktree scratch space. `templates/` is deliberately NOT excluded
# here (unlike in `test_yaml_lint_scope.py`): template files are copied into
# consumer projects, so their interpreter floor matters exactly as much as
# our own.
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pixi",
    "node_modules",
    ".claude",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
}

# File types that can carry Python source: real modules, and the inline
# `run:` Python embedded in composite actions and workflows.
SCANNED_SUFFIXES = {".py", ".yml", ".yaml"}

IMPORT_TOMLLIB_LINE_RE = re.compile(r"^[ \t]*import[ \t]+tomllib\b")
IMPORT_TOMLI_RE = re.compile(r"\bimport[ \t]+tomli\b")

# How far below a YAML-embedded `import tomllib` to look for a fallback.
# Inline `run:` Python cannot be parsed with `ast`, so those sites fall back
# to a line window; the idiom sits within a few lines when present at all.
YAML_FALLBACK_WINDOW = 8

MINIMUM_FLOOR = (3, 11)

# Samples for the classifier self-test below. The guarded one mirrors the
# real shape found in `framework/actions/quality_gates.py`: a nested `try`,
# comments between the keyword and the import, and an unaliased `import
# tomli` in the handler.
_GUARDED_SAMPLE = """
try:
    # For Python 3.11+, use tomllib
    import tomllib

    data = tomllib.loads("")
except ImportError:
    # Fallback for older Python versions
    import tomli

    data = tomli.loads("")
"""

_BARE_SAMPLE = "import tomllib\n\ndata = tomllib.loads('')\n"


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    """True for `except ImportError`, `except (ImportError, ...)`, or bare `except`."""
    if handler.type is None:
        return True
    candidates = (
        handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    )
    return any(
        isinstance(node, ast.Name) and node.id in ("ImportError", "ModuleNotFoundError")
        for node in candidates
    )


def _handler_imports_tomli(handler: ast.ExceptHandler) -> bool:
    """True when the except-branch pulls in `tomli`, aliased or not."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Import) and any(
            alias.name == "tomli" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "tomli":
            return True
    return False


def _guarded_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Line spans of every `try` body whose handler falls back to `tomli`."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(
            _catches_import_error(handler) and _handler_imports_tomli(handler)
            for handler in node.handlers
        ):
            continue
        spans = [
            (stmt.lineno, getattr(stmt, "end_lineno", None) or stmt.lineno)
            for stmt in node.body
        ]
        if spans:
            ranges.append((min(s for s, _ in spans), max(e for _, e in spans)))
    return ranges


def classify_python(label: str, text: str) -> tuple[list[str], list[str]] | None:
    """Split `import tomllib` sites in Python source into (bare, guarded).

    Returns None when the text will not parse, so the caller can fall back to
    the line-window classifier.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    ranges = _guarded_line_ranges(tree)
    bare: list[str] = []
    guarded: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        if not any(alias.name == "tomllib" for alias in node.names):
            continue
        site = f"{label}:{node.lineno}"
        inside = any(lo <= node.lineno <= hi for lo, hi in ranges)
        (guarded if inside else bare).append(site)
    return bare, guarded


def classify_text(label: str, text: str) -> tuple[list[str], list[str]]:
    """Line-window classifier for sources `ast` cannot parse (inline YAML Python)."""
    lines = text.splitlines()
    bare: list[str] = []
    guarded: list[str] = []
    for index, line in enumerate(lines):
        if not IMPORT_TOMLLIB_LINE_RE.match(line):
            continue
        window = "\n".join(lines[index : index + YAML_FALLBACK_WINDOW])
        site = f"{label}:{index + 1}"
        has_fallback = "except ImportError" in window and IMPORT_TOMLI_RE.search(window)
        (guarded if has_fallback else bare).append(site)
    return bare, guarded


def _iter_candidate_files() -> list[Path]:
    """Every file in the repo that could contain a `tomllib` import."""
    found: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        found.append(path)
    return found


def discover_tomllib_sites() -> tuple[list[str], list[str]]:
    """Walk the tree and split every `import tomllib` site into (bare, guarded)."""
    bare: list[str] = []
    guarded: list[str] = []
    for path in _iter_candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "tomllib" not in text:
            continue
        result = classify_python(str(path), text) if path.suffix == ".py" else None
        if result is None:
            result = classify_text(str(path), text)
        bare.extend(result[0])
        guarded.extend(result[1])
    return bare, guarded


def _pyproject_data() -> dict[str, Any]:
    """Parse pyproject.toml once; every other TOML-reading helper builds on this."""
    return tomllib.loads(PYPROJECT.read_text())


def declared_floor() -> str | None:
    """The `[project] requires-python` string, or None when undeclared."""
    data = _pyproject_data()
    value = data.get("project", {}).get("requires-python")
    return value if isinstance(value, str) else None


def floor_admits_below(spec: str, version: tuple[int, int]) -> bool:
    """True when `spec` permits an interpreter older than `version`.

    Only the `>=X.Y` form is understood. Anything else is reported as
    admitting older interpreters, so an unparseable floor fails loudly
    rather than passing vacuously.
    """
    match = re.match(r"^>=\s*(\d+)\.(\d+)", spec.strip())
    if match is None:
        return True
    return (int(match.group(1)), int(match.group(2))) < version


def tomli_in_manifest() -> bool:
    """True when the read-side `tomli` package is a pixi dependency.

    `tomli-w` is a writer and does not provide the `tomli` read module, so it
    deliberately does not satisfy this.
    """
    data = _pyproject_data()
    pixi = data.get("tool", {}).get("pixi", {})
    tables = [pixi.get("dependencies", {}) or {}]
    for feature in (pixi.get("feature", {}) or {}).values():
        if isinstance(feature, dict):
            tables.append(feature.get("dependencies", {}) or {})
    return any("tomli" in table for table in tables)


def _parse_requires_python_floor(spec: str) -> tuple[int, int] | None:
    """Parse the `>=X.Y` floor out of a `requires-python` string.

    Mirrors the regex `floor_admits_below` uses. Only the `>=X.Y` form is
    understood; anything else yields None rather than guessing.
    """
    match = re.match(r"^>=\s*(\d+)\.(\d+)", spec.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def requires_python_floor() -> tuple[int, int] | None:
    """The `[project] requires-python` floor as a (major, minor) tuple."""
    spec = declared_floor()
    if spec is None:
        return None
    return _parse_requires_python_floor(spec)


def _parse_ruff_target_version(value: str) -> tuple[int, int] | None:
    """Parse a ruff `target-version` string like "py311" into (3, 11).

    Accepts the `py<major><minor>` form where minor may be 1 or 2 digits
    (py39, py310, py311). Returns None when the value doesn't match that
    shape.
    """
    match = re.match(r"^py(\d)(\d{1,2})$", value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def ruff_target_version() -> tuple[int, int] | None:
    """The `[tool.ruff] target-version` floor as a (major, minor) tuple."""
    data = _pyproject_data()
    value = data.get("tool", {}).get("ruff", {}).get("target-version")
    if not isinstance(value, str):
        return None
    return _parse_ruff_target_version(value)


def _parse_mypy_python_version(value: object) -> tuple[int, int] | None:
    """Parse a mypy `python_version` value like "3.11" into (3, 11).

    TOML may hand this back as a string; only that form is handled here, so
    a non-string value (or an unparseable string) yields None.
    """
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d+)\.(\d+)$", value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def mypy_python_version() -> tuple[int, int] | None:
    """The `[tool.mypy] python_version` floor as a (major, minor) tuple."""
    data = _pyproject_data()
    value = data.get("tool", {}).get("mypy", {}).get("python_version")
    return _parse_mypy_python_version(value)


def test_classifier_detects_the_fallback_idiom():
    """Meta-guard: the classifier must actually recognise a guarded site.

    A classifier that silently labels everything 'bare' would make the
    mixed-state test below pass for free. That is not hypothetical: the
    first draft of this file used a literal-idiom regex, and it reported a
    clean bill of health against a tree that had five guarded sites in it.
    """
    bare, guarded = classify_python("<guarded-sample>", _GUARDED_SAMPLE)
    assert guarded and not bare, (
        "classifier failed to recognise the try/except ImportError fallback "
        f"idiom (bare={bare}, guarded={guarded}) - every other test in this "
        "file is vacuous until this passes"
    )

    bare, guarded = classify_python("<bare-sample>", _BARE_SAMPLE)
    assert bare and not guarded, (
        "classifier mislabelled an unguarded `import tomllib` as guarded "
        f"(bare={bare}, guarded={guarded})"
    )


def test_tomllib_site_discovery_is_not_vacuous():
    """Vacuity guard: an empty walk would pass every other test for free."""
    bare, guarded = discover_tomllib_sites()
    assert bare or guarded, (
        "no `import tomllib` sites discovered anywhere in the repo - the "
        "tree walk is broken, and the consistency tests below are vacuous"
    )


def test_python_floor_is_declared():
    """`requires-python` must state the floor the code already requires."""
    spec = declared_floor()
    assert spec is not None, (
        "[project] in pyproject.toml declares no `requires-python`, so "
        "nothing states the interpreter range this framework supports - "
        "while `import tomllib` already requires 3.11+ (#281)"
    )


def test_tool_configs_track_the_declared_floor():
    """`[tool.ruff]`, `[tool.mypy]`, and `[project] requires-python` must agree.

    #284: ruff's `target-version` and mypy's `python_version` were both
    pinned to 3.10 while `requires-python` declared 3.11+, so both tools
    checked the code against an interpreter the repo does not support -
    and 3.10 is exactly where `import tomllib` (#281) fails. The three
    values are discovered independently from the parsed TOML and compared
    against *each other*, not against a hardcoded (3, 11), so this also
    fails if the floor is raised in the future and the tool configs are
    left behind.
    """
    requires_python = requires_python_floor()
    ruff = ruff_target_version()
    mypy = mypy_python_version()
    assert requires_python is not None, "could not parse [project] requires-python"
    assert ruff is not None, "could not parse [tool.ruff] target-version"
    assert mypy is not None, "could not parse [tool.mypy] python_version"
    assert requires_python == ruff == mypy, (
        "tool configs have drifted from the declared Python floor (#284): "
        f"requires-python={requires_python}, ruff target-version={ruff}, "
        f"mypy python_version={mypy} - a tool configured below the floor "
        "checks the code against a Python version the repo does not "
        "support"
    )


def test_floor_parsers_are_not_vacuous():
    """Meta-guard: the three parsers must return the *correct* tuple, not just *a* tuple.

    A parser that returned a constant `(3, 11)` for every input would make
    `test_tool_configs_track_the_declared_floor` pass for free, the same way
    an always-'bare' classifier would make the tomllib consistency tests
    above pass for free. Each parser is fed a known-good literal (must yield
    the expected tuple) and a malformed one (must yield None).
    """
    assert _parse_requires_python_floor(">=3.11") == (3, 11)
    assert _parse_requires_python_floor(">=3.9") == (3, 9)
    assert _parse_requires_python_floor("not-a-spec") is None

    assert _parse_ruff_target_version("py311") == (3, 11)
    assert _parse_ruff_target_version("py39") == (3, 9)
    assert _parse_ruff_target_version("not-a-version") is None

    assert _parse_mypy_python_version("3.11") == (3, 11)
    assert _parse_mypy_python_version("3.9") == (3, 9)
    assert _parse_mypy_python_version(None) is None
    assert _parse_mypy_python_version("not-a-version") is None


def test_tomllib_sites_are_not_mixed():
    """Every site must be guarded the same way; a subset fix is the #281 bug."""
    bare, guarded = discover_tomllib_sites()
    assert not (bare and guarded), (
        "`tomllib` import sites are inconsistently guarded, which leaves the "
        "framework broken on 3.10 while reading as protected (#281). "
        f"guarded: {sorted(guarded)}; bare: {sorted(bare)}"
    )


def test_declared_floor_matches_tomllib_usage():
    """The declared floor and the import style must agree."""
    bare, guarded = discover_tomllib_sites()
    spec = declared_floor()
    assert spec is not None, "no `requires-python` declared (see #281)"

    if bare:
        assert not floor_admits_below(spec, MINIMUM_FLOOR), (
            f"`requires-python = {spec!r}` admits interpreters older than "
            f"{MINIMUM_FLOOR[0]}.{MINIMUM_FLOOR[1]}, but these `import "
            "tomllib` sites are bare and would raise ModuleNotFoundError "
            f"there: {sorted(bare)}"
        )
    else:
        assert tomli_in_manifest(), (
            "every `import tomllib` site carries a `tomli` fallback, but "
            "`tomli` is not a pixi dependency, so the fallback import fails "
            "at runtime (`tomli-w` is a writer and does not provide it)"
        )
