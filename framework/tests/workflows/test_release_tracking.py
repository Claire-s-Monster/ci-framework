"""Release tracking labels issues fixed-in-development, then released (#394).

`Closes #N` only fires for merges into the default branch, so issues fixed on
`development` stay unlabelled until a release. scripts/release_tracking.py
labels them `fixed-in-development` on merge (with a hidden sha marker comment)
and swaps to `released` once a tag contains every marker sha. The script is
loaded here by path and driven with an in-memory GitHub fake.
reusable-release-tracking.yml inlines it as a `python3 - <<'PY'` heredoc, so a
test pins the heredoc to the standalone file, and structural tests keep the
pull_request_target caller free of any checkout.
"""

from __future__ import annotations

import importlib.util
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPT = Path("scripts/release_tracking.py")
REUSABLE = Path(".github/workflows/reusable-release-tracking.yml")
CALLER = Path(".github/workflows/release-tracking.yml")
RELEASE_PLEASE = Path(".github/workflows/release-please.yml")
STEP_NAME = "Track issue fixes"
HEREDOC_OPEN = "python3 - <<'PY'\n"
HEREDOC_CLOSE = "\nPY\n"

_spec = importlib.util.spec_from_file_location("release_tracking", SCRIPT)
assert _spec is not None and _spec.loader is not None
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)

REPO = "Claire-s-Monster/ci-framework"
FIXED = "fixed-in-development"
RELEASED = "released"
SHA = "a" * 40
SHA2 = "b" * 40


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", {}, None)  # type: ignore[arg-type]


class FakeGitHub:
    """In-memory stand-in for the REST client; records every call."""

    def __init__(self) -> None:
        self.repo = REPO
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.commits: list[str] = []
        self.labels: set[str] = set()
        self.compare: dict[str, str] = {}
        self.calls: list[tuple[str, str, Any]] = []

    def add_issue(self, num: int, state: str = "open", labels=(), **extra) -> None:
        self.issues[num] = {
            "number": num,
            "state": state,
            "labels": [{"name": n} for n in labels],
            **extra,
        }
        self.comments.setdefault(num, [])

    def request(self, method: str, path: str, body: Any = None) -> Any:
        self.calls.append((method, path, body))
        parts = path.strip("/").split("/")
        if method == "POST" and path == "/labels":
            if body["name"] in self.labels:
                raise _http_error(422)
            self.labels.add(body["name"])
            return body
        if parts[0] == "compare":
            sha = urllib.parse.unquote(parts[1]).split("...")[0]
            if sha not in self.compare:
                raise _http_error(404)
            return {"status": self.compare[sha]}
        num = int(parts[1])
        if num not in self.issues:
            raise _http_error(404)
        issue = self.issues[num]
        if method == "GET":
            return issue
        if method == "PATCH":
            issue.update(state=body["state"], state_reason=body["state_reason"])
            return issue
        if parts[2] == "comments":
            self.comments[num].append({"body": body["body"]})
            return None
        names = [x["name"] for x in issue["labels"]]
        if method == "POST":
            names += [n for n in body["labels"] if n not in names]
        else:
            name = urllib.parse.unquote(parts[3])
            if name not in names:
                raise _http_error(404)
            names.remove(name)
        issue["labels"] = [{"name": n} for n in names]
        return None

    def paginate(self, path: str) -> list[Any]:
        self.calls.append(("GET", path, None))
        if path.startswith("/pulls/"):
            return [{"commit": {"message": m}} for m in self.commits]
        if path.startswith("/issues?"):
            return [
                i
                for i in self.issues.values()
                if i["state"] == "closed" and FIXED in [x["name"] for x in i["labels"]]
            ]
        return self.comments[int(path.split("/")[2])]

    def label_names(self, num: int) -> list[str]:
        return [x["name"] for x in self.issues[num]["labels"]]

    def writes(self) -> list[tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] != "GET"]


def _event(body: str = "", base: str = "development", merged: bool = True) -> dict:
    return {
        "pull_request": {
            "number": 50,
            "title": "fix: thing",
            "body": body,
            "merged": merged,
            "merge_commit_sha": SHA,
            "base": {"ref": base},
        }
    }


def _fixed(gh: FakeGitHub, event: dict) -> int:
    return rt.run_fixed(gh, event, "development", FIXED, RELEASED)


def _released(gh: FakeGitHub, tag: str = "v4.1.0") -> int:
    return rt.run_released(gh, tag, FIXED, RELEASED, "https://github.com")


