"""Behavioural test: `Check if sync needed` in sync-main-to-development.yml.

The real `run:` script of step id `check` is executed with bash against
throwaway git repositories (a bare "origin" plus a clone), and the `skip=`
line it writes to `$GITHUB_OUTPUT` is asserted.

After a development->main merge, main is ahead of development only by a merge
commit whose tree equals development's tree. Opening a sync PR for that is
pointless; the next content-changing push to main (the release commit) syncs
everything. No network and no GPG are used.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

if shutil.which("git") is None or shutil.which("bash") is None:
    pytest.skip("git and bash are required", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sync-main-to-development.yml"

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def check_script() -> str:
    """The `run:` text of the step with id `check`."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if step.get("id") == "check":
                return step["run"]
    raise AssertionError("no step with id 'check' found")


def git(cwd: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603


def commit_file(cwd: Path, name: str, text: str) -> None:
    (cwd / name).write_text(text, encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "commit", "-m", f"change {name}")


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A clone whose main and development both start at one shared commit."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    git(tmp_path, "-c", "init.defaultBranch=main", "init", "--bare", str(origin))
    git(tmp_path, "-c", "init.defaultBranch=main", "init", str(work))
    git(work, "remote", "add", "origin", str(origin))
    commit_file(work, "base.txt", "base\n")
    git(work, "branch", "-M", "main")
    git(work, "branch", "development")
    return work


def run_check(work: Path, tmp_path: Path, script: str | None = None) -> str:
    """Push both branches, fetch, run the script, return the `skip=` value."""
    git(work, "push", "-f", "origin", "main", "development")
    git(work, "fetch", "origin")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    subprocess.run(  # noqa: S603
        ["bash", "-e", "-c", script or check_script()],  # noqa: S607
        cwd=work,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        check=True,
        capture_output=True,
    )
    lines = [
        ln
        for ln in output.read_text(encoding="utf-8").splitlines()
        if ln.startswith("skip=")
    ]
    assert len(lines) == 1, lines
    return lines[0].removeprefix("skip=")


def test_same_sha_skips(clone: Path, tmp_path: Path) -> None:
    assert run_check(clone, tmp_path) == "true"


def test_main_ahead_only_by_merge_commit_skips(clone: Path, tmp_path: Path) -> None:
    """The case the tree-equality check fixes.

    development has a commit main lacks; merging it into main with --no-ff
    leaves main ahead only by the merge commit (identical tree). The previous
    script counted that merge commit and yielded skip=false, so this case is
    the self-test proving the guard can fail.
    """
    git(clone, "checkout", "development")
    commit_file(clone, "feature.txt", "feature\n")
    git(clone, "checkout", "main")
    git(clone, "merge", "--no-ff", "-m", "merge development", "development")
    assert run_check(clone, tmp_path) == "true"


def test_main_with_new_content_commit_does_not_skip(
    clone: Path, tmp_path: Path
) -> None:
    git(clone, "checkout", "main")
    commit_file(clone, "CHANGELOG.md", "release\n")
    assert run_check(clone, tmp_path) == "false"


def test_development_ahead_of_main_skips(clone: Path, tmp_path: Path) -> None:
    git(clone, "checkout", "development")
    commit_file(clone, "feature.txt", "feature\n")
    assert run_check(clone, tmp_path) == "true"
