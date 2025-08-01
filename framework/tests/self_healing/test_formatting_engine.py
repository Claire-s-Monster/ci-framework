"""Tests for the formatting pattern matching engine."""

import pytest
import tempfile
import yaml
from pathlib import Path

from framework.self_healing.formatting_engine import FormattingPatternEngine, MatchResult


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return {
        "version": "1.0",
        "description": "Test configuration",
        "patterns": {
            "ruff": [
                {
                    "id": "ruff_fixable_errors", 
                    "name": "Ruff fixable errors detected",
                    "pattern": r"Found (\d+) error.*\((\d+) fixable.*\)",
                    "description": "Detects when ruff finds fixable errors",
                    "fix_command": "ruff check --fix .",
                    "tool": "ruff",
                    "severity": "medium",
                    "requires_git_commit": True,
                    "commit_message_template": "fix(format): Auto-fix ruff formatting violations"
                }
            ],
            "black": [
                {
                    "id": "black_would_reformat",
                    "name": "Black would reformat files", 
                    "pattern": r"would reformat (\d+) files?",
                    "description": "Detects when black would reformat files",
                    "fix_command": "black .",
                    "tool": "black",
                    "severity": "medium", 
                    "requires_git_commit": True,
                    "commit_message_template": "fix(format): Auto-format code with black"
                }
            ]
        },
        "engine_config": {
            "timeout_seconds": 300,
            "max_file_size_mb": 50,
            "backup_before_fix": True,
            "verify_syntax_after_fix": True
        },
        "git_config": {
            "create_commit": True,
            "commit_author": "Self-Healing CI <ci@framework.local>",
            "commit_prefix": "fix(format): "
        }
    }