def _marker_comment(sha: str, pr: int = 50) -> dict:
    return {"body": f"Fixed.\n\n{rt.marker(sha, pr)}"}


# --- closing_refs -----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Closes #3",
        "closes #3",
        "Closed #3",
        "fix #3",
        "fixes #3",
        "Fixed #3",
        "resolve #3",
        "Resolves #3",
        "resolved #3",
        "Fixes: #3",
        "Fixes:  #3",
    ],
)
def test_closing_keywords_match(text):
    assert rt.closing_refs(text, REPO) == {3}


def test_same_repo_full_form_is_included_case_insensitively():
    assert rt.closing_refs("Closes Claire-s-Monster/ci-framework#4", REPO) == {4}
    assert rt.closing_refs("Closes claire-s-monster/CI-Framework#4", REPO) == {4}


def test_other_repo_reference_is_excluded():
    assert rt.closing_refs("Closes other/repo#5", REPO) == set()


@pytest.mark.parametrize("text", ["fixture #6", "prefix#7", "#8", "closes#9"])
def test_non_closing_text_is_not_matched(text):
    assert rt.closing_refs(text, REPO) == set()


def test_multiple_refs_in_one_text():
    text = "Closes #1, fixes #2\nResolves other/repo#9 and resolved #3"
    assert rt.closing_refs(text, REPO) == {1, 2, 3}


# --- markers / is_released --------------------------------------------------


def test_marker_round_trips_through_marker_shas():
    comments = [
        {"body": f"text\n\n{rt.marker(SHA, 50)}"},
        {"body": rt.marker("abc1234", 7)},
    ]
    assert rt.marker_shas(comments) == {SHA, "abc1234"}


def test_marker_shas_ignores_comments_without_body():
    assert rt.marker_shas([{"body": None}, {}, {"body": "no marker here"}]) == set()


def test_is_released_empty_is_false():
    assert rt.is_released({}) is False


def test_is_released_all_contained():
    assert rt.is_released({SHA: "ahead", SHA2: "identical"}) is True


@pytest.mark.parametrize("bad", ["behind", "diverged", None])
def test_is_released_any_uncontained_is_false(bad):
    assert rt.is_released({SHA: "ahead", SHA2: bad}) is False


# --- run_fixed --------------------------------------------------------------


def _fixed_setup() -> FakeGitHub:
    gh = FakeGitHub()
    gh.add_issue(10, labels=[RELEASED])
    gh.add_issue(11)
    gh.commits = ["feat: other\n\nFixes #11"]
    return gh


def test_fixed_labels_comments_and_closes_each_issue():
    gh = _fixed_setup()
    assert _fixed(gh, _event("Closes #10")) == 0
    for num in (10, 11):
        assert len(rt.marker_shas(gh.comments[num])) == 1
        assert rt.marker_shas(gh.comments[num]) == {SHA}
        assert FIXED in gh.label_names(num)
        assert gh.issues[num]["state"] == "closed"
        assert gh.issues[num]["state_reason"] == "completed"
    assert ("DELETE", f"/issues/10/labels/{RELEASED}", None) in gh.calls
    assert ("DELETE", f"/issues/11/labels/{RELEASED}", None) in gh.calls
    assert RELEASED not in gh.label_names(10)
    assert FIXED in gh.labels


def test_fixed_is_idempotent():
    gh = _fixed_setup()
    _fixed(gh, _event("Closes #10"))
    _fixed(gh, _event("Closes #10"))
    assert len(gh.comments[10]) == 1
    assert len(gh.comments[11]) == 1


def test_fixed_already_closed_issue_is_not_patched():
    gh = FakeGitHub()
    gh.add_issue(10, state="closed")
    _fixed(gh, _event("Closes #10"))
    assert not [c for c in gh.calls if c[0] == "PATCH"]
    assert FIXED in gh.label_names(10)


def test_fixed_skips_pull_request_refs():
    gh = FakeGitHub()
    gh.add_issue(10, pull_request={"url": "x"})
    _fixed(gh, _event("Closes #10"))
    assert gh.comments[10] == []
    assert not [c for c in gh.writes() if c[1].startswith("/issues/10")]


def test_fixed_missing_issue_warns_and_continues(capsys):
    gh = FakeGitHub()
    gh.add_issue(11)
    assert _fixed(gh, _event("Closes #10 and fixes #11")) == 0
    assert "::warning" in capsys.readouterr().out
    assert FIXED in gh.label_names(11)


def test_fixed_unmerged_pr_makes_no_api_calls():
    gh = _fixed_setup()
    _fixed(gh, _event("Closes #10", merged=False))
    assert gh.calls == []


