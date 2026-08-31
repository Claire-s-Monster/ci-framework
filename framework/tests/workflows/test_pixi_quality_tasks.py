"""Tests for pixi task quality-gate conventions in pyproject.toml.

These tests validate that the `quality` aggregate task and its members
follow the env-self-contained delegation convention used throughout this
project (a user-facing task like `lint` delegates to `pixi run -e quality
lint-impl`, rather than being a bare command that only works if the caller
happens to pass `-e quality`). A bare command silently falls back to the
default env and fails with "command not found" instead of running the
intended tool.
"""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

PYPROJECT = Path("pyproject.toml")

# Env-delegation guards accept both the short (`-e`) and long
# (`--environment`) pixi flag forms, and tolerate extra whitespace.
ENV_DELEGATION_RE = re.compile(r"^pixi\s+run\s+(?:-e|--environment)\s+[\w.-]+\s")
QUALITY_ENV_DELEGATION_RE = re.compile(
    r"^pixi\s+run\s+(?:-e|--environment)\s+quality(?:\s|$)"
)


def load_tasks() -> dict:
    """Load the [tool.pixi.tasks] table from pyproject.toml."""
    data = tomllib.loads(PYPROJECT.read_text())
    return data["tool"]["pixi"]["tasks"]


def task_depends_on(task: dict | str) -> list[str]:
    """Return the depends-on list for a task, or an empty list if none."""
    if isinstance(task, dict):
        depends = task.get("depends-on", [])
        return list(depends) if depends else []
    return []


def task_cmd(task: dict | str) -> str | None:
    """Return the command string for a task, or None if it has no cmd."""
    if isinstance(task, str):
        return task
    if isinstance(task, dict):
        cmd = task.get("cmd")
        return cmd if isinstance(cmd, str) else None
    return None


class TestQualityGateTasksAreEnvSelfContained:
    """Validate that the `quality` aggregate and its members are env-self-contained.

    Follows the convention seen in `lint`/`lint-impl` and
    `typecheck`/`typecheck-impl`: a user-facing task delegates to an
    `-impl` task run in the `quality` env via `pixi run -e quality
    <name>-impl`, so it works from any starting env. `format-check` used
    to break this convention as a bare `ruff format --check framework/`
    command, which exits 127 "command not found" unless the caller
    happens to pass `-e quality` themselves.
    """

    def test_quality_task_was_actually_found(self):
        """Vacuity guard: a silently-empty parse would make the other tests trivially pass."""
        tasks = load_tasks()
        assert tasks, "Parsed pixi tasks table is empty — parse likely failed silently"
        assert "quality" in tasks, "'quality' task not found in pyproject.toml"
        depends_on = task_depends_on(tasks["quality"])
        assert len(depends_on) >= 4, (
            f"'quality' depends-on has only {len(depends_on)} entries "
            f"({depends_on!r}) — expected at least 4"
        )

    def test_quality_aggregate_includes_format_check(self):
        """`format-check` must be a member of the mandatory pre-commit `quality` gate.

        Without this, formatting was silently absent from the mandatory
        pre-commit gate: `pixi run quality` could pass while unformatted
        code slipped through, since nothing in the aggregate ever ran
        `ruff format --check`.
        """
        tasks = load_tasks()
        depends_on = task_depends_on(tasks["quality"])
        assert "format-check" in depends_on, (
            f"'quality' depends-on {depends_on!r} is missing 'format-check'"
        )

    def test_quality_gate_members_are_env_self_contained(self):
        """Every task the `quality` gate depends on must be env-self-contained.

        A task is self-contained if its command delegates to an explicit env
        via `pixi run -e <env>` or `pixi run --environment <env>`, or if it
        is itself a depends-on aggregate with no `cmd` of its own. A bare
        tool invocation like `ruff format --check framework/` fails this
        check because it only works if the caller happens to already be in
        the right env.
        """
        tasks = load_tasks()
        depends_on = task_depends_on(tasks["quality"])
        offenders = []
        for name in depends_on:
            assert name in tasks, (
                f"'{name}' listed in quality depends-on but not defined"
            )
            task = tasks[name]
            cmd = task_cmd(task)
            if cmd is None:
                # Aggregate task with no cmd of its own (e.g. depends-on only).
                continue
            if not ENV_DELEGATION_RE.match(cmd):
                offenders.append(f"{name!r}: {cmd!r}")
        assert not offenders, (
            "these quality-gate members are not env-self-contained "
            "(command must delegate via 'pixi run -e <env>' or "
            "'pixi run --environment <env>'): " + "; ".join(offenders)
        )

    def test_ci_format_check_delegates_to_quality_env(self):
        """`ci-format-check` must delegate to the quality env, not run bare."""
        tasks = load_tasks()
        assert "ci-format-check" in tasks, "'ci-format-check' task not found"
        cmd = task_cmd(tasks["ci-format-check"])
        assert cmd is not None, "'ci-format-check' has no command"
        assert QUALITY_ENV_DELEGATION_RE.match(cmd), (
            f"'ci-format-check' command {cmd!r} does not delegate to the quality env"
        )
