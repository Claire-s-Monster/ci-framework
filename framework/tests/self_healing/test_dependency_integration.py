"""
Integration tests for dependency resolution in self-healing framework.

This module tests the complete dependency resolution workflow with
real-world scenarios and sample projects.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from framework.self_healing.dependency_workflow import DependencyFixWorkflow
from framework.self_healing.pattern_engine import FailurePatternEngine


class TestDependencyIntegration:
    """Integration tests for dependency resolution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_sample_project(self, with_lock=False, outdated_lock=False):
        """Create a sample project with pyproject.toml."""
        pyproject_content = """
[tool.pixi.project]
name = "test-project"
version = "0.1.0"
channels = ["conda-forge"]
platforms = ["linux-64"]

[tool.pixi.dependencies]
python = "3.12.*"
requests = "*"
pytest = "*"
"""
        pyproject_file = self.project_dir / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        if with_lock:
            lock_content = "# Mock lock file content"
            lock_file = self.project_dir / "pixi.lock"
            lock_file.write_text(lock_content)
            
            if outdated_lock:
                # Make lock file older than pyproject.toml
                import time
                time.sleep(0.1)
                pyproject_file.touch()
    
    @patch('framework.self_healing.command_executor.SafeCommandExecutor.execute')
    def test_outdated_lock_file_fix(self, mock_run_command):
        """Test fixing outdated pixi.lock file."""
        # Create project with outdated lock
        self.create_sample_project(with_lock=True, outdated_lock=True)
        
        # Mock pixi install command
        mock_result = MagicMock()
        mock_result.return_code = 0
        mock_result.stdout = "Dependencies installed"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        # Create engine and analyze error
        engine = FailurePatternEngine(project_dir=str(self.project_dir))
        error_output = "The lock file is not up-to-date with pyproject.toml"
        
        fix = engine.analyze(error_output)
        
        assert fix is not None
        assert fix["type"] == "dependency-fix"
        assert fix["pattern_id"] == "pixi_lock_outdated"
        
        # Create lock file that would be created by pixi install
        lock_file = self.project_dir / "pixi.lock"
        lock_file.write_text("# Updated lock file")
        
        # Apply fix through workflow
        workflow = fix["workflow"]
        success, message = workflow.execute_workflow(error_output)
        
        assert success is True
        assert "Successfully executed: pixi install" in message
        mock_run_command.assert_called()
    
    def test_module_not_found_suggestion(self):
        """Test suggestion for missing Python module."""
        self.create_sample_project()
        
        engine = FailurePatternEngine(project_dir=str(self.project_dir))
        error_output = """
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    import pandas
ModuleNotFoundError: No module named 'pandas'
"""
        
        fix = engine.analyze(error_output)
        
        assert fix is not None
        assert fix["type"] == "dependency-fix"
        assert fix["pattern_id"] == "module_not_found_error"
        
        # Get workflow and execute
        workflow = fix["workflow"]
        success, message = workflow.execute_workflow(error_output)
        
        assert success is True
        assert "Module 'pandas' not found" in message
        assert "pixi add pandas" in message
    
    def test_dependency_conflict_notification(self):
        """Test notification for dependency conflicts."""
        self.create_sample_project()
        
        engine = FailurePatternEngine(project_dir=str(self.project_dir))
        error_output = """
Error: Conflict detected in package resolution:
- package1 requires python >=3.8,<3.9
- package2 requires python >=3.9,<3.10
"""
        
        fix = engine.analyze(error_output)
        
        assert fix is not None
        assert fix["type"] == "dependency-fix"
        assert fix["severity"] == "critical"
        
        # Execute workflow
        workflow = fix["workflow"]
        success, message = workflow.execute_workflow(error_output)
        
        assert success is False
        assert "Dependency conflict detected" in message
        assert "Manual intervention required" in message
    
    @patch('framework.self_healing.command_executor.SafeCommandExecutor.execute')
    def test_missing_lock_file_creation(self, mock_run_command):
        """Test creating missing pixi.lock file."""
        self.create_sample_project(with_lock=False)
        
        # Mock successful pixi install
        mock_result = MagicMock()
        mock_result.return_code = 0
        mock_result.stdout = "Creating lock file"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result
        
        engine = FailurePatternEngine(project_dir=str(self.project_dir))
        error_output = "Error: pixi.lock not found"
        
        fix = engine.analyze(error_output)
        
        assert fix is not None
        assert fix["pattern_id"] == "pixi_lock_missing"
        
        # Create lock file that would be created by pixi install
        lock_file = self.project_dir / "pixi.lock"
        lock_file.write_text("# New lock file")
        
        # Apply fix
        workflow = fix["workflow"]
        success, message = workflow.execute_workflow(error_output)
        
        assert success is True
        mock_run_command.assert_called()
    
    def test_special_module_mappings(self):
        """Test module name mappings for conda-forge packages."""
        self.create_sample_project()
        
        workflow = DependencyFixWorkflow(working_directory=str(self.project_dir))
        
        # Test OpenCV mapping
        suggestion = workflow.get_suggestion_for_module("cv2")
        assert "pixi add opencv" in suggestion
        
        # Test scikit-learn mapping
        suggestion = workflow.get_suggestion_for_module("sklearn")
        assert "pixi add scikit-learn" in suggestion
        
        # Test PIL/Pillow mapping
        suggestion = workflow.get_suggestion_for_module("PIL")
        assert "pixi add pillow" in suggestion
    
    @patch('subprocess.run')
    def test_git_commit_integration(self, mock_subprocess):
        """Test git commit after successful fix."""
        self.create_sample_project(with_lock=True)
        
        # Mock git commands
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "M pixi.lock"
        
        workflow = DependencyFixWorkflow(working_directory=str(self.project_dir))
        
        success, message = workflow._commit_changes("fix(deps): Update pixi.lock")
        
        assert success is True
        # Verify git commands were called
        calls = [call.args[0] for call in mock_subprocess.call_args_list]
        assert ["git", "status", "--porcelain"] in calls
    
    def test_end_to_end_workflow(self):
        """Test complete dependency resolution workflow."""
        self.create_sample_project()
        
        # Test multiple error scenarios
        test_cases = [
            {
                "error": "The lock file is not up-to-date with pyproject.toml",
                "expected_type": "dependency-fix",
                "expected_pattern": "pixi_lock_outdated"
            },
            {
                "error": "ModuleNotFoundError: No module named 'numpy'",
                "expected_type": "dependency-fix",
                "expected_pattern": "module_not_found_error"
            },
            {
                "error": "ImportError: No module named yaml",
                "expected_type": "dependency-fix",
                "expected_pattern": "import_error_no_module"
            }
        ]
        
        engine = FailurePatternEngine(project_dir=str(self.project_dir))
        
        for test_case in test_cases:
            fix = engine.analyze(test_case["error"])
            assert fix is not None
            assert fix["type"] == test_case["expected_type"]
            assert fix.get("pattern_id") == test_case["expected_pattern"]