def test_fixed_other_base_branch_makes_no_api_calls():
    gh = _fixed_setup()
    _fixed(gh, _event("Closes #10", base="main"))
    assert gh.calls == []


def test_fixed_without_refs_creates_no_label():
    gh = FakeGitHub()
    _fixed(gh, _event("Nothing to close here"))
    assert gh.writes() == []
    assert gh.labels == set()


# --- run_released -----------------------------------------------------------


def _released_issue(gh: FakeGitHub, num: int, *shas: str) -> None:
    gh.add_issue(num, state="closed", labels=[FIXED])
    gh.comments[num] = [_marker_comment(s) for s in shas]


def test_released_relabels_and_comments_when_tag_contains_fix():
    gh = FakeGitHub()
    _released_issue(gh, 10, SHA)
    gh.compare[SHA] = "ahead"
    _released(gh)
    assert RELEASED in gh.label_names(10)
    assert FIXED not in gh.label_names(10)
    assert "v4.1.0" in gh.comments[10][-1]["body"]


def test_released_leaves_issue_when_any_fix_is_behind():
    gh = FakeGitHub()
    _released_issue(gh, 10, SHA, SHA2)
    gh.compare.update({SHA: "ahead", SHA2: "behind"})
    _released(gh)
    assert gh.label_names(10) == [FIXED]
    assert len(gh.comments[10]) == 2


def test_released_leaves_issue_when_compare_404s():
    gh = FakeGitHub()
    _released_issue(gh, 10, SHA)
    _released(gh)
    assert gh.label_names(10) == [FIXED]


def test_released_without_marker_warns_and_leaves_issue(capsys):
    gh = FakeGitHub()
    _released_issue(gh, 10)
    _released(gh)
    assert "::warning" in capsys.readouterr().out
    assert gh.label_names(10) == [FIXED]


def test_released_url_quotes_the_tag():
    gh = FakeGitHub()
    _released_issue(gh, 10, SHA)
    gh.compare[SHA] = "identical"
    _released(gh, tag="v1/2 x")
    body = gh.comments[10][-1]["body"]
    assert f"https://github.com/{REPO}/releases/tag/v1%2F2%20x" in body


# --- sync with the reusable workflow ---------------------------------------


def _inline_script() -> str:
    """Heredoc body of the track step, wrapper stripped."""
    doc = yaml.safe_load(REUSABLE.read_text())
    steps = doc["jobs"]["track"]["steps"]
    run = next(s for s in steps if s.get("name") == STEP_NAME)["run"]
    assert run.startswith(HEREDOC_OPEN), (
        "run must start with a quoted-heredoc python3 -"
    )
    assert run.endswith(HEREDOC_CLOSE), "run must end with the PY terminator"
    return run[len(HEREDOC_OPEN) : -len(HEREDOC_CLOSE)] + "\n"


def test_inline_script_extraction_is_not_vacuous():
    body = _inline_script()
    assert body.strip()
    assert "def run_released" in body


def test_inline_script_matches_standalone_script():
    assert _inline_script() == SCRIPT.read_text()


def test_step_passes_inputs_via_env_only():
    doc = yaml.safe_load(REUSABLE.read_text())
    step = next(s for s in doc["jobs"]["track"]["steps"] if s.get("name") == STEP_NAME)
    assert step["env"]["RELEASE_TAG"] == "${{ inputs.tag }}"
    assert step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
    assert "${{" not in step["run"]


# --- structure --------------------------------------------------------------


@pytest.mark.parametrize("path", [CALLER, REUSABLE])
def test_no_checkout_in_pull_request_target_path(path):
    doc = yaml.safe_load(path.read_text())
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            assert "actions/checkout" not in str(step.get("uses", ""))


def test_caller_triggers_on_pull_request_target_closed_for_development():
    doc = yaml.safe_load(CALLER.read_text())
    trigger = doc.get(True) or doc["on"]
    prt = trigger["pull_request_target"]
    assert prt["types"] == ["closed"]
    assert prt["branches"] == ["development"]


def test_release_please_calls_release_tracking_with_tag_name():
    doc = yaml.safe_load(RELEASE_PLEASE.read_text())
    job = doc["jobs"]["release-tracking"]
    assert job["needs"] == "release-please"
    assert "release_created == 'true'" in job["if"]
    assert job["with"]["tag"] == "${{ needs.release-please.outputs.tag_name }}"
    assert job["permissions"]["issues"] == "write"
