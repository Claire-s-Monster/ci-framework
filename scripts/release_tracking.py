#!/usr/bin/env python3
"""Track issue fixes from the development branch through to a release tag (#394).

Two modes, chosen by RELEASE_TAG:

- unset or empty (fixed mode): run on a pull request merged into the
  development branch. Every same-repo issue named by a closing keyword in the
  PR title, body or commit messages is labelled ``fixed-in-development``, gets
  a comment carrying a hidden marker with the merge sha, and is closed as
  completed.
- set (released mode): run after a release is created. Every closed issue
  labelled ``fixed-in-development`` whose marker shas are all contained in the
  tag is relabelled ``released`` and told which tag shipped it.

Standard library only, so the reusable workflow can run this as an inline
heredoc without checking out ci-framework. The heredoc in
.github/workflows/reusable-release-tracking.yml must stay byte-identical to
this file (enforced by framework/tests/workflows/test_release_tracking.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

MARKER_RE = re.compile(r"<!-- release-tracking: fixed-in=([0-9a-f]{7,40}) pr=(\d+) -->")
KEYWORD_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<num>\d+)\b",
    re.IGNORECASE,
)
CONTAINED = ("ahead", "identical")
FIXED_COMMENT = (
    "Fixed on `{branch}` by #{pr} (merge {sha}).\n\n"
    "**Not yet in a tagged release.** This issue is relabelled `{released}` "
    "once a release tag contains the fix.\n\n{marker}"
)


class Client(Protocol):
    repo: str

    def request(self, method: str, path: str, body: Any = None) -> Any: ...

    def paginate(self, path: str) -> list[Any]: ...


class GitHub:
    """Minimal GitHub REST client for one repository."""

    def __init__(self, token: str, repo: str, api: str) -> None:
        if not api.startswith("https://"):
            raise ValueError(f"refusing non-https API URL: {api}")
        self.token = token
        self.repo = repo
        self.api = api.rstrip("/")

    def request(self, method: str, path: str, body: Any = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(  # noqa: S310 - https enforced in __init__
            f"{self.api}/repos/{self.repo}{path}", data=data, method=method
        )
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310
            raw = resp.read()
        return json.loads(raw) if raw else None

    def paginate(self, path: str) -> list[Any]:
        sep = "&" if "?" in path else "?"
        items: list[Any] = []
        page = 1
        while True:
            batch = self.request("GET", f"{path}{sep}per_page=100&page={page}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1


def closing_refs(text: str, repo: str) -> set[int]:
    """Issue numbers in ``repo`` named by a GitHub closing keyword in ``text``."""
    refs = set()
    for match in KEYWORD_RE.finditer(text):
        other = match.group("repo")
        if other is None or other.lower() == repo.lower():
            refs.add(int(match.group("num")))
    return refs


def marker(sha: str, pr: int) -> str:
    return f"<!-- release-tracking: fixed-in={sha} pr={pr} -->"


def marker_shas(comments: list[dict[str, Any]]) -> set[str]:
    return {
        m.group(1) for c in comments for m in MARKER_RE.finditer(c.get("body") or "")
    }


def is_released(statuses: dict[str, str | None]) -> bool:
    """True when every fix sha is contained in the tag.

    ``statuses`` maps each marker sha to the compare status of
    ``{sha}...{tag}``. ``ahead`` or ``identical`` means the tag contains the
    sha; None means the sha could not be compared.
    """
    return bool(statuses) and all(s in CONTAINED for s in statuses.values())


def _ignore(err: urllib.error.HTTPError, *codes: int) -> None:
    if err.code not in codes:
        raise err


def ensure_label(gh: Client, name: str, color: str, description: str) -> None:
    try:
        gh.request(
            "POST",
            "/labels",
            {"name": name, "color": color, "description": description},
        )
    except urllib.error.HTTPError as err:
        _ignore(err, 422)  # already exists


def remove_label(gh: Client, number: int, name: str) -> None:
    try:
        gh.request("DELETE", f"/issues/{number}/labels/{urllib.parse.quote(name)}")
    except urllib.error.HTTPError as err:
        _ignore(err, 404)  # not applied


def run_fixed(
    gh: Client, event: dict[str, Any], branch: str, fixed: str, released: str
) -> int:
    pr = event.get("pull_request") or {}
    if not pr.get("merged") or (pr.get("base") or {}).get("ref") != branch:
        print(f"Not a pull request merged into {branch}; nothing to do.")
        return 0
    number = pr["number"]
    sha = pr["merge_commit_sha"]
    texts = [pr.get("title") or "", pr.get("body") or ""]
    texts += [c["commit"]["message"] for c in gh.paginate(f"/pulls/{number}/commits")]
    issues = sorted(closing_refs("\n".join(texts), gh.repo))
    if not issues:
        print(f"PR #{number} names no issues to close.")
        return 0
    ensure_label(
        gh, fixed, "fbca04", "Fixed on the development branch, not yet released"
    )
    for num in issues:
        try:
            issue = gh.request("GET", f"/issues/{num}")
        except urllib.error.HTTPError as err:
            _ignore(err, 404, 410)
            print(f"::warning title=release-tracking::#{num} not found; skipping.")
            continue
        if "pull_request" in issue:
            print(f"#{num} is a pull request; skipping.")
            continue
        if sha not in marker_shas(gh.paginate(f"/issues/{num}/comments")):
            body = FIXED_COMMENT.format(
                branch=branch,
                pr=number,
                sha=sha,
                released=released,
                marker=marker(sha, number),
            )
            gh.request("POST", f"/issues/{num}/comments", {"body": body})
        gh.request("POST", f"/issues/{num}/labels", {"labels": [fixed]})
        remove_label(gh, num, released)  # a new, unreleased fix supersedes it
        if issue.get("state") != "closed":
            gh.request(
                "PATCH",
                f"/issues/{num}",
                {"state": "closed", "state_reason": "completed"},
            )
        print(f"#{num}: labelled {fixed} (fixed by #{number}, {sha}).")
    return 0


def compare_status(gh: Client, sha: str, tag: str) -> str | None:
    try:
        result = gh.request(
            "GET", f"/compare/{sha}...{urllib.parse.quote(tag, safe='')}"
        )
    except urllib.error.HTTPError as err:
        _ignore(err, 404)
        return None
    return result.get("status")


def run_released(gh: Client, tag: str, fixed: str, released: str, server: str) -> int:
    issues = gh.paginate(f"/issues?state=closed&labels={urllib.parse.quote(fixed)}")
    ensure_label(gh, released, "0e8a16", "Fix is contained in a tagged release")
    for issue in issues:
        if "pull_request" in issue:
            continue
        num = issue["number"]
        shas = marker_shas(gh.paginate(f"/issues/{num}/comments"))
        if not shas:
            print(
                f"::warning title=release-tracking::#{num} has no fix marker; skipping."
            )
            continue
        statuses = {sha: compare_status(gh, sha, tag) for sha in sorted(shas)}
        if not is_released(statuses):
            print(f"#{num}: not every fix is in {tag} ({statuses}).")
            continue
        url = f"{server}/{gh.repo}/releases/tag/{urllib.parse.quote(tag, safe='')}"
        gh.request(
            "POST", f"/issues/{num}/comments", {"body": f"Released in [{tag}]({url})."}
        )
        gh.request("POST", f"/issues/{num}/labels", {"labels": [released]})
        remove_label(gh, num, fixed)
        print(f"#{num}: released in {tag}.")
    return 0


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    gh = GitHub(
        os.environ["GITHUB_TOKEN"],
        repo,
        os.environ.get("GITHUB_API_URL") or "https://api.github.com",
    )
    # `or` rather than a get() default: workflow inputs arrive as empty strings.
    fixed = os.environ.get("FIXED_LABEL") or "fixed-in-development"
    released = os.environ.get("RELEASED_LABEL") or "released"
    tag = os.environ.get("RELEASE_TAG") or ""
    if tag:
        server = os.environ.get("GITHUB_SERVER_URL") or "https://github.com"
        return run_released(gh, tag, fixed, released, server)
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        event = json.load(fh)
    branch = os.environ.get("DEVELOPMENT_BRANCH") or "development"
    return run_fixed(gh, event, branch, fixed, released)


if __name__ == "__main__":
    sys.exit(main())
