#!/usr/bin/env python3
"""Render the package changes of a ``pixi update --json`` run as a PR body (#387).

Reads the JSON that ``pixi update --json`` wrote (path in UPDATE_JSON) and prints
markdown: a summary line, then one table per environment with the columns
package | platform(s) | old -> new | conda/pypi. Identical changes across
platforms collapse into one row listing the platforms. With nothing to report it
prints a single ``No package changes.`` line.

Schema, as observed from ``pixi update --json --dry-run``:

    {"version": 1,
     "environment": {<env>: {<platform>: [
         {"name": ..., "before": <package>|null, "after": <package>|null,
          "type": "conda"|"pypi"}]}}}

``before`` is null for an added package and ``after`` is null for a removed one.
A conda package carries its location in ``conda`` (a channel URL whose filename
is ``name-version-build``); a version is never a separate field. A pypi package
is read from an explicit ``version`` field, else from its ``pypi`` URL filename.

Standard library only, so the reusable workflow can run this as an inline
heredoc without checking out ci-framework. The heredoc in
.github/workflows/reusable-pixi-lock-refresh.yml must stay byte-identical to
this file (enforced by framework/tests/workflows/test_pixi_lock_refresh.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

EMPTY = "No package changes."
DASH = "—"
ARROW = "→"
KINDS = ("added", "removed", "upgraded", "downgraded", "rebuilt")
_CONDA_SUFFIXES = (".conda", ".tar.bz2")
_SDIST_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".zip")
_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def _filename(url: str) -> str:
    return url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]


def _strip_suffix(name: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _conda_version(url: str) -> tuple[str, str]:
    """(version, build) from a conda URL filename ``name-version-build.ext``."""
    stem = _strip_suffix(_filename(url), _CONDA_SUFFIXES)
    parts = stem.rsplit("-", 2)
    return (parts[1], parts[2]) if len(parts) == 3 else (stem, "")


def _pypi_version(url: str) -> str:
    """Version from a wheel (``name-version-tags.whl``) or sdist filename."""
    name = _filename(url)
    if name.endswith(".whl"):
        parts = name.split("-")
        return parts[1] if len(parts) > 1 else name
    stem = _strip_suffix(name, _SDIST_SUFFIXES)
    return stem.rsplit("-", 1)[1] if "-" in stem else stem


def describe(package: dict[str, Any]) -> tuple[str, str]:
    """(version, build) of one side of a change; build is empty for pypi."""
    if "conda" in package:
        version, build = _conda_version(str(package["conda"]))
        return str(package.get("version") or version), build
    if package.get("version"):
        return str(package["version"]), ""
    return _pypi_version(str(package.get("pypi") or "")), ""


def _version_key(version: str) -> list[tuple[int, int, str]]:
    return [
        (0, int(token), "") if token.isdigit() else (-1, 0, token.lower())
        for token in _TOKEN_RE.findall(version)
    ]


def compare(old: str, new: str) -> int:
    """-1, 0 or 1. Numeric-aware; a missing trailing part counts as zero."""
    a, b = _version_key(old), _version_key(new)
    pad = (0, 0, "")
    size = max(len(a), len(b))
    a += [pad] * (size - len(a))
    b += [pad] * (size - len(b))
    return (a > b) - (a < b)


def _label(version: str, build: str, show_build: bool) -> str:
    return f"{version} ({build})" if show_build and build else version


def _source(entry: dict[str, Any]) -> str:
    kind = entry.get("type")
    if kind in ("conda", "pypi"):
        return str(kind)
    side = entry.get("after") or entry.get("before") or {}
    return "conda" if "conda" in side else "pypi"


def classify(entry: dict[str, Any]) -> tuple[str, str, str] | None:
    """(kind, old label, new label) for one change, or None when nothing changed."""
    before, after = entry.get("before"), entry.get("after")
    if before == after:
        return None
    if before is None:
        return "added", DASH, describe(after)[0]
    if after is None:
        return "removed", describe(before)[0], DASH
    (old_v, old_b), (new_v, new_b) = describe(before), describe(after)
    order = compare(old_v, new_v)
    kind = "rebuilt" if order == 0 else ("upgraded" if order < 0 else "downgraded")
    same = order == 0
    return kind, _label(old_v, old_b, same), _label(new_v, new_b, same)


def collect(
    data: dict[str, Any],
) -> dict[str, dict[tuple[str, str, str, str, str], set[str]]]:
    """Per environment, map (name, source, old, new, kind) -> platforms."""
    result: dict[str, dict[tuple[str, str, str, str, str], set[str]]] = {}
    environments = data.get("environment") or {}
    for env, platforms in environments.items():
        grouped: dict[tuple[str, str, str, str, str], set[str]] = {}
        for platform, entries in (platforms or {}).items():
            for entry in entries or []:
                outcome = classify(entry)
                if outcome is None:
                    continue
                kind, old, new = outcome
                key = (str(entry["name"]), _source(entry), old, new, kind)
                grouped.setdefault(key, set()).add(platform)
        if grouped:
            result[env] = grouped
    return result


def render(data: dict[str, Any]) -> str:
    """Markdown PR body for a parsed ``pixi update --json`` payload."""
    changes = collect(data)
    if not changes:
        return EMPTY + "\n"
    counts = dict.fromkeys(KINDS, 0)
    for grouped in changes.values():
        for key in grouped:
            counts[key[4]] += 1
    lines = [
        "Refreshes `pixi.lock` with `pixi update`. Rows: "
        + ", ".join(f"{counts[kind]} {kind}" for kind in KINDS)
        + ".",
    ]
    for env in sorted(changes):
        lines += ["", f"### {env}", ""]
        lines += ["| Package | Platform(s) | Old " + ARROW + " New | Source |"]
        lines += ["|---|---|---|---|"]
        for key in sorted(
            changes[env], key=lambda k: (k[0].lower(), sorted(changes[env][k]), k)
        ):
            name, source, old, new, _ = key
            platforms = ", ".join(sorted(changes[env][key]))
            lines.append(f"| `{name}` | {platforms} | {old} {ARROW} {new} | {source} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    path = os.environ.get("UPDATE_JSON", "")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        data = json.loads(text) if text.strip() else {}
    except (OSError, ValueError) as err:
        print(f"::error title=pixi-lock-diff::cannot read UPDATE_JSON '{path}': {err}")
        return 1
    sys.stdout.write(render(data if isinstance(data, dict) else {}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
