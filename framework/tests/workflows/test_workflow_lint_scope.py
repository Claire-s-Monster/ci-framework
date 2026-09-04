"""Tests guarding the scope and CI wiring of the `workflow-lint` pixi task.

Issue #279: ci.yml ran `python -m framework.workflow_lint` against a
hand-maintained six-file list, so 12 of the 18 files in `.github/workflows/`
were never linted - including `branch-policy.yml`, the exact file #255 found
a script injection in. `actionlint` (#255), `action-shellcheck` (#261) and
`yaml-lint` (#274) had each already been moved off hand-maintained lists;
this linter was the last one still reading from one.

These are the #255-shaped guards: derive both the linted set and the shipped
set from the filesystem and the manifest rather than hand-listing them, so a
future narrowing of scope (or a dropped CI invocation) fails a test instead
of silently shipping unlinted workflows.

Note for future maintainers: these are meta-tests about the build system, so
they parse `[tool.pixi.tasks]` and `pixi run` command strings directly. If
this project ever moves off pixi as its task runner, `load_tasks`,
`resolve_task_commands` and `PIXI_RUN_TASK_RE` here - and their twins in
`test_yaml_lint_scope.py` - must move with it. They will fail loudly rather
than pass vacuously, which is the intended direction, but the failure will
point here rather than at the real change.
"""

from __future__ import annotations

import re
from pathlib import Path

import tomllib
import yaml

from framework.workflow_lint import discover_workflow_files

PYPROJECT = Path("pyproject.toml")
CI_WORKFLOW = Path(".github/workflows/ci.yml")
WORKFLOWS_DIR = Path(".github/workflows")

# Task name from `pixi run [-e/--environment <env>] <task>`. Matched against a
# single logical line: YAML block/folded scalars are already resolved by the
# parser before these regexes see anything, and `logical_run_lines` rejoins
# shell `\` continuations, so the only text reaching this is plain shell.
PIXI_RUN_TASK_RE = re.compile(
    r"pixi\s+run\s+(?:(?:-e|--environment)\s+[\w.-]+\s+)?([\w.-]+)"
)

# A direct `python -m framework.workflow_lint` invocation, capturing whatever
# arguments follow it on the same logical line.
WORKFLOW_LINT_MODULE_RE = re.compile(
    r"python\s+-m\s+framework\.workflow_lint(?P<args>[^\n]*)"
)


def load_tasks() -> dict:
    """Load the [tool.pixi.tasks] table from pyproject.toml."""
    data = tomllib.loads(PYPROJECT.read_text())
    return data["tool"]["pixi"]["tasks"]


def task_cmd(task: dict | str) -> str | None:
    """Return the command string for a task, or None if it has no cmd."""
    if isinstance(task, str):
        return task
    if isinstance(task, dict):
        cmd = task.get("cmd")
        return cmd if isinstance(cmd, str) else None
    return None


def resolve_task_commands(
    tasks: dict, name: str, _seen: frozenset[str] = frozenset()
) -> list[str]:
    """Expand a pixi task into every concrete command it actually runs.

    Follows a single `pixi run -e <env> <target>` delegation transitively (the
    convention used by `workflow-lint` -> `workflow-lint-impl`), so callers see
    the leaf command rather than the one-line indirection. Cycles terminate
    via `_seen`.
    """
    if name in _seen or name not in tasks:
        return []
    _seen = _seen | {name}
    cmd = task_cmd(tasks[name])
    if cmd is None:
        return []
    match = PIXI_RUN_TASK_RE.match(cmd.strip())
    if match is not None and match.group(1) in tasks:
        return resolve_task_commands(tasks, match.group(1), _seen)
    return [cmd]


def iter_workflow_run_bodies(doc: object):
    """Yield every job step's `run:` body in a parsed workflow document."""
    if not isinstance(doc, dict):
        return
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield step["run"]


def logical_run_lines(body: str) -> list[str]:
    """Split a `run:` body into logical lines, rejoining shell continuations.

    A trailing `\\` splits one logical command across two physical lines,
    which would otherwise hide `pixi run workflow-lint` from a line-oriented
    regex - the very formatting the six-file invocation this replaced used.
    """
    return body.replace("\\\n", " ").splitlines()


