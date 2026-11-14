"""Guard: every third-party `uses:` ref is pinned to a full 40-hex commit SHA.

Tags are mutable, so an unpinned third-party action can change under us. The
original ref is kept as a trailing comment (`@<sha> # v7`) the way Dependabot
writes it, and that comment is required so a bare SHA cannot slip in. Local
refs (./) and first-party Claire-s-Monster refs are exempt: the latter are
bumped by release-please and must stay as tags.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^\s'\"#]+)")
SHA_RE = re.compile(r"@[0-9a-f]{40}$")
VERSION_COMMENT_RE = re.compile(r"[ \t]+#[ \t]*(?:v\d|release/)")
FIRST_PARTY_OWNER = "claire-s-monster/"


def _scanned_files() -> list[Path]:
    files: set[Path] = set()
    for ext in ("yml", "yaml"):
        files |= set((ROOT / ".github" / "workflows").glob(f"*.{ext}"))
        files |= set((ROOT / "actions").rglob(f"action.{ext}"))
        files |= set((ROOT / ".github" / "actions").rglob(f"action.{ext}"))
    return sorted(files)


def _is_first_party_or_local(ref: str) -> bool:
    return ref.startswith("./") or ref.lower().startswith(FIRST_PARTY_OWNER)


def is_unpinned_third_party(ref: str) -> bool:
    """True if `ref` is a third-party action ref not pinned to a 40-hex SHA."""
    if _is_first_party_or_local(ref):
        return False
    return SHA_RE.search(ref) is None


def lacks_version_comment(line: str) -> bool:
    """True if a SHA-pinned third-party `uses:` line has no `# vN`/`# release/` comment."""
    match = USES_RE.match(line)
    if not match or _is_first_party_or_local(match.group(1)):
        return False
    if SHA_RE.search(match.group(1)) is None:
        return False
    return VERSION_COMMENT_RE.match(line[match.end() :]) is None


def _uses_lines(files: list[Path]) -> list[tuple[Path, int, str]]:
    found = []
    for path in files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if USES_RE.match(line):
                found.append((path, lineno, line))
    return found


def _third_party_refs(files: list[Path]) -> list[tuple[Path, int, str]]:
    found = []
    for path, lineno, line in _uses_lines(files):
        match = USES_RE.match(line)
        if match:
            found.append((path, lineno, match.group(1)))
    return found


def test_classifier_self_test():
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"  # pragma: allowlist secret
    assert is_unpinned_third_party("actions/checkout@v7")
    assert is_unpinned_third_party("github/codeql-action/init@v4")
    assert is_unpinned_third_party(f"actions/checkout@{sha[:39]}")
    assert not is_unpinned_third_party(f"actions/checkout@{sha}")
    assert not is_unpinned_third_party("./actions/x")
    assert not is_unpinned_third_party("Claire-s-Monster/ci-framework/actions/y@v4.2.1")
    # The line regex must capture the ref but ignore the trailing comment.
    line = f"      - uses: actions/checkout@{sha} # v7"
    assert USES_RE.match(line).group(1) == f"actions/checkout@{sha}"
    two_space = f"      - uses: actions/checkout@{sha}  # v7"
    assert USES_RE.match(two_space).group(1) == f"actions/checkout@{sha}"
    assert USES_RE.match("#   uses: actions/checkout@v7") is None


def test_version_comment_self_test():
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"  # pragma: allowlist secret
    assert lacks_version_comment(f"      - uses: actions/checkout@{sha}")
    assert lacks_version_comment(f"      - uses: actions/checkout@{sha}  # latest")
    assert not lacks_version_comment(f"      - uses: actions/checkout@{sha}  # v7")
    assert not lacks_version_comment(
        f"      - uses: pypa/gh-action-pypi-publish@{sha}  # release/v1"
    )
    assert not lacks_version_comment("      - uses: ./actions/x")
    assert not lacks_version_comment("      - uses: actions/checkout@v7")


def test_scan_examines_files_and_refs():
    files = _scanned_files()
    refs = _third_party_refs(files)
    assert len(files) > 10
    assert (
        sum(1 for _, _, r in refs if is_unpinned_third_party(r) or SHA_RE.search(r))
        > 100
    )


def test_all_third_party_actions_are_sha_pinned():
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {ref}"
        for path, lineno, ref in _third_party_refs(_scanned_files())
        if is_unpinned_third_party(ref)
    ]
    assert not offenders, "Unpinned third-party actions:\n" + "\n".join(offenders)


def test_sha_pins_carry_version_comment():
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}"
        for path, lineno, line in _uses_lines(_scanned_files())
        if lacks_version_comment(line)
    ]
    assert not offenders, "SHA pins without a version comment:\n" + "\n".join(offenders)
