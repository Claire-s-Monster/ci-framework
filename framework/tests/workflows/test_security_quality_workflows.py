"""Tests for reusable-security.yml and reusable-quality.yml structural validation.

These tests validate the workflow files that consumers depend on, ensuring
correct job structure, dependency chains, inputs with defaults, and output
definitions for the language detection job.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).parents[3] / ".github" / "workflows"
REUSABLE_SECURITY = WORKFLOWS_DIR / "reusable-security.yml"
REUSABLE_QUALITY = WORKFLOWS_DIR / "reusable-quality.yml"


def load_workflow(path: Path) -> dict:
    """Load a workflow file, returning parsed YAML."""
    return yaml.safe_load(path.read_text())


# ============================================================================
# Structural validation for reusable-security.yml
# ============================================================================


class TestReusableSecurityStructure:
    """Validate reusable-security.yml structure and correctness."""

    def _workflow(self) -> dict:
        return load_workflow(REUSABLE_SECURITY)

    def test_is_workflow_call_trigger(self):
        """Must use workflow_call trigger for reusable pattern."""
        workflow = self._workflow()
        trigger = workflow.get("on", workflow.get(True, {}))
        assert "workflow_call" in trigger

    def test_has_detect_languages_job(self):
        """Must have detect-languages job for language auto-detection."""
        workflow = self._workflow()
        assert "detect-languages" in workflow["jobs"]

    def test_detect_languages_outputs(self):
        """detect-languages must expose all expected language outputs."""
        workflow = self._workflow()
        outputs = workflow["jobs"]["detect-languages"].get("outputs", {})
        expected_outputs = {
            "python",
            "rust",
            "c_cpp",
            "cython",
            "js_ts",
            "codeql_matrix",
            "has_codeql",
        }
        actual_outputs = set(outputs.keys())
        missing = expected_outputs - actual_outputs
        assert not missing, f"detect-languages missing outputs: {missing}"

    def test_has_security_jobs(self):
        """Must have all expected security scanning jobs."""
        workflow = self._workflow()
        expected_jobs = {
            "detect-languages",
            "python-dep-audit",
            "rust-dep-audit",
            "rust-deny",
            "js-dep-audit",
            "sast-semgrep",
            "sast-codeql",
            "secret-scan",
            "scorecard",
            "security-summary",
        }
        actual_jobs = set(workflow["jobs"].keys())
        missing = expected_jobs - actual_jobs
        assert not missing, f"Missing security jobs: {missing}"

    def test_all_jobs_need_detect_languages(self):
        """All content jobs (except detect-languages, security-summary, scorecard)
        must declare needs: detect-languages.

        scorecard is excluded because it doesn't use language detection outputs.
        """
        workflow = self._workflow()
        excluded = {"detect-languages", "security-summary", "scorecard"}
        for job_name, job_config in workflow["jobs"].items():
            if job_name in excluded:
                continue
            if not isinstance(job_config, dict):
                continue
            needs = job_config.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            assert "detect-languages" in needs, (
                f"Job '{job_name}' does not declare needs: detect-languages"
            )

    def test_security_summary_needs_all_jobs(self):
        """security-summary must declare needs for every other job."""
        workflow = self._workflow()
        all_jobs = set(workflow["jobs"].keys()) - {"security-summary"}
        summary_needs = workflow["jobs"]["security-summary"].get("needs", [])
        if isinstance(summary_needs, str):
            summary_needs = [summary_needs]
        summary_needs_set = set(summary_needs)
        missing = all_jobs - summary_needs_set
        assert not missing, f"security-summary missing needs: {missing}"

    def test_all_inputs_have_defaults(self):
        """All inputs must have default values so consumers can call with zero config."""
        workflow = self._workflow()
        trigger = workflow.get("on", workflow.get(True, {}))
        inputs = trigger.get("workflow_call", {}).get("inputs", {})
        for name, config in inputs.items():
            assert "default" in config, f"Input '{name}' missing default value"

    def test_codeql_uses_matrix_from_detect_languages(self):
        """sast-codeql matrix must reference needs.detect-languages.outputs.codeql_matrix."""
        workflow = self._workflow()
        codeql_job = workflow["jobs"]["sast-codeql"]
        strategy = codeql_job.get("strategy", {})
        matrix = strategy.get("matrix", {})
        language_value = matrix.get("language", "")
        assert "needs.detect-languages.outputs.codeql_matrix" in str(language_value), (
            "sast-codeql matrix.language must reference "
            "needs.detect-languages.outputs.codeql_matrix"
        )


# ============================================================================
# Structural validation for reusable-quality.yml
# ============================================================================


class TestReusableQualityStructure:
    """Validate reusable-quality.yml structure and correctness."""

    def _workflow(self) -> dict:
        return load_workflow(REUSABLE_QUALITY)

    def test_is_workflow_call_trigger(self):
        """Must use workflow_call trigger for reusable pattern."""
        workflow = self._workflow()
        trigger = workflow.get("on", workflow.get(True, {}))
        assert "workflow_call" in trigger

    def test_has_detect_languages_job(self):
        """Must have detect-languages job for language auto-detection."""
        workflow = self._workflow()
        assert "detect-languages" in workflow["jobs"]

    def test_has_quality_jobs(self):
        """Must have all expected quality checking jobs."""
        workflow = self._workflow()
        expected_jobs = {
            "detect-languages",
            "python-lint",
            "python-format",
            "python-types",
            "rust-lint",
            "rust-format",
            "c-cpp-lint",
            "cython-lint",
            "js-lint",
            "quality-summary",
        }
        actual_jobs = set(workflow["jobs"].keys())
        missing = expected_jobs - actual_jobs
        assert not missing, f"Missing quality jobs: {missing}"

    def test_all_jobs_need_detect_languages(self):
        """All content jobs (except detect-languages and quality-summary) must
        declare needs: detect-languages.
        """
        workflow = self._workflow()
        excluded = {"detect-languages", "quality-summary"}
        for job_name, job_config in workflow["jobs"].items():
            if job_name in excluded:
                continue
            if not isinstance(job_config, dict):
                continue
            needs = job_config.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            assert "detect-languages" in needs, (
                f"Job '{job_name}' does not declare needs: detect-languages"
            )

    def test_quality_summary_needs_all_jobs(self):
        """quality-summary must declare needs for every other job."""
        workflow = self._workflow()
        all_jobs = set(workflow["jobs"].keys()) - {"quality-summary"}
        summary_needs = workflow["jobs"]["quality-summary"].get("needs", [])
        if isinstance(summary_needs, str):
            summary_needs = [summary_needs]
        summary_needs_set = set(summary_needs)
        missing = all_jobs - summary_needs_set
        assert not missing, f"quality-summary missing needs: {missing}"

    def test_all_inputs_have_defaults(self):
        """All inputs must have default values so consumers can call with zero config."""
        workflow = self._workflow()
        trigger = workflow.get("on", workflow.get(True, {}))
        inputs = trigger.get("workflow_call", {}).get("inputs", {})
        for name, config in inputs.items():
            assert "default" in config, f"Input '{name}' missing default value"
