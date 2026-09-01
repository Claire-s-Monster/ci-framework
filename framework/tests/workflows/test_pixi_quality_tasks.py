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

import pytest
import tomllib

PYPROJECT = Path("pyproject.toml")
TEMPLATE_PYPROJECT = Path("templates/pyproject-tiered-template.toml")

# Env-delegation guards accept both the short (`-e`) and long
# (`--environment`) pixi flag forms, and tolerate extra whitespace.
ENV_DELEGATION_RE = re.compile(r"^pixi\s+run\s+(?:-e|--environment)\s+[\w.-]+\s")
QUALITY_ENV_DELEGATION_RE = re.compile(
    r"^pixi\s+run\s+(?:-e|--environment)\s+quality(?:\s|$)"
)
# Captures (env, target-task) from a `pixi run -e/--environment <env> <task> ...` command.
DELEGATION_TARGET_RE = re.compile(
    r"^pixi\s+run\s+(?:-e|--environment)\s+([\w.-]+)\s+([\w.-]+)"
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


def load_template_tasks() -> dict:
    """Load the [tool.pixi.tasks] table from the tiered pyproject template."""
    data = tomllib.loads(TEMPLATE_PYPROJECT.read_text())
    return data["tool"]["pixi"]["tasks"]


def load_template_manifest() -> dict:
    """Load the full parsed template manifest (for feature/environment tables)."""
    return tomllib.loads(TEMPLATE_PYPROJECT.read_text())


def build_tool_to_feature_map(manifest: dict) -> dict[str, str]:
    """Map each tool/binary name to the pixi feature that declares it.

    Parses every `[tool.pixi.feature.<name>.dependencies]` table directly
    from the manifest, so the tracked tool universe reflects whatever the
    template actually declares instead of a hand-maintained literal list —
    the exact staleness failure mode this guard exists to prevent (#255,
    #261). There is no exclusion list: every tool declared under a feature
    is tracked, and any task that bare-invokes one must earn its exemption
    structurally by being an `-impl` leaf.
    """
    features = manifest.get("tool", {}).get("pixi", {}).get("feature", {})
    tool_to_feature: dict[str, str] = {}
    for feature_name, feature_table in features.items():
        deps = (
            feature_table.get("dependencies", {})
            if isinstance(feature_table, dict)
            else {}
        )
        for dep_name in deps:
            tool_to_feature.setdefault(dep_name, feature_name)
    return tool_to_feature


def build_feature_to_environments_map(manifest: dict) -> dict[str, set]:
    """Map each pixi feature to the set of environments that include it."""
    environments = manifest.get("tool", {}).get("pixi", {}).get("environments", {})
    feature_to_envs: dict[str, set] = {}
    for env_name, env_table in environments.items():
        if not isinstance(env_table, dict):
            continue
        for feature_name in env_table.get("features", []):
            feature_to_envs.setdefault(feature_name, set()).add(env_name)
    return feature_to_envs


def find_direct_tool_invocation(cmd: str, tool_to_feature: dict) -> str | None:
    """Return the tracked tool name `cmd` directly invokes, or None.

    Matches a tool name only when it is the command being run — at the very
    start of `cmd`, or immediately after a shell separator (&&, |, ;) — never
    when it merely appears as an argument. A `pixi run ...` delegation is
    never a direct invocation, since it only references a task name.
    """
    if not tool_to_feature or cmd.strip().startswith("pixi run"):
        return None
    pattern = re.compile(
        r"(?:^|&&|\||;)\s*(" + "|".join(re.escape(t) for t in tool_to_feature) + r")\b"
    )
    match = pattern.search(cmd)
    return match.group(1) if match else None


@pytest.fixture(scope="module")
def template_manifest() -> dict:
    """Parse the template manifest once per module, not once per parametrized case."""
    return load_template_manifest()


@pytest.fixture(scope="module")
def template_tool_to_feature(template_manifest: dict) -> dict:
    return build_tool_to_feature_map(template_manifest)


@pytest.fixture(scope="module")
def template_feature_to_envs(template_manifest: dict) -> dict:
    return build_feature_to_environments_map(template_manifest)


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


class TestTemplateFormatCheckTasksAreEnvSelfContained:
    """Guard the tiered pyproject template against the same #267 regression.

    `templates/pyproject-tiered-template.toml` is copied into every project
    scaffolded from it, so a bare `ruff format --check {{ source_path }}`
    there reproduces the exit-127 "command not found" bug for every
    generated project, not just this repo.
    """

    def test_template_tasks_were_actually_found(self):
        """Vacuity guard: a silently-empty parse would make the other tests trivially pass."""
        tasks = load_template_tasks()
        assert tasks, (
            "Parsed template pixi tasks table is empty — parse likely failed silently"
        )
        assert "format-check" in tasks, "'format-check' task not found in template"
        assert "ci-format-check" in tasks, (
            "'ci-format-check' task not found in template"
        )

    def test_template_format_check_delegates_to_quality_env(self):
        """`format-check` in the template must delegate, not run bare."""
        tasks = load_template_tasks()
        cmd = task_cmd(tasks["format-check"])
        assert cmd is not None, "'format-check' has no command"
        assert QUALITY_ENV_DELEGATION_RE.match(cmd), (
            f"'format-check' command {cmd!r} does not delegate to the quality env"
        )

    def test_template_ci_format_check_delegates_to_quality_env(self):
        """`ci-format-check` in the template must delegate, not run bare."""
        tasks = load_template_tasks()
        cmd = task_cmd(tasks["ci-format-check"])
        assert cmd is not None, "'ci-format-check' has no command"
        assert QUALITY_ENV_DELEGATION_RE.match(cmd), (
            f"'ci-format-check' command {cmd!r} does not delegate to the quality env"
        )

    def test_template_quality_aggregate_includes_format_check(self):
        """`format-check` must be a member of the template's mandatory quality gate."""
        tasks = load_template_tasks()
        depends_on = task_depends_on(tasks["quality"])
        assert "format-check" in depends_on, (
            f"template 'quality' depends-on {depends_on!r} is missing 'format-check'"
        )


class TestTemplateToolInvokingTasksFollowDelegationConvention:
    """Data-driven guard for the #267/#268 defect class across ALL template tasks.

    Hand-listing "the tasks this applies to" (as the class above does for
    `format-check`/`ci-format-check`) goes stale whenever a new bare
    tool-invoking task is added — see #255, #261. This derives the tracked
    tool universe from the manifest itself (every dependency declared under
    `[tool.pixi.feature.*.dependencies]`, mapped to the smallest
    `[tool.pixi.environments]` entries that provide each feature) and walks
    every task in the template's `[tool.pixi.tasks]`:

    - if a task's command directly bare-invokes a tracked tool, its name
      must end in `-impl` (bare tool invocations only belong in `-impl`
      leaf tasks, run inside an env that provides the tool);
    - if a task delegates (`pixi run -e/--environment <env> <target>`) to a
      target task that itself directly bare-invokes a tracked tool, the
      delegation's env must actually provide the feature that declares that
      tool — not just any env.
    """

    def test_template_task_table_was_actually_found(self):
        """Vacuity guard: a silently-empty parse would make the other tests trivially pass."""
        tasks = load_template_tasks()
        assert tasks, (
            "Parsed template pixi tasks table is empty — parse likely failed silently"
        )

    def test_template_tool_and_environment_maps_were_actually_found(
        self, template_tool_to_feature, template_feature_to_envs
    ):
        """Vacuity guard: empty derived maps would make the other tests trivially pass."""
        tool_to_feature = template_tool_to_feature
        feature_to_envs = template_feature_to_envs
        assert tool_to_feature, (
            "Parsed template tool→feature map is empty — parse likely failed silently"
        )
        assert "bandit" in tool_to_feature, (
            "'bandit' not found in template's tool→feature map"
        )
        assert feature_to_envs, (
            "Parsed template feature→environments map is empty — parse likely failed silently"
        )
        assert "quality" in feature_to_envs, (
            "'quality' feature not found in template's feature→environments map"
        )

    @pytest.mark.parametrize("name", sorted(load_template_tasks()))
    def test_template_task_tool_delegation_convention(
        self,
        name,
        template_manifest,
        template_tool_to_feature,
        template_feature_to_envs,
    ):
        tasks = template_manifest["tool"]["pixi"]["tasks"]
        tool_to_feature = template_tool_to_feature
        feature_to_envs = template_feature_to_envs

        cmd = task_cmd(tasks[name])
        if cmd is None:
            pytest.skip(f"{name!r} has no cmd (depends-on aggregate)")

        tool = find_direct_tool_invocation(cmd, tool_to_feature)
        if tool is not None:
            assert name.endswith("-impl"), (
                f"{name!r} directly invokes {tool!r} ({cmd!r}), a tool declared "
                f"in the {tool_to_feature[tool]!r} feature, but its name does "
                "not end in '-impl' — bare tool invocations must live in an "
                "'-impl' leaf task"
            )
            return

        match = DELEGATION_TARGET_RE.match(cmd.strip())
        if match is None:
            return
        env, target = match.group(1), match.group(2)
        target_task = tasks.get(target)
        if target_task is None:
            return
        target_cmd = task_cmd(target_task)
        if target_cmd is None:
            return
        target_tool = find_direct_tool_invocation(target_cmd, tool_to_feature)
        if target_tool is None:
            return
        required_feature = tool_to_feature[target_tool]
        providing_envs = feature_to_envs.get(required_feature, set())
        assert env in providing_envs, (
            f"{name!r} delegates to {target!r} (which directly invokes "
            f"{target_tool!r}, declared in the {required_feature!r} feature) "
            f"via env {env!r}, but {env!r} does not provide the "
            f"{required_feature!r} feature — provided by: {sorted(providing_envs)!r}"
        )
