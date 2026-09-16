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

Issue #286 widened this file again: `discover_version_declarations` walks
three corpora - every `*.toml` at the repo root and under `templates/`,
every `.github/workflows/*.yml` and `*.yml.template`, and the literal
`py3XX` / `>=3.Y` defaults `framework/migration/migrator.py` emits into
migrated projects - and checks every Python-version declaration found there
against the `[project] requires-python` floor. It deliberately EXCLUDES
`docs/` and `README.md` (~70 sites still pinned to 3.10 at the time this
was written): those are fixed in a separate PR (#286 PR-C), and including
them here would fail this guard until that PR lands. Doc drift is
therefore NOT currently guarded by this file.

Issue #286 PR-B added a fourth corpus: `discover_framework_version_declarations`
walks every `*.py` under `framework/` for version-spec literals (`py3XX`,
`>=3.Y`/`^3.Y`/`~=3.Y`, `3.Y.*`, version-string list literals) and
`sys.version_info >= (3, N)`-shaped comparisons, checked against the same
declared floor. Sites that are deliberately below the floor - consumer-project
fixtures, and this file's own classifier self-test samples - carry an
in-place `# python-floor-exempt: <reason>` (or, for a whole file that is
entirely such fixtures, a module-level `# python-floor-exempt-module:
<reason>`) rather than being tracked in a central list, for the same reason
`EXCLUDED_DIR_NAMES` above stays short: a hand-maintained inventory of exempt
sites is the exact artefact #250/#255/#261/#286 keep going stale on. A bare
version string with no spec syntax around it (`"3.10"` as a dict key, say) is
out of scope for this corpus - see the corpus's own docstring below.

Issue #286 PR-C added a fifth corpus: `discover_docs_version_declarations`
walks `docs/**/*.md`, the repo-root `README.md`, `examples/**/*.yml`|`.yaml`,
and shipped composite-action READMEs (`actions/*/README.md`,
`.github/actions/*/README.md`) - the two corpora the #286 paragraph above
named as still excluded. Markdown mixes structured config with running
prose, so this corpus classifies each line as structured (inside a ```
fence or an inline `code span`, matched against the same quoted/structured
shapes the other corpora use) or prose (a bare `X.Y` token in running
text), and both modes drop a match whose line/sentence reads as
non-support ("not supported", "no longer", "dropped", "unsupported",
"removed", "fail(s)", "ModuleNotFoundError", "must pass an explicit") -
see `discover_docs_version_declarations`'s own docstring for the full
contract. `#`-comments do not work in Markdown, so the per-site exemption
marker is `<!-- python-floor-exempt: <reason> -->` instead of the `#
python-floor-exempt: <reason>` used elsewhere in this file.
"""

# python-floor-exempt-module: this file's samples are classifier self-test
# input; they must spell out sub-floor versions to prove the walk catches them.

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


# All three `_parse_*` helpers below take `value: object` rather than `str`.
# TOML can hand back a non-string for these keys - `python_version = 3.11`
# written *without* quotes parses as a float, not a string - so each parser
# is a total function over whatever TOML yields, and a non-string fails
# loudly via the wrapper's `is not None` assertion rather than raising
# TypeError deep inside a regex match.


def _parse_requires_python_floor(value: object) -> tuple[int, int] | None:
    """Parse the `>=X.Y` floor out of a `requires-python` value.

    Mirrors the regex `floor_admits_below` uses. Only the `>=X.Y` form is
    understood; anything else (including a non-string value) yields None
    rather than guessing.
    """
    if not isinstance(value, str):
        return None
    match = re.match(r"^>=\s*(\d+)\.(\d+)", value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def requires_python_floor() -> tuple[int, int] | None:
    """The `[project] requires-python` floor as a (major, minor) tuple."""
    spec = declared_floor()
    if spec is None:
        return None
    return _parse_requires_python_floor(spec)


def _parse_ruff_target_version(value: object) -> tuple[int, int] | None:
    """Parse a ruff `target-version` value like "py311" into (3, 11).

    Accepts the `py<major><minor>` form where minor may be 1 or 2 digits
    (py39, py310, py311). Returns None when the value doesn't match that
    shape, or isn't a string at all.
    """
    if not isinstance(value, str):
        return None
    match = re.match(r"^py(\d)(\d{1,2})$", value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def ruff_target_version() -> tuple[int, int] | None:
    """The `[tool.ruff] target-version` floor as a (major, minor) tuple."""
    data = _pyproject_data()
    value = data.get("tool", {}).get("ruff", {}).get("target-version")
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
    # No `$` anchor in the regex: it matches the `>=X.Y` prefix and ignores
    # whatever follows, so comma-separated upper bounds are understood too.
    assert _parse_requires_python_floor(">=3.11,<4.0") == (3, 11)
    assert _parse_requires_python_floor(">=3.11, <4.0") == (3, 11)
    # Deliberate: an exact pin is not the `>=X.Y` form the guard reasons
    # about, so it fails loudly via the "could not parse" assertion instead
    # of being silently guessed at - mirrors `floor_admits_below`'s contract.
    assert _parse_requires_python_floor("==3.11") is None
    assert _parse_requires_python_floor(None) is None
    assert _parse_requires_python_floor(3.11) is None

    assert _parse_ruff_target_version("py311") == (3, 11)
    assert _parse_ruff_target_version("py39") == (3, 9)
    assert _parse_ruff_target_version("not-a-version") is None
    assert _parse_ruff_target_version(None) is None
    assert _parse_ruff_target_version(3.11) is None

    assert _parse_mypy_python_version("3.11") == (3, 11)
    assert _parse_mypy_python_version("3.9") == (3, 9)
    assert _parse_mypy_python_version(None) is None
    assert _parse_mypy_python_version("not-a-version") is None
    assert _parse_mypy_python_version(3.11) is None


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


# ============================================================================
# #286: version-declaration discovery across TOML / workflow / migrator /
# framework / docs corpora. See the module docstring for each corpus's scope.
# ============================================================================

DeclarationRecord = tuple[Path, str, str, tuple[int, int] | None]

TEMPLATES_DIR = REPO_ROOT / "templates"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
MIGRATOR_PATH = REPO_ROOT / "framework" / "migration" / "migrator.py"

# Any "X.Y" pair, used to pull a floor out of loosely-formatted specs
# (pixi's `python = ">=3.11"` / `"3.12.*"`, workflow matrix arrays) that
# don't follow one single fixed grammar.
VERSION_TOKEN_RE = re.compile(r"(\d+)\.(\d+)")
JSON_ARRAY_RE = re.compile(r"\[[^\]]*\]")

# Matches a `python-version`/`python-versions` key whether written as a YAML
# `key: value` pair or a shell `key=value` assignment (the standalone-ci.yml
# `echo 'python-versions=[...]'` idiom), with or without a leading `#`
# (the reusable-ci.yml usage-example comment). Not anchored to line start so
# it also matches inside a quoted shell string.
VERSION_KEY_RE = re.compile(r"['\"]?(python-versions?)['\"]?\s*[:=]\s*(.*)$")

# How far below a bare `python-versions:` key to look for its `default:`
# entry in a `workflow_call` input block (key and value live on separate
# lines when the key also carries a multi-line `description: >-`). Mirrors
# the `YAML_FALLBACK_WINDOW` idiom above.
WORKFLOW_LOOKAHEAD_WINDOW = 10
DEFAULT_VALUE_RE = re.compile(r"default:\s*['\"]?(\[[^\]\n]*\])")

# `framework/migration/migrator.py` literals: quote-agnostic so either
# quote style is caught, using a backreference to match the same quote on
# both sides.
PY3_LITERAL_RE = re.compile(r"""(['"])(py3\d+)\1""")
GTE_LITERAL_RE = re.compile(r"""(['"])(>=3\.\d+)\1""")


def _parse_version_floor_loose(value: object) -> tuple[int, int] | None:
    """Extract the lowest `(major, minor)` token from a loosely-formatted spec.

    Handles forms `_parse_requires_python_floor`/`_parse_mypy_python_version`
    don't: pixi's `">=3.11"` or `"3.12.*"`, and a Jinja-templated default
    embedding a concrete fallback (`"{{ python_version | default('3.12.*')
    }}"` - the template's own `[tool.pixi.dependencies]` value). Every `X.Y`
    token in the string is a candidate; the minimum is treated as the floor,
    matching the policy applied to workflow matrix arrays below. Returns
    None when the value carries no version token at all, rather than
    guessing.
    """
    if not isinstance(value, str):
        return None
    matches = [
        (int(major), int(minor)) for major, minor in VERSION_TOKEN_RE.findall(value)
    ]
    return min(matches) if matches else None


def _iter_toml_candidate_files() -> list[Path]:
    """Every `*.toml` at the repo root (non-recursive) and under `templates/`."""
    root_files = [path for path in REPO_ROOT.glob("*.toml") if path.is_file()]
    template_files = (
        list(TEMPLATES_DIR.rglob("*.toml")) if TEMPLATES_DIR.is_dir() else []
    )
    return root_files + template_files


def discover_toml_version_declarations() -> list[DeclarationRecord]:
    """`[tool.ruff] target-version`, `[tool.mypy] python_version`, and
    `[tool.pixi.dependencies] python`, across every `*.toml` at the repo
    root and under `templates/` (templates ship into consumer projects, so
    their floor matters exactly as much as our own)."""
    records: list[DeclarationRecord] = []
    for path in _iter_toml_candidate_files():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
            continue
        tool = data.get("tool", {})
        ruff_value = tool.get("ruff", {}).get("target-version")
        if ruff_value is not None:
            records.append(
                (
                    path,
                    "toml-ruff-target-version",
                    str(ruff_value),
                    _parse_ruff_target_version(ruff_value),
                )
            )
        mypy_value = tool.get("mypy", {}).get("python_version")
        if mypy_value is not None:
            records.append(
                (
                    path,
                    "toml-mypy-python-version",
                    str(mypy_value),
                    _parse_mypy_python_version(mypy_value),
                )
            )
        pixi_value = tool.get("pixi", {}).get("dependencies", {}).get("python")
        if pixi_value is not None:
            records.append(
                (
                    path,
                    "toml-pixi-python",
                    str(pixi_value),
                    _parse_version_floor_loose(pixi_value),
                )
            )
    return records


def _extract_array_versions(fragment: str) -> list[tuple[int, int]] | None:
    """Pull `[..., ...]` version tokens out of `fragment`, or None if no array is present.

    None (not an empty list) distinguishes "this value isn't an array at
    all" (a scalar default, or a `${{ expression }}` reference) from "an
    array with nothing recognisable in it", so a caller can tell the two
    apart.
    """
    array_match = JSON_ARRAY_RE.search(fragment)
    if array_match is None:
        return None
    return [
        (int(major), int(minor))
        for major, minor in VERSION_TOKEN_RE.findall(array_match.group(0))
    ]


def _iter_workflow_candidate_files() -> list[Path]:
    """Every `*.yml` and `*.yml.template` under `.github/workflows/`."""
    if not WORKFLOWS_DIR.is_dir():
        return []
    return sorted(
        set(WORKFLOWS_DIR.glob("*.yml")) | set(WORKFLOWS_DIR.glob("*.yml.template"))
    )


def discover_workflow_version_declarations() -> list[DeclarationRecord]:
    """`python-version`/`python-versions` matrix values under `.github/workflows/`.

    Only JSON-array-string or YAML-list values count: a scalar default like
    `python-version: '3.12'` or a reference like `${{ matrix.python-version
    }}` is not a floor declaration and is skipped. For a `workflow_call`
    input whose key and `default:` live on separate lines, the default is
    found by looking a few lines below the bare key.
    """
    records: list[DeclarationRecord] = []
    for path in _iter_workflow_candidate_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines):
            match = VERSION_KEY_RE.search(line)
            if match is None:
                continue
            rest = match.group(2).strip()
            if rest:
                raw = rest
                versions = _extract_array_versions(rest)
            else:
                window = "\n".join(
                    lines[index + 1 : index + 1 + WORKFLOW_LOOKAHEAD_WINDOW]
                )
                default_match = DEFAULT_VALUE_RE.search(window)
                raw = default_match.group(1) if default_match else ""
                versions = _extract_array_versions(raw) if default_match else None
            if not versions:
                continue
            records.append((path, "workflow-python-version-min", raw, min(versions)))
    return records


def discover_migrator_version_declarations() -> list[DeclarationRecord]:
    """`py3\\d+` and `>=3\\.\\d+` string literals in `framework/migration/migrator.py`.

    These are the Python-version defaults the migrator writes INTO
    consumer projects' `pyproject.toml`/ruff config during a migration, so a
    stale literal here ships a stale floor outward to every project this
    tool touches.
    """
    records: list[DeclarationRecord] = []
    try:
        text = MIGRATOR_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return records
    for match in PY3_LITERAL_RE.finditer(text):
        value = match.group(2)
        records.append(
            (
                MIGRATOR_PATH,
                "migrator-py3-literal",
                value,
                _parse_ruff_target_version(value),
            )
        )
    for match in GTE_LITERAL_RE.finditer(text):
        value = match.group(2)
        records.append(
            (
                MIGRATOR_PATH,
                "migrator-gte-literal",
                value,
                _parse_requires_python_floor(value),
            )
        )
    return records


def discover_version_declarations() -> list[DeclarationRecord]:
    """Every Python-version declaration across all five corpora.

    #286 PR-C added the docs corpus - see the module docstring and
    `discover_docs_version_declarations` for its structured/prose
    two-mode contract.
    """
    return (
        discover_toml_version_declarations()
        + discover_workflow_version_declarations()
        + discover_migrator_version_declarations()
        + discover_framework_version_declarations()
        + discover_docs_version_declarations()
    )


def test_version_declaration_discovery_is_not_vacuous():
    """Per-corpus vacuity guard: an empty walk in any one corpus would make
    `test_no_declaration_is_below_the_project_floor` pass for free for it."""
    toml_records = discover_toml_version_declarations()
    assert toml_records, (
        "no [tool.ruff]/[tool.mypy]/[tool.pixi.dependencies] python "
        "declarations found in any *.toml at the repo root or under "
        "templates/ - the TOML walker is broken"
    )

    workflow_records = discover_workflow_version_declarations()
    assert workflow_records, (
        "no python-version(s) matrix declarations found under "
        ".github/workflows/ (*.yml or *.yml.template) - the workflow "
        "walker is broken"
    )

    migrator_records = discover_migrator_version_declarations()
    assert migrator_records, (
        "no py3XX / >=3.Y string literals found in "
        "framework/migration/migrator.py - the migrator walker is broken"
    )


def test_no_declaration_is_below_the_project_floor():
    """Every discovered declaration must admit nothing older than the
    `[project] requires-python` floor (#286).

    Collects every violation and asserts once, rather than asserting inside
    the loop. `discover_version_declarations()` concatenates four corpora,
    so a bare in-loop assert aborts on the first violation found and the
    earliest corpus masks every later one - a mutation test that moved the
    floor forward reported a single `toml-ruff-target-version` failure while
    eleven `framework-*` declarations were violating it in the same run. One
    failure should name all of them, not send the reader round the loop once
    per site.
    """
    floor = requires_python_floor()
    assert floor is not None, "could not parse [project] requires-python"

    violations = [
        f"{path}: {kind} declares {raw_value!r} (parsed floor {parsed_floor})"
        for path, kind, raw_value, parsed_floor in discover_version_declarations()
        # `parsed_floor is None` means no version token at all in the raw
        # value; such a value isn't a floor declaration in its own right, so
        # it can't violate one.
        if parsed_floor is not None and parsed_floor < floor
    ]
    assert not violations, (
        f"{len(violations)} Python-version declaration(s) sit below the "
        f"project floor {floor} required by [project] requires-python "
        "(#286):\n  " + "\n  ".join(sorted(violations))
    )


def test_declaration_classifier_would_have_caught_py310():
    """Classifier self-test: replay the exact #286 regression as synthetic
    input and confirm every declaration shape is both detected and
    classified as below the 3.11 floor. Without this, a classifier that
    silently ignored everything would make the test above pass vacuously,
    the same way an always-'bare' tomllib classifier would above."""
    ruff_floor = _parse_ruff_target_version("py310")
    assert ruff_floor is not None and ruff_floor < MINIMUM_FLOOR, (
        f"ruff target-version classifier failed to catch 'py310' (got {ruff_floor})"
    )

    mypy_floor = _parse_mypy_python_version("3.10")
    assert mypy_floor is not None and mypy_floor < MINIMUM_FLOOR, (
        f"mypy python_version classifier failed to catch '3.10' (got {mypy_floor})"
    )

    pixi_floor = _parse_version_floor_loose(">=3.10")
    assert pixi_floor is not None and pixi_floor < MINIMUM_FLOOR, (
        f"pixi python classifier failed to catch '>=3.10' (got {pixi_floor})"
    )

    matrix_versions = _extract_array_versions('\'["3.10", "3.11"]\'')
    assert matrix_versions is not None, (
        'workflow matrix classifier failed to find an array in \'["3.10", "3.11"]\''
    )
    matrix_floor = min(matrix_versions)
    assert matrix_floor < MINIMUM_FLOOR, (
        f'workflow matrix classifier failed to catch \'["3.10", "3.11"]\' '
        f"(got minimum {matrix_floor})"
    )


# ============================================================================
# #286 PR-B: version declarations inside `framework/` (source and tests)
#
# The three corpora above cover what this repo SHIPS (templates, workflows,
# the migrator's emitted literals). They do not cover `framework/` itself,
# which is how `test_compatibility_matrix.py` came to assert
# `sys.version_info >= (3, 10)` and publish `"3.10": "✅ Supported"` while
# `[project] requires-python` said 3.11.
#
# SCOPE LIMIT, stated plainly so this is not read as broader than it is:
# only version-SPEC shapes are matched - `py3XX`, `>=3.Y` / `^3.Y` / `~=3.Y`,
# `3.Y.*`, list literals of version strings, and `... >= (3, N)`
# comparisons. A BARE `"3.10"` string (a dict key in a free-form
# version->status table, say) is deliberately NOT matched: it occurs in far
# too many innocent contexts to flag usefully. The `compatibility_matrix`
# table in test_compatibility_matrix.py is guarded by its own test against
# the declared floor, not by this walk.
# ============================================================================

FRAMEWORK_DIR = REPO_ROOT / "framework"

# Some version literals below the floor are CORRECT and must stay: the
# classifier self-test samples in this very file, and synthetic fixtures
# modelling CONSUMER projects (a real consumer may well still declare
# ">=3.10" - this framework has to parse that, and testing it means writing
# it down). Exemptions therefore live AT the site and carry a reason, rather
# than in a central list here: a hand-maintained inventory of exempt sites is
# the exact artefact #250/#255/#261/#286 keep going stale on. The trailing
# `\S` means a marker with no reason does not count.
EXEMPT_LINE_RE = re.compile(r"#\s*python-floor-exempt:\s*\S")
EXEMPT_MODULE_RE = re.compile(r"#\s*python-floor-exempt-module:\s*\S")

FRAMEWORK_SPEC_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("framework-py3-literal", re.compile(r"""(['"])(py3\d+)\1""")),
    (
        "framework-spec-literal",
        re.compile(r"""(['"])((?:>=|\^|~=)\s*3\.\d+[^'"]*)\1"""),
    ),
    ("framework-pin-literal", re.compile(r"""(['"])(3\.\d+\.\*)\1""")),
)

# `sys.version_info >= (3, 10)`, including the black-formatted multi-line
# spelling `>= (\n    3,\n    10,\n)` - `\s` matches newlines, so both forms
# are caught.
VERSION_INFO_CMP_RE = re.compile(r">=\s*\(\s*3\s*,\s*(\d+)\s*,?\s*\)")

# A list literal of version strings: `["3.10", "3.11", "3.12"]`. Requires a
# second element so a lone `["3.11"]` - far more likely to be something
# unrelated - is not swept in.
VERSION_LIST_RE = re.compile(r"""\[\s*(['"])3\.\d+\1\s*,\s*[^\]]*\]""")


def _line_of(text: str, offset: int) -> int:
    """1-based line number containing `offset` within `text`."""
    return text.count("\n", 0, offset) + 1


def _is_exempt(lines: list[str], lineno: int) -> bool:
    """True when an exemption marker sits on line `lineno` or the line above.

    `lines` is 0-indexed; `lineno` is 1-based.
    """
    for candidate in (lineno - 1, lineno - 2):
        if 0 <= candidate < len(lines) and EXEMPT_LINE_RE.search(lines[candidate]):
            return True
    return False


def _iter_framework_python_files() -> list[Path]:
    """Every `*.py` under `framework/`, minus the usual excluded directories."""
    if not FRAMEWORK_DIR.is_dir():
        return []
    return sorted(
        path
        for path in FRAMEWORK_DIR.rglob("*.py")
        if not any(part in EXCLUDED_DIR_NAMES for part in path.parts)
    )


def discover_framework_version_declarations() -> list[DeclarationRecord]:
    """Version-spec literals and floor comparisons under `framework/`."""
    records: list[DeclarationRecord] = []
    for path in _iter_framework_python_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if EXEMPT_MODULE_RE.search(text):
            continue
        lines = text.splitlines()

        for kind, pattern in FRAMEWORK_SPEC_RES:
            for match in pattern.finditer(text):
                lineno = _line_of(text, match.start())
                if _is_exempt(lines, lineno):
                    continue
                value = match.group(2)
                parsed = (
                    _parse_ruff_target_version(value)
                    if kind == "framework-py3-literal"
                    else _parse_version_floor_loose(value)
                )
                records.append((path, f"{kind}:{lineno}", value, parsed))

        for match in VERSION_INFO_CMP_RE.finditer(text):
            lineno = _line_of(text, match.start())
            if _is_exempt(lines, lineno):
                continue
            records.append(
                (
                    path,
                    f"framework-version-info-cmp:{lineno}",
                    match.group(0),
                    (3, int(match.group(1))),
                )
            )

        for match in VERSION_LIST_RE.finditer(text):
            lineno = _line_of(text, match.start())
            if _is_exempt(lines, lineno):
                continue
            versions = _extract_array_versions(match.group(0))
            if not versions:
                continue
            records.append(
                (
                    path,
                    f"framework-version-list:{lineno}",
                    match.group(0),
                    min(versions),
                )
            )
    return records


def test_framework_corpus_is_not_vacuous():
    """Vacuity guard, matching the three corpora above."""
    assert discover_framework_version_declarations(), (
        "no version-spec literals or floor comparisons found anywhere under "
        "framework/ - the framework walker is broken, and every site in it "
        "is silently unguarded"
    )


def test_framework_exemption_markers_are_honoured_and_required():
    """Meta-guard on the exemption mechanism itself.

    An `_is_exempt` that returned True unconditionally would silence this
    entire corpus while every test above still passed - the same failure
    shape as an always-'bare' tomllib classifier.
    """
    assert _is_exempt(['python = ">=3.10"  # python-floor-exempt: fixture'], 1)
    assert _is_exempt(["# python-floor-exempt: fixture", 'python = ">=3.10"'], 2)
    assert not _is_exempt(['python = ">=3.10"'], 1)
    # A marker with no reason after the colon does not count.
    assert not _is_exempt(['python = ">=3.10"  # python-floor-exempt:'], 1)


def test_framework_classifier_would_have_caught_the_286_sites():
    """Replay the real #286 `framework/` sites as synthetic input."""
    for raw, parser in (
        ("py310", _parse_ruff_target_version),
        (">=3.10", _parse_version_floor_loose),
        ("^3.10", _parse_version_floor_loose),
        ("3.10.*", _parse_version_floor_loose),
    ):
        parsed = parser(raw)
        assert parsed is not None and parsed < MINIMUM_FLOOR, (
            f"framework spec classifier failed to catch {raw!r} (got {parsed})"
        )

    # `sys.version_info >= (3, 10)` - the test_compatibility_matrix.py shape.
    single_line = VERSION_INFO_CMP_RE.search("assert sys.version_info >= (3, 10)")
    assert single_line is not None
    assert (3, int(single_line.group(1))) < MINIMUM_FLOOR
    # ...and its black-formatted multi-line spelling.
    assert VERSION_INFO_CMP_RE.search("current_version >= (\n    3,\n    10,\n)")

    # `["3.10", "3.11", "3.12"]` - the analyzer.py shape.
    list_match = VERSION_LIST_RE.search('versions = ["3.10", "3.11", "3.12"]')
    assert list_match is not None
    list_versions = _extract_array_versions(list_match.group(0))
    assert list_versions is not None and min(list_versions) < MINIMUM_FLOOR

    # The documented scope limit: a bare version string must NOT be swept in.
    assert not any(
        pattern.search('matrix = {"3.10": "not supported"}')
        for _, pattern in FRAMEWORK_SPEC_RES
    )


# ============================================================================
# #286 PR-C: version declarations inside docs/, README.md, examples/, and
# shipped composite-action READMEs.
#
# Markdown mixes structured config (fenced code blocks, inline-code spans)
# with running prose, so this corpus classifies each line in one of two
# modes rather than a single regex set:
#
#   - structured: a line inside a ``` fence or an inline `code span` is
#     matched against the same quoted/structured shapes the TOML/workflow/
#     framework corpora above already use (`python = "<spec>"`,
#     `python-version(s):`/`=` arrays or comma strings, `target-version =
#     "pyNNN"`, `python_version = "N.NN"`, a bare `- python>=N.NN` list
#     item).
#   - prose: any bare `X.Y` version token in running text (`Python 3.10+`,
#     a table cell, `On 3.10 or older they fail...`) is a candidate, GATED
#     on a "python" mention in the same line - or, for a table row, in that
#     row's actual HEADER row (the row immediately above the table's
#     `|---|---|` delimiter row - never prose that merely sits a few lines
#     above), matched by column index - so unrelated decimal-shaped numbers
#     (framework/action versions, percentages, pixi CLI pins, playback
#     speeds, or an ordinary prose line like "...for Python projects..."
#     sitting above an unrelated table) don't get swept in as Python-floor
#     declarations.
#
# Both modes are negation-aware: a match is dropped when its line (or, for
# prose, the enclosing sentence) reads as non-support - "not supported", "no
# longer", "dropped", "unsupported", "removed", "fail(s)",
# "ModuleNotFoundError", "must pass an explicit". This is what lets prose
# describing what ISN'T supported read correctly without an exemption
# marker. `#`-comments do not work in Markdown, so the exemption mechanism
# is `<!-- python-floor-exempt: <reason> -->` on the same line or the line
# above, mirroring `EXEMPT_LINE_RE`'s same-line-or-above contract and
# mandatory reason.
# ============================================================================

DOCS_DIR = REPO_ROOT / "docs"
README_PATH = REPO_ROOT / "README.md"
EXAMPLES_DIR = REPO_ROOT / "examples"
ACTIONS_DIR = REPO_ROOT / "actions"
GITHUB_ACTIONS_DIR = REPO_ROOT / ".github" / "actions"

# Mirrors EXEMPT_LINE_RE's same-line-or-above contract and mandatory reason,
# spelled as an HTML comment since `#` is not a comment marker in Markdown.
DOCS_EXEMPT_RE = re.compile(r"<!--\s*python-floor-exempt:\s*\S")

# Case-insensitive non-support vocabulary that suppresses a match in either
# mode - see the corpus header comment above for why this exists.
DOCS_NEGATION_RE = re.compile(
    r"not\s+supported|no\s+longer|dropped|unsupported|removed|fails?|"
    r"ModuleNotFoundError|must\s+pass\s+an\s+explicit",
    re.IGNORECASE,
)

FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# A markdown table delimiter row (`|---|---|`, `|:--|--:|`, ...): every cell
# is dashes with optional leading/trailing alignment colons. This is what
# distinguishes an actual table HEADER from prose that merely sits a few
# lines above a table - matching by line-count proximity (the previous
# `DOCS_TABLE_HEADER_WINDOW` approach) let prose mentioning "python"
# anywhere near a table misattribute an unrelated cell to the Python floor
# (docs/api/actions/quality-gates.md:16's `| **Version** | v0.0.1 |`, gated
# in by "...for Python projects..." two rows above prose, not a header).
TABLE_DELIMITER_CELL_RE = re.compile(r"^:?-+:?$")

DOCS_RUFF_TARGET_RE = re.compile(r"""\btarget-version\s*=\s*(['"])(py\d{2,3})\1""")
DOCS_MYPY_VERSION_RE = re.compile(r"""\bpython_version\s*=\s*(['"])(\d+\.\d+)\1""")
DOCS_PIXI_PYTHON_RE = re.compile(r"""\bpython\s*=\s*(['"])([^'"]+)\1""")
DOCS_VERSION_KEY_RE = re.compile(r"""['"]?(python-versions?)['"]?\s*[:=]\s*(.+)$""")
DOCS_BARE_SPEC_RE = re.compile(r"-\s*python\s*(>=|==|~=|\^)\s*(\d+\.\d+)")

# Prose-mode Python-attachment (#286 PR-C follow-up): a version token only
# counts toward the floor when it is syntactically attached to one of these
# mentions. The longer alternative is tried first so "python-version(s)"/
# "python_version" isn't eaten by the bare "python" branch before its own
# attached version-run can be matched against the text right after it.
PYTHON_MENTION_RE = re.compile(r"python[-_]version(?:s)?|python", re.IGNORECASE)

# The run of version tokens immediately attached to a `PYTHON_MENTION_RE`
# match: a single token (`3.10`, `3.10+`), a dash/en-dash range
# (`3.10-3.12`, `3.10–3.12` - the FIRST token is the floor), a textual
# range ("3.10 or higher", "3.10 and up"), or a comma-run
# (`3.10, 3.11, 3.12` - the minimum of the run is the floor). Each token
# after the first requires its own separator immediately before it, so the
# run stops the instant something that isn't part of this shape follows -
# which is what keeps `Python 3.10+, Rust 1.70+, Node.js 18+` from
# swallowing `1.70`/`18` into the same run as `3.10`. The leading `[*_]*`
# absorbs markdown emphasis closing markers directly after the mention
# (`- **Python**: 3.10 or higher`), where `mention.end()` lands right before
# the closing `**` and not before the version token itself; it only
# consumes emphasis markers immediately there, so it cannot skip ahead
# through arbitrary text to a later, unrelated number.
VERSION_RUN_RE = re.compile(
    r"""
    [*_]*\s*[:=]?\s*
    \d+\.\d+\+?
    (?:
        \s*(?:,|-|–|or\s+higher|and\s+up|or\s+up)\s*
        \d+\.\d+\+?
    )*
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _iter_docs_candidate_files() -> list[Path]:
    """`docs/**/*.md`, the repo-root `README.md`, `examples/**/*.yml`|`.yaml`,
    and shipped composite-action READMEs (`actions/*/README.md`,
    `.github/actions/*/README.md`)."""
    candidates: set[Path] = set()
    if DOCS_DIR.is_dir():
        candidates.update(DOCS_DIR.rglob("*.md"))
    if README_PATH.is_file():
        candidates.add(README_PATH)
    if EXAMPLES_DIR.is_dir():
        candidates.update(EXAMPLES_DIR.rglob("*.yml"))
        candidates.update(EXAMPLES_DIR.rglob("*.yaml"))
    if ACTIONS_DIR.is_dir():
        candidates.update(ACTIONS_DIR.glob("*/README.md"))
    if GITHUB_ACTIONS_DIR.is_dir():
        candidates.update(GITHUB_ACTIONS_DIR.glob("*/README.md"))
    return sorted(
        path
        for path in candidates
        if path.is_file() and not any(part in EXCLUDED_DIR_NAMES for part in path.parts)
    )


def _is_docs_exempt(lines: list[str], lineno: int) -> bool:
    """True when a `<!-- python-floor-exempt: ... -->` marker sits on line
    `lineno` or the line above. `lines` is 0-indexed; `lineno` is 1-based."""
    for candidate in (lineno - 1, lineno - 2):
        if 0 <= candidate < len(lines) and DOCS_EXEMPT_RE.search(lines[candidate]):
            return True
    return False


def _fence_is_exempt(lines: list[str], fence_lineno: int) -> bool:
    """True when a `<!-- python-floor-exempt: ... -->` marker sits on the
    line immediately ABOVE an opening fence at 1-based `fence_lineno`.

    An HTML comment placed INSIDE the fence would render literally as part
    of the sample it's meant to exempt, so `_is_docs_exempt`'s same-line-or-
    line-above contract can never reach a line that is itself inside a
    fenced block - the marker and the flagged line are always separated by
    the opening ``` fence itself. This is the fence-scoped counterpart: the
    marker exempts every line inside the fence that follows it (up to its
    closing fence), not just one line. "Immediately above" (not "somewhere
    above") keeps the scope tight and visible to reviewers - a blank or
    prose line between the marker and the fence breaks the association, the
    same way `EXEMPT_MODULE_RE` requires an explicit, reasoned marker rather
    than an implicit central list.
    """
    candidate = fence_lineno - 2
    return (
        0 <= candidate < len(lines)
        and DOCS_EXEMPT_RE.search(lines[candidate]) is not None
    )


def _is_table_delimiter_row(line: str) -> bool:
    """True when `line` is a markdown table delimiter row (`|---|:--|--:|`):
    every cell is dashes with optional alignment colons, nothing else."""
    if not line.lstrip().startswith("|"):
        return False
    cells = _split_table_cells(line)
    return bool(cells) and all(TABLE_DELIMITER_CELL_RE.match(cell) for cell in cells)


def _table_header_index(lines: list[str], index: int) -> int | None:
    """Index of the HEADER row for the table row at `index`, or None.

    Walks upward through the contiguous block of pipe-delimited rows this
    row belongs to; the block's topmost row counts as a header when the row
    immediately below it is a markdown delimiter row. That is what
    distinguishes an actual table header from prose that merely happens to
    sit a few lines above a table - proximity alone is not enough (see
    `TABLE_DELIMITER_CELL_RE`'s comment for the concrete false positive
    this replaced).

    Gherkin data tables (`| Python Version | Operating System |` followed
    directly by data rows, as in `bdd-scenarios-ci-workflow.md`) never carry
    a `|---|---|` delimiter row at all - that's markdown-table syntax, not
    Gherkin's. When NO row anywhere in the contiguous block is a delimiter
    row, the topmost row is accepted as the header by the Gherkin table
    spec (first row = header, unconditionally). This can't resurrect the
    nearby-prose false positive above: that block only ever forms from
    contiguous `|`-prefixed lines, so prose sitting outside the block is
    still excluded from `top` by the same upward walk as before.
    """
    top = index
    while top - 1 >= 0 and lines[top - 1].lstrip().startswith("|"):
        top -= 1
    if top + 1 < len(lines) and _is_table_delimiter_row(lines[top + 1]):
        return top
    bottom = index
    while bottom + 1 < len(lines) and lines[bottom + 1].lstrip().startswith("|"):
        bottom += 1
    if top < bottom and not any(
        _is_table_delimiter_row(lines[i]) for i in range(top, bottom + 1)
    ):
        return top
    return None


def _has_python_context(lines: list[str], index: int, line: str) -> bool:
    """True when `line` mentions "python" - or, for a markdown table row,
    when that row's actual HEADER row (see `_table_header_index`; requires
    a delimiter row immediately beneath it) does. `index` is 0-based,
    matching `lines`.

    This is the gate that keeps prose mode from sweeping in unrelated
    decimal-shaped numbers (framework/action versions, percentages, pixi
    CLI pins, playback speeds) as Python-floor declarations. A table row
    with no qualifying header contributes nothing - it does NOT fall back
    to scanning nearby prose.
    """
    if "python" in line.lower():
        return True
    if not line.lstrip().startswith("|"):
        return False
    header_index = _table_header_index(lines, index)
    if header_index is None:
        return False
    return "python" in lines[header_index].lower()


def _split_table_cells(line: str) -> list[str]:
    """Cell texts of one markdown table row, leading/trailing `|` stripped."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _table_python_value_cells(lines: list[str], index: int) -> list[str] | None:
    """The cell(s) of the table row at `index` that hold Python-version
    data, or None when this isn't a recognisable Python-version table row.

    Two shapes, mirroring `_has_python_context`'s own-row-or-actual-header
    lookup: a ROW-oriented table, where a cell in THIS row names Python (a
    row label like `| Python | 3.10+ |`, or a self-contained cell like
    `| Python 3.10+ |`) - the data is that cell itself if it already
    carries an attached version, otherwise every other cell in the row; or
    a COLUMN-oriented table, where this row's actual HEADER row (see
    `_table_header_index`; requires a delimiter row immediately beneath it
    - prose above a table is never a header) names a Python column at some
    index - the data is just this row's cell at that SAME column index.
    Either way the extraction is scoped to the identified cell(s), not the
    whole row, so an unrelated column (`Framework Version: v1.0.x`,
    `Operating System: ubuntu-latest`) can't contribute a stray token.
    Returns None - contributing nothing, with no further fallback - when
    neither shape matches.
    """
    line = lines[index]
    if not line.lstrip().startswith("|"):
        return None
    cells = _split_table_cells(line)
    for col, cell in enumerate(cells):
        if PYTHON_MENTION_RE.search(cell):
            if VERSION_TOKEN_RE.search(cell):
                return [cell]
            return cells[:col] + cells[col + 1 :]
    header_index = _table_header_index(lines, index)
    if header_index is None:
        return None
    header_cells = _split_table_cells(lines[header_index])
    for col, header_cell in enumerate(header_cells):
        if PYTHON_MENTION_RE.search(header_cell):
            return [cells[col]] if col < len(cells) else None
    return None


def _sentence_containing(line: str, position: int) -> str:
    """The sentence in `line` (period/question/exclamation-delimited) that
    contains character offset `position`, so prose-mode negation is gated
    per-sentence rather than per-line when a line carries more than one."""
    start = 0
    end = len(line)
    for boundary_match in re.finditer(r"[.!?](?:\s|$)", line):
        boundary = boundary_match.end()
        if boundary <= position:
            start = boundary
        else:
            end = boundary
            break
    return line[start:end]


def _match_docs_structured(
    text: str,
) -> tuple[str, str, tuple[int, int] | None] | None:
    """Match one of the quoted/structured version-declaration shapes this
    corpus scans for inside fenced code blocks and inline-code spans.
    Mirrors the quoted-literal shapes `FRAMEWORK_SPEC_RES` and the
    TOML/workflow corpora above already match, so the same declaration
    written in a doc's example config is caught the same way."""
    match = DOCS_RUFF_TARGET_RE.search(text)
    if match is not None:
        value = match.group(2)
        return "docs-ruff-target-version", value, _parse_ruff_target_version(value)

    match = DOCS_MYPY_VERSION_RE.search(text)
    if match is not None:
        value = match.group(2)
        return "docs-mypy-python-version", value, _parse_mypy_python_version(value)

    match = DOCS_PIXI_PYTHON_RE.search(text)
    if match is not None:
        value = match.group(2)
        return "docs-pixi-python", value, _parse_version_floor_loose(value)

    match = DOCS_VERSION_KEY_RE.search(text)
    if match is not None:
        raw = match.group(2).strip()
        versions = _extract_array_versions(raw)
        floor = min(versions) if versions else _parse_version_floor_loose(raw)
        if floor is not None:
            return "docs-python-versions", raw, floor

    match = DOCS_BARE_SPEC_RE.search(text)
    if match is not None:
        raw = match.group(0).strip()
        return "docs-bare-python-spec", raw, _parse_version_floor_loose(raw)

    return None


def _structured_record(
    path: Path, line: str, text: str, lineno: int
) -> DeclarationRecord | None:
    """One structured-mode record for `text` (either a whole fenced line or
    an inline-code span's contents), gated on `line`-level negation."""
    structured = _match_docs_structured(text)
    if structured is None or DOCS_NEGATION_RE.search(line):
        return None
    kind, raw, parsed = structured
    return (path, f"{kind}:{lineno}", raw, parsed)


def _prose_floor(prose_line: str) -> tuple[int, int] | None:
    """Minimum non-negated version-token floor in a prose line, scanning
    only version tokens syntactically ATTACHED to a Python mention (see
    `PYTHON_MENTION_RE`/`VERSION_RUN_RE`) - not every version-shaped token
    on the line. A token that isn't attached to Python (`Rust 1.70`,
    `Node.js 18+`, `C++17`) contributes nothing, which is what stops this
    line-wide scan from misattributing another tool's version to the
    Python floor. Returns None when no mention has an attached run, or
    every attached run's sentence reads as non-support.
    """
    floor: tuple[int, int] | None = None
    for mention in PYTHON_MENTION_RE.finditer(prose_line):
        run_match = VERSION_RUN_RE.match(prose_line, mention.end())
        if run_match is None:
            continue
        sentence = _sentence_containing(prose_line, run_match.start())
        if DOCS_NEGATION_RE.search(sentence):
            continue
        for major, minor in VERSION_TOKEN_RE.findall(run_match.group(0)):
            candidate = (int(major), int(minor))
            if floor is None or candidate < floor:
                floor = candidate
    return floor


def _prose_python_floor(
    lines: list[str], index: int, prose_line: str
) -> tuple[int, int] | None:
    """The Python-attached version floor for one prose line.

    A markdown table row is scoped to just its Python-identified cell(s)
    (`_table_python_value_cells`, row-label or column-header) and
    contributes NOTHING - no loose-scan fallback - when neither shape
    qualifies; every other prose line is scoped to version tokens
    syntactically attached to a Python mention (`_prose_floor`). A table
    row's own cells are checked against `DOCS_NEGATION_RE` as a whole
    (mirroring the structured-mode per-line check) rather than
    per-sentence, since a table cell rarely forms a full sentence of its
    own.
    """
    if prose_line.lstrip().startswith("|"):
        cells = _table_python_value_cells(lines, index)
        if cells is None:
            return None
        if DOCS_NEGATION_RE.search(prose_line):
            return None
        tokens = [
            (int(major), int(minor))
            for cell in cells
            for major, minor in VERSION_TOKEN_RE.findall(cell)
        ]
        return min(tokens) if tokens else None
    return _prose_floor(prose_line)


# How far a bare `["3.10", "3.11", "3.12"]`-shaped array literal (2+
# tokens, via `_extract_array_versions`) may sit from a "python" mention on
# a DIFFERENT line before the two are considered attached, e.g. a jq
# pipeline that builds `["3.10", "3.11", "3.12"] as $versions |` on one
# line and consumes it as `{package: $pkg, python: $ver}` a couple of
# lines later (`examples/monorepo-change-detection.yml`). Kept small and
# gated on the array shape itself (not a bare "python" word scan) so this
# can't resurrect the nearby-prose false positive `_table_header_index`'s
# delimiter check exists to close - an array of 2+ version-shaped tokens is
# a far stronger signal than proximity to the word "python" alone.
ARRAY_PYTHON_MENTION_WINDOW = 3


def _nearby_python_mention(lines: list[str], index: int) -> bool:
    """True when a "python" mention sits within
    `ARRAY_PYTHON_MENTION_WINDOW` lines of `index` (either direction, not
    counting `index` itself)."""
    lo = max(0, index - ARRAY_PYTHON_MENTION_WINDOW)
    hi = min(len(lines), index + ARRAY_PYTHON_MENTION_WINDOW + 1)
    return any("python" in lines[i].lower() for i in range(lo, hi) if i != index)


def _docs_records_for_text(path: Path, text: str) -> list[DeclarationRecord]:
    """Real per-file classifier, factored out of
    `discover_docs_version_declarations` so the self-test below can feed it
    synthetic markdown directly - the same way `classify_python`/
    `classify_text` are unit-tested above `discover_tomllib_sites`.

    Fenced-code lines and inline-code spans go through the structured
    matcher first; everything else (including a fenced or inline-code span
    that ISN'T one of the structured shapes - a prose sentence or a Gherkin
    table row quoted inside a ``` fence, a console-output job name wrapped
    in a single inline-code span) falls back to the same bare-`X.Y`-token
    prose scan used for ordinary text, gated on a "python" mention (line or
    table header - see `_has_python_context`). A bare version-array literal
    with no "python" mention on its OWN line, but one nearby, is also
    caught (see `_nearby_python_mention`). Every mode drops a match whose
    line/sentence reads as non-support (see `DOCS_NEGATION_RE`), and all
    honour a same-line-or-above `<!-- python-floor-exempt: ... -->` marker.
    """
    records: list[DeclarationRecord] = []
    lines = text.splitlines()
    in_fence = False
    fence_exempt = False
    for index, line in enumerate(lines):
        lineno = index + 1
        if FENCE_RE.match(line):
            if in_fence:
                in_fence = False
                fence_exempt = False
            else:
                in_fence = True
                fence_exempt = _fence_is_exempt(lines, lineno)
            continue
        if in_fence and fence_exempt:
            continue
        if _is_docs_exempt(lines, lineno):
            continue

        if in_fence:
            record = _structured_record(path, line, line, lineno)
            if record is not None:
                records.append(record)
            elif _has_python_context(lines, index, line):
                floor = _prose_python_floor(lines, index, line)
                if floor is not None:
                    records.append(
                        (path, f"docs-prose-token:{lineno}", line.strip(), floor)
                    )
            continue

        for span in INLINE_CODE_RE.finditer(line):
            span_text = span.group(1)
            record = _structured_record(path, line, span_text, lineno)
            if record is not None:
                records.append(record)
            else:
                floor = _prose_floor(span_text)
                if floor is not None:
                    records.append(
                        (path, f"docs-prose-token:{lineno}", span_text.strip(), floor)
                    )

        prose_line = INLINE_CODE_RE.sub(" ", line)
        if _has_python_context(lines, index, prose_line):
            floor = _prose_python_floor(lines, index, prose_line)
            if floor is not None:
                records.append(
                    (path, f"docs-prose-token:{lineno}", prose_line.strip(), floor)
                )
        elif not prose_line.lstrip().startswith("|"):
            versions = _extract_array_versions(prose_line)
            if (
                versions
                and len(versions) > 1
                and _nearby_python_mention(lines, index)
                and not DOCS_NEGATION_RE.search(prose_line)
            ):
                records.append(
                    (
                        path,
                        f"docs-nearby-array-token:{lineno}",
                        prose_line.strip(),
                        min(versions),
                    )
                )
    return records


def discover_docs_version_declarations() -> list[DeclarationRecord]:
    """Python-version declarations across docs/, README.md, examples/, and
    shipped composite-action READMEs (#286 PR-C)."""
    records: list[DeclarationRecord] = []
    for path in _iter_docs_candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        records.extend(_docs_records_for_text(path, text))
    return records


def test_docs_corpus_is_not_vacuous():
    """Vacuity guard, matching `test_framework_corpus_is_not_vacuous` above."""
    assert discover_docs_version_declarations(), (
        "no version declarations found anywhere in docs/, README.md, "
        "examples/, or shipped action READMEs - the docs walker is broken, "
        "and every site in it is silently unguarded"
    )


def test_docs_classifier_distinguishes_support_from_deprecation():
    """Anti-vacuity self-test for the docs corpus: feeds synthetic markdown
    through the REAL classifier (`_docs_records_for_text`), mirroring
    `test_classifier_detects_the_fallback_idiom` above. A classifier that
    silently ignored everything, or that flagged deprecation prose as a
    live declaration, would make this corpus vacuous or noisy without a
    test like this one catching it."""
    sample = (
        "Some intro text.\n"
        "```toml\n"
        'python = ">=3.10"\n'
        "```\n"
        "This project supports Python 3.10+.\n"
        "Python 3.10 is no longer supported here.\n"
        'python = ">=3.9"  <!-- python-floor-exempt: fixture -->\n'
    )
    records = _docs_records_for_text(Path("<docs-sample>"), sample)
    flagged_lines = {int(kind.rsplit(":", 1)[1]) for _, kind, _, _ in records}

    assert 3 in flagged_lines, (
        f'fenced `python = ">=3.10"` (line 3) was not flagged: {records}'
    )
    assert 5 in flagged_lines, (
        f"prose 'Python 3.10+' (line 5) was not flagged: {records}"
    )
    assert 6 not in flagged_lines, (
        "deprecation prose '3.10 is no longer supported' (line 6) was "
        f"incorrectly flagged: {records}"
    )
    assert 7 not in flagged_lines, (
        f'exempted `python = ">=3.9"` (line 7) was incorrectly flagged: {records}'
    )


def test_docs_prose_classifier_only_attaches_versions_to_python():
    """Regression for the #286 PR-C follow-up: prose mode used to take the
    line-wide minimum of EVERY version-shaped token on a line gated only by
    a "python" mention somewhere on it, so `Python 3.10+, Rust 1.70+` read
    Rust's `1.70` as the Python floor. That happened to still flag the
    line (1.70 < 3.11), which made the bug invisible - the same shape with
    a correct Python version (`Python 3.12+, Rust 1.70+`) would report a
    false-positive violation on a perfectly fine line. This checks both the
    absence of a violation on the correct-version line AND the exact parsed
    floor on the violating line, per the classifier self-test convention
    used elsewhere in this file (`test_classifier_detects_the_fallback_idiom`,
    `test_framework_classifier_would_have_caught_the_286_sites`): checking
    only "something was flagged" would let the misattribution regress
    invisibly, the same way it did originally.
    """
    clean_sample = (
        "**Compatibility**: GitHub Actions, Python 3.12+, Rust 1.70+, Node.js 18+\n"
    )
    clean_records = _docs_records_for_text(Path("<docs-sample>"), clean_sample)
    clean_violations = [
        record
        for record in clean_records
        if record[3] is not None and record[3] < MINIMUM_FLOOR
    ]
    assert not clean_violations, (
        "a line whose Python version is above the floor must produce no "
        "violation even though it also mentions Rust/Node versions - Rust's "
        f"1.70 must not be misread as the Python floor: {clean_records}"
    )

    violating_sample = "**Compatibility**: GitHub Actions, Python 3.10+, Rust 1.70+\n"
    violating_records = _docs_records_for_text(Path("<docs-sample>"), violating_sample)
    assert violating_records, (
        "a line whose Python version is below the floor must be flagged: "
        f"{violating_records}"
    )
    parsed_floors = {parsed for _, _, _, parsed in violating_records}
    assert parsed_floors == {(3, 10)}, (
        "classifier misattributed a non-Python version token (likely Rust's "
        f"1.70) to the Python floor instead of parsing Python's own 3.10: "
        f"{violating_records}"
    )


def test_docs_table_header_must_be_a_real_header_not_nearby_prose():
    """Regression for the exact `docs/api/actions/quality-gates.md:16` false
    positive: a prose line mentioning "python" sitting a few rows above an
    UNRELATED table used to be accepted as that table's header by pure
    line-count proximity, so `| **Version** | v0.0.1 |` (an action's own
    version, not a Python version) was misread as a Python floor of
    `(0, 0)`. A line only counts as a table header now when it is
    immediately followed by a markdown delimiter row (`_table_header_index`),
    and a cell is only a Python-version candidate when the header cell AT
    THE SAME COLUMN INDEX names Python (`_table_python_value_cells`) - so
    prose above a table can never stand in for its header.

    The second assertion is the anti-vacuity half: it proves the fix did
    not simply disable table scanning by feeding a table whose header
    genuinely does name a Python column and asserting it is still caught,
    with the exact parsed floor - the same convention used by
    `test_docs_prose_classifier_only_attaches_versions_to_python` above.
    """
    quality_gates_shape = (
        "This action is intended for Python projects.\n"
        "\n"
        "| Setting | Value |\n"
        "|---------|-------|\n"
        "| **Version** | v0.0.1 |\n"
    )
    no_violation_records = _docs_records_for_text(
        Path("<docs-sample>"), quality_gates_shape
    )
    no_violations = [
        record
        for record in no_violation_records
        if record[3] is not None and record[3] < MINIMUM_FLOOR
    ]
    assert not no_violations, (
        "prose mentioning 'python' above an unrelated table must not turn "
        "that table's non-Python cell into a Python-floor violation: "
        f"{no_violation_records}"
    )

    python_column_shape = (
        "| Python version | Status |\n"
        "|-----------------|--------|\n"
        "| 3.10 | Supported |\n"
    )
    violating_records = _docs_records_for_text(
        Path("<docs-sample>"), python_column_shape
    )
    assert violating_records, (
        "a table whose header genuinely names a Python column must still "
        f"be flagged - the fix must not disable table scanning: {python_column_shape!r}"
    )
    parsed_floors = {parsed for _, _, _, parsed in violating_records}
    assert parsed_floors == {(3, 10)}, (
        "a real Python-version column table must parse floor (3, 10), not "
        f"be silently dropped or misparsed: {violating_records}"
    )


def _violations(records: list[DeclarationRecord]) -> list[DeclarationRecord]:
    """Records below the floor, for the paired MISS/near-miss tests below."""
    return [r for r in records if r[3] is not None and r[3] < MINIMUM_FLOOR]


def test_docs_prose_classifier_handles_markdown_bold_python_mention():
    """Regression for #286 PR-C follow-up survey site
    `docs/ci-workflow-guide.md:62`: `- **Python**: 3.10 or higher` was not
    flagged because markdown bold syntax puts a closing `**` directly
    between the "Python" mention and its version, and `VERSION_RUN_RE`
    anchored immediately after the mention (via `re.match`, not `re.search`)
    with no allowance for it - `mention.end()` lands right before the `**`,
    not before the digits, so the match failed at the very first character.
    """
    sample = "- **Python**: 3.10 or higher\n"
    violations = _violations(_docs_records_for_text(Path("<docs-sample>"), sample))
    assert violations, f"bold-then-colon Python mention was not flagged: {violations}"
    assert {parsed for *_, parsed in violations} == {(3, 10)}, violations

    # Near-miss: consuming the closing `**` must not let the regex skip
    # through unrelated text to a LATER, unrelated version number.
    near_miss = "**Python** is documented separately; see **v2.0** for details.\n"
    near_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), near_miss)
    )
    assert not near_violations, (
        f"an unattached later version must not be swept in: {near_violations}"
    )


