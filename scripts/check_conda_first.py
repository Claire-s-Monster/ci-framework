"""Conda-first lock check (issue #386).

Policy: a dependency may come from PyPI only when conda-forge has no package
for it. This script scans a pixi.lock for PyPI-sourced packages and reports
those not matching an allowlist pattern.

Stdlib only, with a line-based parser instead of PyYAML: the runner's system
python3 is not guaranteed to ship PyYAML, and this runs before/outside any
pixi environment.

All inputs arrive via environment variables (never interpolated into code):
  CONDA_FIRST_MODE   off | warn | enforce
  CONDA_FIRST_ALLOW  comma/newline-separated fnmatch patterns on package name
  LOCK_FILE          path to pixi.lock (default: pixi.lock)
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys
from pathlib import Path

MODES = ("off", "warn", "enforce")

# A package entry opens with `- conda: <url>` or `- pypi: <url>` (pixi >= 0.2x
# lock v6/v7), or `- kind: pypi` in older locks.
_ENTRY_RE = re.compile(
    r"^(?P<indent>\s*)- (?P<key>conda|pypi|kind):\s*(?P<value>.*?)\s*$"
)
_NAME_RE = re.compile(r"^(?P<indent>\s*)name:\s*(?P<value>.+?)\s*$")


def normalize(name: str) -> str:
    """Case-insensitive; `_` and `.` are equivalent to `-`."""
    return re.sub(r"[_.]", "-", name.strip().lower())


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _name_from_url(url: str) -> str:
    """Best-effort package name when an entry has no `name:` field."""
    last = url.rstrip("/").rsplit("/", 1)[-1].split("@", 1)[0]
    last = re.sub(r"\.git$", "", last)
    return last.split("-", 1)[0] if re.search(r"\.(whl|tar\.gz|zip)$", last) else last


def parse_pypi_packages(text: str) -> list[str]:
    """Return the names of PyPI-sourced entries in the top-level `packages:`.

    Only the top-level `packages:` list is read: `environments:` also holds
    `- pypi: <url>` references that must not be counted twice.
    """
    names: list[str] = []
    in_packages = False
    entry: dict[str, object] | None = None

    def flush() -> None:
        if entry and entry["pypi"]:
            names.append(str(entry["name"] or _name_from_url(str(entry["url"]))))

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace() and not line.startswith("-"):
            # Top-level key: either opens or closes the `packages:` section.
            flush()
            entry = None
            in_packages = line.split(":", 1)[0] == "packages"
            continue
        if not in_packages:
            continue
        start = _ENTRY_RE.match(line)
        if start and (
            entry is None or len(start["indent"]) <= int(str(entry["indent"]))
        ):
            flush()
            key, value = start["key"], _unquote(start["value"])
            entry = {
                "indent": len(start["indent"]),
                "pypi": key == "pypi" or (key == "kind" and value == "pypi"),
                "url": value,
                "name": None,
            }
            continue
        field = _NAME_RE.match(line)
        if (
            field
            and entry is not None
            and len(field["indent"]) == int(str(entry["indent"])) + 2
        ):
            entry["name"] = _unquote(field["value"])
    flush()
    return names


def parse_allow(raw: str) -> list[str]:
    return [normalize(p) for p in re.split(r"[,\n]", raw) if p.strip()]


def is_allowed(name: str, patterns: list[str]) -> bool:
    norm = normalize(name)
    return any(fnmatch.fnmatchcase(norm, pattern) for pattern in patterns)


def _escape(value: str) -> str:
    """Escape a value for a GitHub workflow-command message."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def run(mode: str, allow: str, lock_file: str) -> int:
    if mode not in MODES:
        print(
            f"::error title=conda-first-check invalid::'{_escape(mode)}' is not a valid "
            f"conda-first-check value; use one of: {', '.join(MODES)}."
        )
        return 1
    if mode == "off":
        print("conda-first-check is off; skipping.")
        return 0
    lock = Path(lock_file)
    if not lock.is_file():
        print(
            f"::notice title=conda-first-check::No {lock_file} found; nothing to check."
        )
        return 0

    patterns = parse_allow(allow)
    # pixi.lock has one entry per platform wheel: dedupe by normalized name (first spelling wins).
    unique: dict[str, str] = {}
    for name in parse_pypi_packages(lock.read_text(encoding="utf-8")):
        unique.setdefault(normalize(name), name)
    offenders = [
        unique[key] for key in sorted(unique) if not is_allowed(unique[key], patterns)
    ]
    level = "error" if mode == "enforce" else "warning"
    for name in offenders:
        print(
            f"::{level} title=PyPI package in lock::'{_escape(name)}' is sourced from PyPI in "
            f"{lock_file}. Prefer the conda-forge package; if none exists, add its name to "
            "'conda-first-allow'. See https://github.com/Claire-s-Monster/ci-framework/issues/386"
        )
    if offenders and mode == "enforce":
        return 1
    print(f"conda-first-check: {len(offenders)} PyPI package(s) outside the allowlist.")
    return 0


def main() -> int:
    return run(
        os.environ.get("CONDA_FIRST_MODE", "warn"),
        os.environ.get("CONDA_FIRST_ALLOW", "hb-*"),
        os.environ.get("LOCK_FILE", "pixi.lock"),
    )


if __name__ == "__main__":
    sys.exit(main())
