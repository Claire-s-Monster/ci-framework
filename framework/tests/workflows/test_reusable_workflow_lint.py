"""Tests for reusable-ci.yml and standalone-ci.yml quality.

These tests validate the actual workflow files that consumer repos depend on,
catching anti-patterns that actionlint misses (double ${{ }}, cross-repo
checkout fragility, missing event guards, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")
REUSABLE_CI = WORKFLOWS_DIR / "reusable-ci.yml"
STANDALONE_CI = WORKFLOWS_DIR / "standalone-ci.yml"
CI_YML = WORKFLOWS_DIR / "ci.yml"


def load_workflow(path: Path) -> tuple[dict, list[str]]:
    """Load a workflow file, returning parsed YAML and raw lines."""
    text = path.read_text()
    return yaml.safe_load(text), text.splitlines()


# ============================================================================
# Custom linter integration tests
# ============================================================================


class TestWorkflowLinter:
    """Test that the custom linter catches known anti-patterns."""

    def test_reusable_ci_has_no_lint_errors(self):
        """reusable-ci.yml must pass custom lint with zero errors."""
        from framework.workflow_lint import lint_workflow

        result = lint_workflow(REUSABLE_CI)
        errors = [e for e in result.errors if e.severity == "error"]
        assert not errors, "Lint errors in reusable-ci.yml:\n" + "\n".join(
            str(e) for e in errors
        )

    def test_standalone_ci_has_no_lint_errors(self):
        """standalone-ci.yml must pass custom lint with zero errors."""
        from framework.workflow_lint import lint_workflow

        result = lint_workflow(STANDALONE_CI)
        errors = [e for e in result.errors if e.severity == "error"]
        assert not errors, "Lint errors in standalone-ci.yml:\n" + "\n".join(
            str(e) for e in errors
        )

    def test_ci_yml_has_no_lint_errors(self):
        """ci.yml must pass custom lint with zero errors."""
        from framework.workflow_lint import lint_workflow

        result = lint_workflow(CI_YML)
        errors = [e for e in result.errors if e.severity == "error"]
        assert not errors, "Lint errors in ci.yml:\n" + "\n".join(
            str(e) for e in errors
        )


# ============================================================================
# Structural validation for reusable-ci.yml
# ============================================================================


class TestReusableCIStructure:
    """Validate reusable-ci.yml structure and correctness."""

    @pytest.fixture()
    def workflow(self) -> dict:
        wf, _ = load_workflow(REUSABLE_CI)
        return wf

    def test_is_workflow_call_trigger(self, workflow):
        """Must use workflow_call trigger for reusable pattern."""
        trigger = workflow.get("on", workflow.get(True, {}))
        assert "workflow_call" in trigger

    def test_all_inputs_have_defaults(self, workflow):
        """All inputs must have defaults so consumers can call with zero config."""
        trigger = workflow.get("on", workflow.get(True, {}))
        inputs = trigger["workflow_call"]["inputs"]
        for name, config in inputs.items():
            assert "default" in config, f"Input '{name}' missing default value"

    def test_has_all_10_jobs(self, workflow):
        """Must have exactly the expected 10 jobs."""
        expected_jobs = {
            "detect-changes",
            "hygiene",
            "quality",
            "test",
            "security",
            "performance",
            "build",
            "release",
            "self-heal",
            "summary",
        }
        actual_jobs = set(workflow["jobs"].keys())
        assert expected_jobs == actual_jobs, (
            f"Missing: {expected_jobs - actual_jobs}, "
            f"Extra: {actual_jobs - expected_jobs}"
        )

    def test_no_double_expression_wrap_in_job_if(self, workflow):
        """No job-level if: should contain explicit ${{ }}.

        Job-level if: already implicitly wraps in ${{ }}, so explicit wrapping
        causes startup_failure — the exact bug that motivated this test suite.
        """
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                continue
            job_if = job_config.get("if")
            if job_if and isinstance(job_if, str):
                assert "${{" not in job_if, (
                    f"Job '{job_name}' has double ${{{{ }}}} in if: '{job_if}'. "
                    "Remove the explicit ${{{{ }}}} — job-level if: wraps implicitly."
                )

    def test_no_cross_repo_checkout(self, workflow):
        """No job should checkout external repos — makes workflow fragile."""
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                continue
            for step in job_config.get("steps", []):
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses", "")
                with_config = step.get("with", {})
                if "actions/checkout" in uses and isinstance(with_config, dict):
                    repo = with_config.get("repository", "")
                    assert not repo or repo == "${{ github.repository }}", (
                        f"Job '{job_name}' checks out external repo '{repo}'. "
                        "Reusable workflow must be self-contained."
                    )

    def test_dependency_review_has_event_guard(self, workflow):
        """dependency-review-action must have pull_request event guard."""
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                continue
            for step in job_config.get("steps", []):
                if not isinstance(step, dict):
                    continue
                if "dependency-review-action" in step.get("uses", ""):
                    step_if = str(step.get("if", ""))
                    assert "pull_request" in step_if, (
                        f"Job '{job_name}' uses dependency-review-action without "
                        "pull_request event guard. It only works on PR events."
                    )

    def test_release_if_no_double_wrap(self, workflow):
        """Release job if: must not have the double ${{ }} bug."""
        release = workflow["jobs"]["release"]
        release_if = release.get("if", "")
        assert "${{" not in str(release_if), (
            f"Release job if: has double ${{{{ }}}}: '{release_if}'"
        )

    def test_summary_job_always_runs(self, workflow):
        """Summary job must use if: always() to run even on failures."""
        summary = workflow["jobs"]["summary"]
        assert summary.get("if") == "always()" or "always()" in str(
            summary.get("if", "")
        )

    def test_summary_needs_all_jobs(self, workflow):
        """Summary job needs: must reference all content jobs.

        detect-changes is excluded because it's an upstream prerequisite that
        completes before all the jobs summary already waits on.
        """
        # Jobs that are upstream-only (transitively covered by other needs)
        upstream_only = {"detect-changes"}
        all_jobs = set(workflow["jobs"].keys()) - {"summary"} - upstream_only
        summary_needs = set(workflow["jobs"]["summary"].get("needs", []))
        missing = all_jobs - summary_needs
        assert not missing, f"Summary job missing needs: {missing}"

    def test_consistent_pixi_version(self):
        """All pixi-version references must use the same value."""
        _, raw_lines = load_workflow(REUSABLE_CI)
        versions = set()
        for line in raw_lines:
            match = re.search(r"pixi-version:\s*(\S+)", line)
            if match and "#" not in line.split("pixi-version:")[0]:
                versions.add(match.group(1))
        assert len(versions) <= 1, f"Multiple pixi versions: {versions}"


# ============================================================================
# Structural validation for standalone-ci.yml
# ============================================================================


class TestStandaloneCIStructure:
    """Validate standalone-ci.yml structure and correctness."""

    @pytest.fixture()
    def workflow(self) -> dict:
        wf, _ = load_workflow(STANDALONE_CI)
        return wf

    def test_is_not_workflow_call(self, workflow):
        """Standalone must NOT use workflow_call — it's a direct trigger template."""
        trigger = workflow.get("on", workflow.get(True, {}))
        if isinstance(trigger, dict):
            assert "workflow_call" not in trigger

    def test_has_dispatch_trigger(self, workflow):
        """Must have at least workflow_dispatch trigger.

        In ci-framework repo, standalone uses workflow_dispatch only to avoid
        running against the framework itself. The comments instruct consumers
        to add push/pull_request triggers when copying.
        """
        trigger = workflow.get("on", workflow.get(True, {}))
        # trigger can be a string "workflow_dispatch" or dict
        if isinstance(trigger, str):
            assert trigger == "workflow_dispatch"
        else:
            assert "workflow_dispatch" in trigger

    def test_has_configure_job(self, workflow):
        """Must have configure job for job-level settings."""
        assert "configure" in workflow["jobs"]
        outputs = workflow["jobs"]["configure"].get("outputs", {})
        assert "python-versions" in outputs
        assert "os-matrix" in outputs

    def test_has_all_10_content_jobs(self, workflow):
        """Must have all 10 content jobs (same as reusable) plus configure."""
        expected = {
            "configure",
            "detect-changes",
            "hygiene",
            "quality",
            "test",
            "security",
            "performance",
            "build",
            "release",
            "self-heal",
            "summary",
        }
        actual = set(workflow["jobs"].keys())
        assert expected == actual

    def test_no_cross_repo_checkout(self, workflow):
        """Standalone must have zero external dependencies."""
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                continue
            for step in job_config.get("steps", []):
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses", "")
                with_config = step.get("with", {})
                if "actions/checkout" in uses and isinstance(with_config, dict):
                    repo = with_config.get("repository", "")
                    assert not repo, (
                        f"Job '{job_name}' checks out external repo '{repo}'. "
                        "Standalone template must be fully self-contained."
                    )

    def test_has_top_level_permissions(self, workflow):
        """Must declare top-level permissions for security."""
        assert "permissions" in workflow

    def test_has_env_block(self, workflow):
        """Must have env block for step-level configuration."""
        assert "env" in workflow
        env = workflow["env"]
        assert "PIXI_VERSION" in env
        assert "PIXI_ENVIRONMENT" in env
        assert "PACKAGE_PATH" in env