@pytest.fixture  
def temp_config_file(sample_config):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(sample_config, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    temp_path.unlink()


def test_engine_initialization_with_default_config():
    """Test engine initializes with default config path."""
    engine = FormattingPatternEngine()
    assert engine.config_path is not None
    assert isinstance(engine.patterns, dict)


def test_engine_initialization_with_custom_config(temp_config_file):
    """Test engine initializes with custom config path."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    assert str(engine.config_path) == str(temp_config_file)
    assert "ruff" in engine.patterns
    assert "black" in engine.patterns


def test_engine_initialization_with_missing_config():
    """Test engine fails gracefully with missing config file."""
    with pytest.raises(FileNotFoundError):
        FormattingPatternEngine(config_path="/nonexistent/config.yml")


def test_ruff_pattern_matching(temp_config_file):
    """Test ruff pattern matching with sample output."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    # Sample ruff output
    ruff_output = "Found 5 errors (3 fixable with the `--fix` option)."
    
    result = engine.match_output(ruff_output)
    
    assert result is not None
    assert isinstance(result, MatchResult)
    assert result.pattern_id == "ruff_fixable_errors"
    assert result.tool == "ruff"
    assert result.fix_command == "ruff check --fix ."
    assert result.severity == "medium"
    assert result.requires_git_commit is True
    assert len(result.matched_groups) == 3  # Full match + 2 capture groups
    assert result.matched_groups[1] == "5"  # Total errors
    assert result.matched_groups[2] == "3"  # Fixable errors


def test_black_pattern_matching(temp_config_file):
    """Test black pattern matching with sample output."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    # Sample black output
    black_output = "would reformat 3 files"
    
    result = engine.match_output(black_output)
    
    assert result is not None
    assert result.pattern_id == "black_would_reformat"
    assert result.tool == "black"
    assert result.fix_command == "black ."
    assert result.matched_groups[1] == "3"  # File count


def test_no_match_for_unknown_output(temp_config_file):
    """Test that unknown output returns None."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    # Output that doesn't match any pattern
    unknown_output = "Everything is perfect, no issues found!"
    
    result = engine.match_output(unknown_output)
    assert result is None


def test_empty_output_returns_none(temp_config_file):
    """Test that empty output returns None."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    result = engine.match_output("")
    assert result is None
    
    result = engine.match_output("   ")
    assert result is None


def test_match_specific_tool(temp_config_file):
    """Test matching output against patterns for a specific tool only."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    # This output matches both ruff and black patterns in our test config
    ruff_output = "Found 5 errors (3 fixable with the `--fix` option)."
    
    # Test ruff-specific matching
    result = engine.match_specific_tool(ruff_output, "ruff")
    assert result is not None
    assert result.tool == "ruff"
    
    # Test black-specific matching (should return None for ruff output)
    result = engine.match_specific_tool(ruff_output, "black")
    assert result is None


def test_get_patterns_by_tool(temp_config_file):
    """Test getting patterns for a specific tool."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    ruff_patterns = engine.get_patterns_by_tool("ruff")
    assert len(ruff_patterns) == 1
    assert ruff_patterns[0]["id"] == "ruff_fixable_errors"
    
    black_patterns = engine.get_patterns_by_tool("black")
    assert len(black_patterns) == 1
    assert black_patterns[0]["id"] == "black_would_reformat"
    
    unknown_patterns = engine.get_patterns_by_tool("unknown_tool")
    assert len(unknown_patterns) == 0


def test_get_all_tools(temp_config_file):
    """Test getting list of all tools."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    tools = engine.get_all_tools()
    assert set(tools) == {"ruff", "black"}


def test_get_engine_config(temp_config_file):
    """Test getting engine configuration."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    config = engine.get_engine_config()
    assert config["timeout_seconds"] == 300
    assert config["max_file_size_mb"] == 50
    assert config["backup_before_fix"] is True


def test_get_git_config(temp_config_file):
    """Test getting git configuration."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    config = engine.get_git_config()
    assert config["create_commit"] is True
    assert config["commit_author"] == "Self-Healing CI <ci@framework.local>"


def test_pattern_validation_success(temp_config_file):
    """Test pattern validation with valid patterns."""
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    errors = engine.validate_patterns()
    assert len(errors) == 0


def test_pattern_validation_with_invalid_regex():
    """Test pattern validation catches invalid regex patterns."""
    invalid_config = {
        "patterns": {
            "test": [
                {
                    "id": "invalid_regex",
                    "name": "Invalid regex",
                    "pattern": r"[unclosed_bracket",  # Invalid regex
                    "description": "Test invalid regex",
                    "fix_command": "test",
                    "tool": "test",
                    "severity": "low",
                    "requires_git_commit": True,
                    "commit_message_template": "fix: test"
                }
            ]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(invalid_config, f)
        temp_path = Path(f.name)
    
    try:
        engine = FormattingPatternEngine(config_path=str(temp_path))
        errors = engine.validate_patterns()
        assert len(errors) > 0
        assert "Invalid regex" in errors[0]
    finally:
        temp_path.unlink()


def test_pattern_validation_with_missing_fields():
    """Test pattern validation catches missing required fields."""
    invalid_config = {
        "patterns": {
            "test": [
                {
                    "id": "missing_fields",
                    "name": "Missing fields",
                    # Missing required fields like pattern, fix_command, etc.
                }
            ]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(invalid_config, f)
        temp_path = Path(f.name)
    
    try:
        engine = FormattingPatternEngine(config_path=str(temp_path))
        errors = engine.validate_patterns()
        assert len(errors) > 0
        assert "missing field" in errors[0].lower()
    finally:
        temp_path.unlink()


def test_pattern_validation_with_invalid_severity():
    """Test pattern validation catches invalid severity values."""
    invalid_config = {
        "patterns": {
            "test": [
                {
                    "id": "invalid_severity",
                    "name": "Invalid severity",
                    "pattern": r"test",
                    "description": "Test invalid severity",
                    "fix_command": "test",
                    "tool": "test",
                    "severity": "invalid",  # Should be low/medium/high
                    "requires_git_commit": True,
                    "commit_message_template": "fix: test"
                }
            ]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(invalid_config, f)
        temp_path = Path(f.name)
    
    try:
        engine = FormattingPatternEngine(config_path=str(temp_path))
        errors = engine.validate_patterns()
        assert len(errors) > 0
        assert "Invalid severity" in errors[0]
    finally:
        temp_path.unlink()


def test_multiline_pattern_matching(temp_config_file):
    """Test pattern matching works with multiline output.""" 
    engine = FormattingPatternEngine(config_path=str(temp_config_file))
    
    # Multiline output
    multiline_output = """
    Checking code...
    Found 5 errors (3 fixable with the `--fix` option).
    Process completed.
    """
    
    result = engine.match_output(multiline_output)
    assert result is not None
    assert result.pattern_id == "ruff_fixable_errors"