def shipped_workflow_files() -> list[Path]:
    """Every workflow file GitHub would actually run from this repo.

    `.github/workflows/*.yml` and `*.yaml`, read off the filesystem rather
    than hand-listed. `python-ci-template.yml.template` is deliberately out of
    scope: it is scaffolding copied into consumer projects, not a workflow
    this repo runs, and it is not a standalone parseable workflow.

    The scan is deliberately flat rather than recursive. GitHub's workflow
    loader reads only files sitting directly in `.github/workflows/` and
    ignores subdirectories, so an `rglob` here would assert coverage of files
    that never run - and would then disagree with `discover_workflow_files`,
    which is flat for the same reason.
    """
    return sorted(
        path
        for path in WORKFLOWS_DIR.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def test_discovery_is_not_empty():
    """Vacuity guard: empty discovery would pass the coverage test for free."""
    assert shipped_workflow_files(), "no workflow files found - the walk is broken"
    assert discover_workflow_files(WORKFLOWS_DIR), (
        "framework.workflow_lint discovered no workflow files - discovery is broken"
    )


def test_workflow_lint_discovers_every_shipped_workflow():
    """`workflow_lint`'s discovery must cover every shipped workflow file."""
    discovered = {path.resolve() for path in discover_workflow_files(WORKFLOWS_DIR)}
    uncovered = [
        str(path)
        for path in shipped_workflow_files()
        if path.resolve() not in discovered
    ]
    assert not uncovered, (
        "these workflow files are outside framework.workflow_lint's discovery: "
        + "; ".join(sorted(uncovered))
    )


def test_workflow_lint_task_takes_no_file_list():
    """The `workflow-lint` task must lint by discovery, not by a file list."""
    tasks = load_tasks()
    assert "workflow-lint" in tasks, "'workflow-lint' task missing from pyproject.toml"
    commands = resolve_task_commands(tasks, "workflow-lint")
    assert commands, "'workflow-lint' resolved to no command - the parse is broken"
    for cmd in commands:
        match = WORKFLOW_LINT_MODULE_RE.search(cmd)
        assert match is not None, (
            f"'workflow-lint' does not invoke framework.workflow_lint: {cmd!r}"
        )
        args = match.group("args").strip()
        assert not args, (
            "'workflow-lint' passes an explicit file list to "
            f"framework.workflow_lint ({args!r}); pass nothing so discovery "
            f"walks {WORKFLOWS_DIR} (#279)"
        )


def test_workflow_lint_is_invoked_by_ci():
    """`workflow-lint` must actually be invoked by some job in ci.yml."""
    tasks = load_tasks()
    assert "workflow-lint" in tasks, "'workflow-lint' task missing from pyproject.toml"

    doc = yaml.safe_load(CI_WORKFLOW.read_text())
    invoked = False
    for body in iter_workflow_run_bodies(doc):
        for raw_line in logical_run_lines(body):
            line = raw_line.strip()
            if "pixi run" not in line:
                continue
            match = PIXI_RUN_TASK_RE.search(line)
            if match is not None and match.group(1) == "workflow-lint":
                invoked = True
    assert invoked, (
        "'workflow-lint' exists in pyproject.toml but no `run:` step in "
        f"{CI_WORKFLOW} invokes it via `pixi run [-e <env>] workflow-lint`"
    )


def test_ci_does_not_pass_a_hand_maintained_file_list():
    """No ci.yml step may pass explicit paths to framework.workflow_lint.

    The regression #279 records: the invocation named six files, all of which
    existed, so nothing looked stale - it was simply missing twelve others.
    """
    doc = yaml.safe_load(CI_WORKFLOW.read_text())
    body_text = "\n".join(
        line
        for body in iter_workflow_run_bodies(doc)
        for line in logical_run_lines(body)
    )
    offenders = [
        match.group("args").strip()
        for match in WORKFLOW_LINT_MODULE_RE.finditer(body_text)
        if match.group("args").strip()
    ]
    assert not offenders, (
        f"{CI_WORKFLOW} passes an explicit file list to framework.workflow_lint "
        f"({offenders!r}); lint by discovery instead (#279)"
    )
