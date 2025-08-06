"""
Unit tests for dependency pattern recognition.

This module tests the dependency pattern matching functionality
to ensure proper detection of dependency-related issues.
"""

import pytest

from framework.self_healing.dependency_engine import DependencyEngine


class TestDependencyPatternRecognition:
    """Test dependency pattern matching."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DependencyEngine()

    def test_pixi_lock_outdated_detection(self):
        """Test detection of outdated pixi.lock files."""
        output = """
        Error: The lock file is not up-to-date with pyproject.toml
        Please run 'pixi install' to update the lock file.
        """

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "pixi_lock_outdated"
        assert match.tool == "pixi"
        assert match.fix_command == "pixi install"
        assert match.severity == "high"
        assert match.requires_git_commit is True

    def test_pixi_lock_missing_detection(self):
        """Test detection of missing pixi.lock file."""
        output = "Error: pixi.lock not found in the project directory"

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "pixi_lock_missing"
        assert match.tool == "pixi"
        assert match.fix_command == "pixi install"

    def test_module_not_found_error_detection(self):
        """Test detection of ModuleNotFoundError."""
        output = """
        Traceback (most recent call last):
          File "test.py", line 1, in <module>
            import requests
        ModuleNotFoundError: No module named 'requests'
        """

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "module_not_found_error"
        assert match.tool == "python"
        assert match.custom_handler == "suggest_pixi_add"
        assert match.captured_data.get("module_name") == "requests"
        assert "pixi add requests" in match.handler_message

    def test_import_error_detection(self):
        """Test detection of ImportError."""
        output = "ImportError: No module named 'numpy'"

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "import_error_no_module"
        assert match.captured_data.get("module_name") == "numpy"

    def test_dependency_conflict_detection(self):
        """Test detection of dependency conflicts."""
        output = """
        Error: Conflict detected in package resolution:
        - package1 requires python >=3.8,<3.9
        - package2 requires python >=3.9,<3.10
        """

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "pixi_conflict_detected"
        assert match.severity == "critical"
        assert match.custom_handler == "notify_conflict"

    def test_no_pattern_match(self):
        """Test that non-dependency errors don't match."""
        output = "SyntaxError: invalid syntax"

        match = self.engine.match_pattern(output)

        assert match is None

    def test_suggest_fix_for_module_error(self):
        """Test fix suggestion for module errors."""
        output = "ModuleNotFoundError: No module named 'pandas'"

        fix_info = self.engine.suggest_fix(output)

        assert fix_info is not None
        assert fix_info["pattern_id"] == "module_not_found_error"
        assert fix_info["action"] == "suggest_pixi_add"
        assert "pixi add pandas" in fix_info["message"]

    def test_suggest_fix_for_lock_file(self):
        """Test fix suggestion for lock file issues."""
        output = "The lock file is not up-to-date with pyproject.toml"

        fix_info = self.engine.suggest_fix(output)

        assert fix_info is not None
        assert fix_info["pattern_id"] == "pixi_lock_outdated"
        assert fix_info["action"] == "execute"
        assert fix_info["fix_command"] == "pixi install"

    def test_pyproject_toml_changed_detection(self):
        """Test detection of pyproject.toml changes."""
        output = "Warning: pyproject.toml has been modified since last install"

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "pyproject_toml_changed"
        assert match.severity == "medium"
        assert match.fix_command == "pixi install"

    def test_missing_dependencies_detection(self):
        """Test detection of missing dependencies."""
        output = """
        The following dependencies are missing:
        - pytest
        - black
        - ruff
        """

        match = self.engine.match_pattern(output)

        assert match is not None
        assert match.pattern_id == "missing_dependencies"
        assert match.severity == "high"
        assert match.fix_command == "pixi install"