def test_docs_inline_code_prose_is_not_dropped_by_the_structured_matcher():
    """Regression for #286 PR-C follow-up survey site
    `docs/ci-workflow-guide.md:122`: a job name like `` `🧪 Test Python 3.10
    on ubuntu-latest` `` wrapped in inline code was silently dropped twice
    over - the structured matcher only recognises config shapes (not free
    prose), and `INLINE_CODE_RE.sub(" ", line)` blanks the span out of the
    prose scanner's view before it ever runs.
    """
    sample = "Job names: `🧪 Test Python 3.10 on ubuntu-latest`.\n"
    violations = _violations(_docs_records_for_text(Path("<docs-sample>"), sample))
    assert violations, f"prose inside inline code was not flagged: {violations}"
    assert {parsed for *_, parsed in violations} == {(3, 10)}, violations

    # Near-miss: "Python" mentioned but not immediately attached to the
    # version that follows an unrelated word - must not be swept in.
    near_miss = "Job names: `Test Python and Node 3.10 on ubuntu-latest`.\n"
    near_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), near_miss)
    )
    assert not near_violations, (
        f"an unattached version inside inline code must not be flagged: {near_violations}"
    )


def test_docs_fenced_gherkin_table_without_delimiter_row_is_caught():
    """Regression for #286 PR-C follow-up survey site
    `docs/bdd-scenarios-ci-workflow.md:81-82`: a Gherkin data table nested
    inside a ```gherkin fence was invisible twice over - fenced lines only
    ran through the structured matcher (no table logic at all), and Gherkin
    tables never carry markdown's `|---|---|` delimiter row in the first
    place, which `_table_header_index` used to require unconditionally.
    """
    sample = (
        "```gherkin\n"
        "    Then it should test all combinations:\n"
        "      | Python Version | Operating System |\n"
        "      | 3.10 | ubuntu-latest |\n"
        "      | 3.11 | ubuntu-latest |\n"
        "```\n"
    )
    violations = _violations(_docs_records_for_text(Path("<docs-sample>"), sample))
    assert violations, f"fenced Gherkin table column was not flagged: {violations}"
    assert {parsed for *_, parsed in violations} == {(3, 10)}, violations

    # Near-miss: a delimiter-less fenced table with no Python column must
    # stay silent - proves this isn't just "flag every fenced table".
    near_miss = (
        "```gherkin\n"
        "      | Framework Version | Operating System |\n"
        "      | 1.2 | ubuntu-latest |\n"
        "```\n"
    )
    near_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), near_miss)
    )
    assert not near_violations, (
        f"a non-Python fenced table column must not be flagged: {near_violations}"
    )


