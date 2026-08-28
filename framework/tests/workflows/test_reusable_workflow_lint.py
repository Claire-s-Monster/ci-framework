"""Tests for reusable-ci.yml and standalone-ci.yml quality.

These tests validate the actual workflow files that consumer repos depend on,
catching anti-patterns that actionlint misses (double ${{ }}, cross-repo
checkout fragility, missing event guards, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")
REUSABLE_CI = WORKFLOWS_DIR / "reusable-ci.yml"
REUSABLE_RELEASE = WORKFLOWS_DIR / "reusable-release.yml"
REUSABLE_SECURITY = WORKFLOWS_DIR / "reusable-security.yml"
STANDALONE_CI = WORKFLOWS_DIR / "standalone-ci.yml"
CI_YML = WORKFLOWS_DIR / "ci.yml"

# Matches a `pixi-version:` site that carries a value on the same line (i.e.
# excludes the bare `pixi-version:` key that introduces the input definition,
# whose `default:` lives on a following line).
PIXI_VERSION_SITE_RE = re.compile(r"pixi-version:\s*(\S.*?)\s*$")
HARDCODED_PIXI_VERSION_RE = re.compile(r"pixi-version:\s*(v[0-9]\S*)")


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

    def test_has_expected_jobs(self, workflow):
        """Check that all core jobs exist (allows additional language-specific jobs)."""
        jobs = set(workflow["jobs"].keys())
        core_jobs = {"detect-changes", "hygiene", "test", "summary"}
        assert core_jobs.issubset(jobs), f"Missing core jobs: {core_jobs - jobs}"

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

    def test_summary_job_always_runs(self, workflow):
        """Summary job must use if: always() to run even on failures."""
        summary = workflow["jobs"]["summary"]
        assert summary.get("if") == "always()" or "always()" in str(
            summary.get("if", "")
        )

    def test_summary_needs_all_jobs(self, workflow):
        """Summary job must depend on all other jobs except detect-changes and configure."""
        upstream_only = {"detect-changes", "configure"}
        all_jobs = set(workflow["jobs"].keys()) - {"summary"} - upstream_only
        summary_needs = workflow["jobs"]["summary"].get("needs", [])
        if isinstance(summary_needs, str):
            summary_needs = [summary_needs]
        missing = all_jobs - set(summary_needs)
        assert not missing, f"Summary missing needs: {sorted(missing)}"


# ============================================================================
# pixi-version input: no hardcoded drift, all sites reference the input
# ============================================================================


class TestPixiVersionInput:
    """Validate the pixi-version workflow_call input across reusable workflows.

    reusable-ci.yml and reusable-security.yml both take a `pixi-version`
    input so the pinned pixi CLI version can be overridden per-caller
    (issue #250). These tests replace the old test_consistent_pixi_version,
    which became vacuous once every site was rewritten to the literal string
    `${{ inputs.pixi-version }}` (a single-element set no matter what the
    input's actual default is).
    """

    @pytest.mark.parametrize("path", [REUSABLE_CI, REUSABLE_SECURITY])
    def test_no_hardcoded_pixi_version_literal(self, path):
        """No pixi-version site may hardcode a literal version like v0.74.0."""
        _, raw_lines = load_workflow(path)
        for lineno, line in enumerate(raw_lines, start=1):
            if line.strip().startswith("default:"):
                continue
            match = HARDCODED_PIXI_VERSION_RE.search(line)
            assert not match, (
                f"{path}:{lineno} hardcodes pixi-version '{match.group(1)}' "
                "instead of using ${{ inputs.pixi-version }}"
            )

    @pytest.mark.parametrize("path", [REUSABLE_CI, REUSABLE_SECURITY])
    def test_setup_pixi_steps_reference_input(self, path):
        """Every setup-pixi pixi-version: site must resolve to the input expression."""
        _, raw_lines = load_workflow(path)
        sites = [
            (lineno, match.group(1))
            for lineno, line in enumerate(raw_lines, start=1)
            if (match := PIXI_VERSION_SITE_RE.search(line))
        ]
        assert sites, f"No pixi-version: sites with a value found in {path}"
        for lineno, value in sites:
            assert value == "${{ inputs.pixi-version }}", (
                f"{path}:{lineno} pixi-version does not reference the input: "
                f"'{value}'"
            )

    @pytest.mark.parametrize("path", [REUSABLE_CI, REUSABLE_SECURITY])
    def test_pixi_version_input_is_well_formed(self, path):
        """The pixi-version input must exist, be an optional string with a vX.Y.Z default."""
        workflow, _ = load_workflow(path)
        trigger = workflow.get("on", workflow.get(True, {}))
        inputs = trigger["workflow_call"]["inputs"]
        assert "pixi-version" in inputs, f"{path} is missing the 'pixi-version' input"
        config = inputs["pixi-version"]
        assert config.get("type") == "string", (
            f"{path} pixi-version input type must be 'string', got {config.get('type')!r}"
        )
        assert config.get("required") is False, (
            f"{path} pixi-version input must be optional (required: false)"
        )
        default = config.get("default")
        assert default and re.match(r"^v\d+\.\d+\.\d+$", default), (
            f"{path} pixi-version default {default!r} is not a valid vX.Y.Z version"
        )

    def test_pixi_version_default_matches_across_reusable_workflows(self):
        """The default pixi-version must be identical in both reusable workflows."""
        ci_workflow, _ = load_workflow(REUSABLE_CI)
        security_workflow, _ = load_workflow(REUSABLE_SECURITY)
        ci_trigger = ci_workflow.get("on", ci_workflow.get(True, {}))
        security_trigger = security_workflow.get("on", security_workflow.get(True, {}))
        ci_default = ci_trigger["workflow_call"]["inputs"]["pixi-version"]["default"]
        security_default = security_trigger["workflow_call"]["inputs"]["pixi-version"][
            "default"
        ]
        assert ci_default == security_default, (
            f"pixi-version default mismatch: reusable-ci={ci_default!r}, "
            f"reusable-security={security_default!r}"
        )


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

    def test_has_expected_jobs(self, workflow):
        """Must have expected content jobs (same as reusable) plus configure."""
        expected = {
            "configure",
            "detect-changes",
            "hygiene",
            "quality",
            "test",
            "security",
            "performance",
            "build",
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
# Structural validation for reusable-release.yml
# ============================================================================


class TestReusableReleaseStructure:
    """Validate reusable-release.yml structure and correctness."""

    @pytest.fixture()
    def workflow(self) -> dict:
        wf, _ = load_workflow(REUSABLE_RELEASE)
        return wf

    def test_is_workflow_call_trigger(self, workflow):
        """Must use workflow_call trigger for reusable pattern."""
        trigger = workflow.get("on", workflow.get(True, {}))
        assert "workflow_call" in trigger

    def test_no_permissions_declared(self, workflow):
        """Must NOT declare top-level or job-level permissions.

        The caller must provide id-token: write and contents: write at the
        calling job level. If the reusable workflow declares these permissions
        itself, it causes startup_failure for callers whose token scope
        cannot satisfy them.
        """
        # No top-level permissions
        assert "permissions" not in workflow, (
            "reusable-release.yml must not declare top-level permissions — "
            "the caller provides them"
        )
        # No job-level permissions
        for job_name, job_config in workflow["jobs"].items():
            if isinstance(job_config, dict):
                assert "permissions" not in job_config, (
                    f"Job '{job_name}' must not declare permissions — "
                    "the caller provides them"
                )

    def test_has_event_guard(self, workflow):
        """Publish job must guard against non-push events."""
        publish = workflow["jobs"]["publish"]
        job_if = str(publish.get("if", ""))
        assert "push" in job_if, (
            "Publish job must guard on push event to prevent accidental "
            "publishing on PRs"
        )

    def test_downloads_artifact(self, workflow):
        """Must download the build artifact from the CI pipeline."""
        publish = workflow["jobs"]["publish"]
        download_steps = [
            s
            for s in publish.get("steps", [])
            if isinstance(s, dict) and "download-artifact" in s.get("uses", "")
        ]
        assert download_steps, "Publish job must download build artifact"

    def test_no_double_expression_wrap(self, workflow):
        """No job-level if: should contain explicit ${{ }}."""
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                continue
            job_if = job_config.get("if")
            if job_if and isinstance(job_if, str):
                assert "${{" not in job_if, (
                    f"Job '{job_name}' has double ${{{{ }}}} in if: '{job_if}'"
                )


# ============================================================================
# Cross-file consistency
# ============================================================================


class TestCrossFileConsistency:
    """Validate consistency between reusable and standalone workflows."""

    def test_same_content_jobs(self):
        """Core jobs should match between reusable and standalone (security/quality may differ)."""
        reusable, _ = load_workflow(REUSABLE_CI)
        standalone, _ = load_workflow(STANDALONE_CI)

        reusable_jobs = set(reusable["jobs"].keys())
        standalone_jobs = set(standalone["jobs"].keys())
        # These jobs differ: reusable has multi-lang, standalone has Python-only
        multi_lang_jobs = {
            "python-dep-audit",
            "rust-dep-audit",
            "rust-deny",
            "js-dep-audit",
            "sast-semgrep",
            "sast-codeql",
            "secret-scan",
            "scorecard",
            "python-quality",
            "python-lint",
            "python-format",
            "python-types",
            "rust-lint",
            "rust-format",
            "c-cpp-lint",
            "cython-lint",
            "js-lint",
        }
        old_jobs = {"security", "quality"}
        # Optional service-container jobs only in reusable workflow
        optional_service_jobs = {"test-postgres"}
        reusable_core = (
            reusable_jobs - multi_lang_jobs - old_jobs - optional_service_jobs
        )
        standalone_core = standalone_jobs - multi_lang_jobs - old_jobs - {"configure"}
        assert reusable_core == standalone_core, (
            f"Core job mismatch: reusable={sorted(reusable_core)}, standalone={sorted(standalone_core)}"
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

        assert not mismatches, "Action version mismatches:\n" + "\n".join(mismatches)
