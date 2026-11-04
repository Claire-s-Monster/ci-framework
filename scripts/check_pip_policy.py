"""Pip policy check (issue #399).

Policy: dependencies come from conda-forge via pixi. Two things bypass that and
are reported:
  a) [project.optional-dependencies] extras in pyproject.toml: pixi merges a
     same-named extra into the pixi feature as PyPI requirements.
  b) bare pip invocations in CI/build files (workflows, actions, shell
     scripts, Makefile, Dockerfile, pixi.toml, pyproject.toml). Editable
     installs of the project itself, comment lines and lines carrying the
     marker "pip-policy: allow" are exempt.

Stdlib only (tomllib needs python >= 3.11; on older pythons the check reports
that instead of crashing): the runner's system python3 is not guaranteed to
ship extra packages, and this runs before/outside any pixi environment.

All inputs arrive via environment variables (never interpolated into code):
  PIP_POLICY_MODE  off | warn | enforce
  PYPROJECT        path to pyproject.toml (default: pyproject.toml)
  REPO_ROOT        directory scanned for pip usage (default: .)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # python < 3.11
    tomllib = None  # type: ignore[assignment]

MODES = ("off", "warn", "enforce")
SKIP_DIRS = {".git", ".pixi", "node_modules", ".venv", "venv", "__pycache__"}
ISSUE = "https://github.com/Claire-s-Monster/ci-framework/issues/399"
MARKER = "pip-policy: allow"

_PIP_RE = re.compile(r"\bpip3?\s+install\b")
_EDITABLE_RE = re.compile(
    r"\bpython3?\s+-m\s+pip\s+install\s+(?:-[-\w]+(?:=\S+)?\s+)*(?:-e|--editable)(?=[\s=]|$)"
)
_TRAILING_COMMENT_RE = re.compile(r"\s#.*$")


def find_extras(text: str) -> list[str]:
    """Names in [project.optional-dependencies]; raises tomllib.TOMLDecodeError."""
    data = tomllib.loads(text)
    table = data.get("project", {}).get("optional-dependencies", {})
    return list(table) if isinstance(table, dict) else []


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """(first physical line number, line) with backslash continuations joined."""
    logical: list[tuple[int, str]] = []
    pending: tuple[int, str] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if pending is not None:
            number, line = pending[0], f"{pending[1]} {line.strip()}"
        if line.rstrip().endswith("\\") and not line.lstrip().startswith("#"):
            pending = (number, line.rstrip()[:-1].rstrip())
            continue
        pending = None
        logical.append((number, line))
    if pending is not None:
        logical.append(pending)
    return logical


def pip_violations_in_text(text: str) -> list[tuple[int, str]]:
    """(line number, stripped line) for each non-exempt pip invocation.

    Lines ending in a backslash are joined with the next one before matching;
    the reported number is that of the first physical line. A "#" preceded by
    whitespace starts a comment, which is ignored.
    """
    found: list[tuple[int, str]] = []
    for number, line in _logical_lines(text):
        stripped = line.strip()
        if stripped.startswith("#") or MARKER in line:
            continue
        code = _TRAILING_COMMENT_RE.sub("", line)
        if _PIP_RE.search(code) and not _EDITABLE_RE.search(code):
            found.append((number, stripped))
    return found


def _is_scanned(rel: Path) -> bool:
    name = rel.name
    if name in ("action.yml", "action.yaml"):
        return True
    if rel.parts[0] == ".github" and rel.suffix in (".yml", ".yaml"):
        return True
    if rel.suffix in (".sh", ".bash"):
        return True
    return name in ("Makefile", "Dockerfile", "pixi.toml", "pyproject.toml") or (
        name.startswith("Dockerfile.")
    )


def iter_scanned_files(root: Path) -> list[Path]:
    """Files under root that may hold pip usage, skipping vendored/env dirs."""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in SKIP_DIRS or p == "site-packages" for p in rel.parts):
            continue
        if path.is_file() and _is_scanned(rel):
            files.append(path)
    return files


def _escape(value: str) -> str:
    """Escape a value for a GitHub workflow-command message."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Escape a value for a workflow-command property (file=, line=, title=)."""
    return _escape(value).replace(":", "%3A").replace(",", "%2C")


def _extras_violations(pyproject: str, level: str) -> int:
    path = Path(pyproject)
    if not path.is_file():
        print(
            f"::notice title=pip-policy-check::No {pyproject} found; skipping extras rule."
        )
        return 0
    try:
        extras = find_extras(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(
            f"::{level} title=pip-policy-check invalid toml::Cannot parse "
            f"{_escape(pyproject)}: {_escape(str(exc))}"
        )
        return 1
    for name in extras:
        print(
            f"::{level} title=optional-dependencies extra::Extra '{_escape(name)}' in "
            f"{_escape(pyproject)} is merged by pixi into the pixi feature as PyPI "
            "requirements; declare these with conda-forge in a pixi feature instead. "
            f"See {ISSUE}"
        )
    return len(extras)


def _pip_violation_count(repo_root: str, level: str) -> int:
    root = Path(repo_root)
    count = 0
    for path in iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        for number, _ in pip_violations_in_text(text):
            count += 1
            print(
                f"::{level} file={_escape_property(rel)},line={number},title=bare pip "
                "install::Bare pip installs bypass the conda-forge solve. Use a pixi "
                "dependency instead, or an editable install of the project "
                "(python -m pip install -e .); to keep a deliberate one, append "
                f"'# {MARKER}' to the line. See {ISSUE}"
            )
    return count


def run(mode: str, pyproject: str, repo_root: str) -> int:
    if mode not in MODES:
        print(
            f"::error title=pip-policy-check invalid::'{_escape(mode)}' is not a valid "
            f"pip-policy-check value; use one of: {', '.join(MODES)}."
        )
        return 1
    if mode == "off":
        print("pip-policy-check is off; skipping.")
        return 0
    level = "error" if mode == "enforce" else "warning"
    if tomllib is None:
        print(
            f"::{level} title=pip-policy-check python::pip-policy-check needs python "
            f">= 3.11 (tomllib); found {_escape(sys.version.split()[0])}. See {ISSUE}"
        )
        return 1 if mode == "enforce" else 0
    total = _extras_violations(pyproject, level) + _pip_violation_count(
        repo_root, level
    )
    if total and mode == "enforce":
        return 1
    print(f"pip-policy-check: {total} violation(s).")
    return 0


def main() -> int:
    return run(
        os.environ.get("PIP_POLICY_MODE", "off"),
        os.environ.get("PYPROJECT", "pyproject.toml"),
        os.environ.get("REPO_ROOT", "."),
    )


if __name__ == "__main__":
    sys.exit(main())