def test_docs_fenced_prose_sentence_is_caught():
    """Regression for #286 PR-C follow-up survey site
    `docs/examples/quick-start.md:138`: a prose sentence inside a ```bash
    fence (here, a multi-line git commit message body) was invisible
    because fenced lines only ran through the structured matcher, which
    doesn't recognise free prose at all - the same gap
    `test_docs_fenced_gherkin_table_without_delimiter_row_is_caught` closes
    for table rows, closed here for ordinary sentences.
    """
    sample = "```bash\n- Configure cross-platform testing (Python 3.10-3.12)\n```\n"
    violations = _violations(_docs_records_for_text(Path("<docs-sample>"), sample))
    assert violations, f"fenced prose sentence was not flagged: {violations}"
    assert {parsed for *_, parsed in violations} == {(3, 10)}, violations

    # Near-miss: fenced prose whose Python version is fine must not flag,
    # even though it also mentions an unrelated tool's version.
    near_miss = (
        "```bash\n- Configure cross-platform testing (Python 3.12+, Rust 1.70+)\n```\n"
    )
    near_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), near_miss)
    )
    assert not near_violations, (
        f"a fine fenced Python version must not be flagged: {near_violations}"
    )


def test_docs_nearby_array_literal_without_same_line_python_is_caught():
    """Regression for #286 PR-C follow-up survey site
    `examples/monorepo-change-detection.yml:55`: a jq pipeline builds
    `["3.10", "3.11", "3.12"] as $versions |` on one line and consumes it as
    `{package: $pkg, python: $ver}` two lines later - the array line itself
    never mentions "python", so the same-line-only gate missed it even
    though `examples/**/*.yml` is genuinely walked (`_iter_docs_candidate_files`
    includes it, and this is the only version-shaped content anywhere under
    `examples/`).
    """
    sample = (
        'test_matrix=$(echo "$package_array" | jq \'\n'
        "  [.[] as $pkg |\n"
        '   ["3.10", "3.11", "3.12"] as $versions |\n'
        "   $versions[] as $ver |\n"
        "   {package: $pkg, python: $ver}]')\n"
    )
    violations = _violations(_docs_records_for_text(Path("<docs-sample>"), sample))
    assert violations, f"nearby array literal was not flagged: {violations}"
    assert {parsed for *_, parsed in violations} == {(3, 10)}, violations

    # Near-miss: an unrelated array sitting outside the mention window must
    # not be swept in, even though a "python" mention appears later on.
    near_miss = "retries = [1.5, 2.5, 3.5]\n\n\n\n# uses python for orchestration\n"
    near_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), near_miss)
    )
    assert not near_violations, (
        f"an out-of-window array must not be flagged: {near_violations}"
    )


