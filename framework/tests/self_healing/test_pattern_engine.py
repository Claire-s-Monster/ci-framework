import pytest

from framework.self_healing.pattern_engine import FailurePatternEngine


def test_analyze_returns_fix():
    engine = FailurePatternEngine()
    fix = engine.analyze()
    assert fix is not None
    assert fix["type"] == "dummy-fix"


def test_analyze_formatting_fix():
    """Test that formatting issues are detected and return correct fix type."""
    engine = FailurePatternEngine()

    # Test ruff formatting error
    ruff_output = "Found 5 errors (3 fixable with the `--fix` option)."
    fix = engine.analyze(ruff_output)

    assert fix is not None
    assert fix["type"] == "formatting-fix"
    assert fix["tool"] == "ruff"
    assert "workflow" in fix


def test_analyze_dependency_fix():
    """Test that dependency issues are detected and return correct fix type."""
    engine = FailurePatternEngine()

    # Test outdated lock file
    lock_output = "The lock file is not up-to-date with pyproject.toml"
    fix = engine.analyze(lock_output)

    assert fix is not None
    assert fix["type"] == "dependency-fix"
    assert fix["pattern_id"] == "pixi_lock_outdated"
    assert fix["tool"] == "pixi"
    assert fix["severity"] == "high"
    assert "workflow" in fix


def test_analyze_module_not_found():
    """Test detection of ModuleNotFoundError."""
    engine = FailurePatternEngine()

    module_error = "ModuleNotFoundError: No module named 'requests'"
    fix = engine.analyze(module_error)

    assert fix is not None
    assert fix["type"] == "dependency-fix"
    assert fix["pattern_id"] == "module_not_found_error"
    assert fix["tool"] == "python"


def test_analyze_no_match_returns_dummy():
    """Test that unmatched output returns dummy fix for backward compatibility."""
    engine = FailurePatternEngine()

    unknown_output = "Some random error that doesn't match any pattern"
    fix = engine.analyze(unknown_output)

    assert fix is not None
    assert fix["type"] == "dummy-fix"
    assert fix["details"] == "Simulated fix"
