"""
Unit tests for dependency resolution workflow.

This module tests the complete dependency fix workflow including
pattern matching, fix application, and verification.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from framework.self_healing.dependency_workflow import DependencyFixWorkflow


class TestDependencyWorkflow:
    """Test dependency fix workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.workflow = DependencyFixWorkflow(working_directory=self.temp_dir)

    def test_analyze_output_detects_issues(self):
        """Test that analyze_output correctly identifies dependency issues."""
        output = "ModuleNotFoundError: No module named 'requests'"

        fix_info = self.workflow.analyze_output(output)

        assert fix_info is not None
        assert fix_info["pattern_id"] == "module_not_found_error"
        assert fix_info["action"] == "suggest_pixi_add"

    def test_analyze_output_no_issues(self):
        """Test analyze_output returns None for non-dependency output."""
        output = "All tests passed!"

        fix_info = self.workflow.analyze_output(output)

        assert fix_info is None

    def test_execute_workflow_pixi_install(self):
        """Test workflow execution for pixi install fix."""
        # Mock command executor
        mock_result = MagicMock()
        mock_result.return_code = 0
        mock_result.stdout = "Successfully installed dependencies"
        mock_result.stderr = ""

        # Patch both command executors
        with patch.object(
            self.workflow.command_executor, "execute", return_value=mock_result
        ):
            with patch.object(
                self.workflow.dependency_engine.command_executor,
                "execute",
                return_value=mock_result,
            ):
                # Create test files
                pyproject_file = Path(self.temp_dir) / "pyproject.toml"
                pyproject_file.write_text("[tool.pixi.dependencies]\npython = '3.12.*'")

                # Create a mock lock file that would be created by pixi install
                lock_file = Path(self.temp_dir) / "pixi.lock"
                lock_file.write_text("# Mock pixi.lock content")

                output = "The lock file is not up-to-date with pyproject.toml"

                success, message = self.workflow.execute_workflow(output)

                assert success is True
                assert "Successfully executed: pixi install" in message

    def test_execute_workflow_module_suggestion(self):
        """Test workflow execution for module suggestion."""
        output = "ModuleNotFoundError: No module named 'pandas'"

        success, message = self.workflow.execute_workflow(output)

        assert success is True
        assert "pixi add pandas" in message
        assert "Module 'pandas' not found" in message

    def test_execute_workflow_conflict_notification(self):
        """Test workflow execution for dependency conflicts."""
        output = "Conflict detected in dependencies"

        success, message = self.workflow.execute_workflow(output)

        assert success is False
        assert "Dependency conflict detected" in message
        assert "Manual intervention required" in message

    def test_verify_pixi_install_success(self):
        """Test verification of successful pixi install."""
        # Create lock file
        lock_file = Path(self.temp_dir) / "pixi.lock"
        lock_file.write_text("lock file content")

        # Mock pixi info command
        mock_result = MagicMock()
        mock_result.return_code = 0
        mock_result.stdout = "Environment info"
        mock_result.stderr = ""

        with patch.object(
            self.workflow.command_executor, "execute", return_value=mock_result
        ):
            success, message = self.workflow._verify_pixi_install()

            assert success is True
            assert "verified successfully" in message

    def test_verify_pixi_install_no_lock_file(self):
        """Test verification fails when lock file is missing."""
        success, message = self.workflow._verify_pixi_install()

        assert success is False
        assert "pixi.lock file not found" in message

    def test_get_suggestion_for_module(self):
        """Test module suggestion with name mapping."""
        # Test common mappings
        suggestion = self.workflow.get_suggestion_for_module("cv2")
        assert "pixi add opencv" in suggestion

        suggestion = self.workflow.get_suggestion_for_module("sklearn")
        assert "pixi add scikit-learn" in suggestion

        # Test unmapped module
        suggestion = self.workflow.get_suggestion_for_module("requests")
        assert "pixi add requests" in suggestion

    @patch("subprocess.run")
    def test_commit_changes_success(self, mock_run):
        """Test successful git commit."""
        # Mock git status - has changes
        status_result = MagicMock()
        status_result.stdout = "M pixi.lock"
        status_result.returncode = 0

        # Mock git add and commit
        success_result = MagicMock()
        success_result.returncode = 0

        mock_run.side_effect = [status_result, success_result, success_result]

        # Create lock file
        lock_file = Path(self.temp_dir) / "pixi.lock"
        lock_file.write_text("lock content")

        success, message = self.workflow._commit_changes("fix: Update dependencies")

        assert success is True
        assert "Changes committed" in message

    @patch("subprocess.run")
    def test_commit_changes_no_changes(self, mock_run):
        """Test commit when no changes exist."""
        # Mock git status - no changes
        status_result = MagicMock()
        status_result.stdout = ""
        status_result.returncode = 0

        mock_run.return_value = status_result

        success, message = self.workflow._commit_changes("fix: Update dependencies")

        assert success is True
        assert "No changes to commit" in message

    def test_execute_workflow_dry_run(self):
        """Test workflow in dry run mode."""
        output = "The lock file is not up-to-date with pyproject.toml"

        success, message = self.workflow.execute_workflow(output, dry_run=True)

        assert success is True
        assert "Would execute: pixi install" in message