def test_docs_fence_scoped_exemption_is_tight_and_does_not_leak():
    """Regression for `docs/ci-workflow-guide.md:202`: a sample diagnostic
    (`::warning ... this job is named for Python 3.11 but pixi environment
    'default' runs Python 3.9 ...`) sits several lines inside a fenced code
    block, illustrating a mismatch rather than declaring one. An HTML
    comment cannot live INSIDE the fence - it would render literally as
    part of the sample - so `<!-- python-floor-exempt: ... -->` has to sit
    on the line immediately above the OPENING fence instead, and
    `_is_docs_exempt`'s same-line-or-line-above contract can never see a
    marker separated from its target by the fence line itself. This is the
    fence-scoped counterpart (`_fence_is_exempt`), checked in three parts
    so the exemption is proven both present where it should be and absent
    everywhere it should not leak to - the same paired
    present/absent convention as `test_docs_prose_classifier_only_attaches_versions_to_python`.
    """
    # Part 1: marker immediately above the opening fence exempts a line two
    # rows deep in that block - must raise no violation at all.
    exempt_sample = (
        "<!-- python-floor-exempt: sample diagnostic output illustrating a "
        "mismatch, not a support declaration -->\n"
        "```\n"
        "some diagnostic preamble\n"
        'python = ">=3.9"\n'
        "```\n"
    )
    exempt_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), exempt_sample)
    )
    assert not exempt_violations, (
        "a marker immediately above the opening fence must exempt every "
        f"line inside that fenced block: {exempt_violations}"
    )

    # Part 2 (anti-vacuity): a BLANK line between the marker and the fence
    # breaks the association, so the identical fenced content is flagged
    # with the exact parsed floor - proves the exemption is scoped to
    # "immediately before the fence", not merely "somewhere above it".
    blank_gap_sample = (
        "<!-- python-floor-exempt: sample diagnostic output illustrating a "
        "mismatch, not a support declaration -->\n"
        "\n"
        "```\n"
        "some diagnostic preamble\n"
        'python = ">=3.9"\n'
        "```\n"
    )
    blank_gap_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), blank_gap_sample)
    )
    assert blank_gap_violations, (
        "a marker separated from the fence by a blank line must NOT exempt "
        f"the block: {blank_gap_violations}"
    )
    assert {parsed for *_, parsed in blank_gap_violations} == {(3, 9)}, (
        f"blank-gap block must parse floor (3, 9): {blank_gap_violations}"
    )

    # Part 3: a marker exempting one fenced block must not leak past its own
    # closing fence into a LATER, unmarked block in the same document.
    two_block_sample = (
        "<!-- python-floor-exempt: sample diagnostic output illustrating a "
        "mismatch, not a support declaration -->\n"
        "```\n"
        'python = ">=3.9"\n'
        "```\n"
        "\n"
        "Some unrelated prose here.\n"
        "\n"
        "```\n"
        'python = ">=3.10"\n'
        "```\n"
    )
    two_block_violations = _violations(
        _docs_records_for_text(Path("<docs-sample>"), two_block_sample)
    )
    assert two_block_violations, (
        f"the second, unmarked fenced block must still be flagged: {two_block_violations}"
    )
    assert {parsed for *_, parsed in two_block_violations} == {(3, 10)}, (
        "exemption leaked past its own closing fence into the second block "
        f"(expected only (3, 10) from block B): {two_block_violations}"
    )