# ============================================================================
# Cross-file consistency
# ============================================================================


class TestCrossFileConsistency:
    """Validate consistency between reusable and standalone workflows."""

    def test_same_content_jobs(self):
        """Both workflows must have the same set of content jobs."""
        reusable, _ = load_workflow(REUSABLE_CI)
        standalone, _ = load_workflow(STANDALONE_CI)

        reusable_jobs = set(reusable["jobs"].keys())
        standalone_jobs = set(standalone["jobs"].keys()) - {"configure"}

        assert reusable_jobs == standalone_jobs, (
            f"Job mismatch. Only in reusable: {reusable_jobs - standalone_jobs}, "
            f"Only in standalone: {standalone_jobs - reusable_jobs}"
        )

    def test_action_versions_match(self):
        """Action versions should be consistent across workflows."""
        reusable_text = REUSABLE_CI.read_text()
        standalone_text = STANDALONE_CI.read_text()

        # Extract action@version pairs
        action_re = re.compile(r"uses:\s*([\w/-]+)@(v\d+)")

        reusable_actions = {}
        for match in action_re.finditer(reusable_text):
            reusable_actions[match.group(1)] = match.group(2)

        standalone_actions = {}
        for match in action_re.finditer(standalone_text):
            standalone_actions[match.group(1)] = match.group(2)

        # Check common actions have same versions
        common = set(reusable_actions.keys()) & set(standalone_actions.keys())
        mismatches = []
        for action in sorted(common):
            if reusable_actions[action] != standalone_actions[action]:
                mismatches.append(
                    f"  {action}: reusable={reusable_actions[action]}, "
                    f"standalone={standalone_actions[action]}"
                )

        assert not mismatches, (
            "Action version mismatches:\n" + "\n".join(mismatches)
        )


# Need re import at module level for TestReusableCIStructure.test_consistent_pixi_version
import re  # noqa: E402
