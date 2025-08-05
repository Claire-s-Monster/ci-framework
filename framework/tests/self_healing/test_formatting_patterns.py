"""Tests for formatting pattern database schema and validation."""

import os
import re
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def formatting_config():
    """Load the formatting.yml configuration file."""
    config_path = (
        Path(__file__).parent.parent.parent / "self_healing" / "formatting.yml"
    )
    with open(config_path) as f:
        return yaml.safe_load(f)


def test_formatting_yml_schema_valid(formatting_config):
    """Test that formatting.yml has valid schema structure."""
    # Check top-level keys
    assert "version" in formatting_config
    assert "description" in formatting_config
    assert "patterns" in formatting_config
    assert "engine_config" in formatting_config
    assert "git_config" in formatting_config

    # Check version format
    assert isinstance(formatting_config["version"], str)
    assert re.match(r"\d+\.\d+", formatting_config["version"])


def test_pattern_structure(formatting_config):
    """Test that each pattern has required fields."""
    patterns = formatting_config["patterns"]

    required_fields = [
        "id",
        "name",
        "pattern",
        "description",
        "fix_command",
        "tool",
        "severity",
        "requires_git_commit",
        "commit_message_template",
    ]

    for tool_name, tool_patterns in patterns.items():
        assert isinstance(tool_patterns, list), (
            f"Patterns for {tool_name} should be a list"
        )

        for pattern in tool_patterns:
            for field in required_fields:
                assert field in pattern, (
                    f"Pattern {pattern.get('id', 'unknown')} missing field: {field}"
                )

            # Validate field types
            assert isinstance(pattern["id"], str)
            assert isinstance(pattern["name"], str)
            assert isinstance(pattern["pattern"], str)
            assert isinstance(pattern["description"], str)
            assert isinstance(pattern["fix_command"], str)
            assert isinstance(pattern["tool"], str)
            assert isinstance(pattern["requires_git_commit"], bool)
            assert isinstance(pattern["commit_message_template"], str)

            # Validate severity values
            assert pattern["severity"] in ["low", "medium", "high"]


def test_regex_patterns_valid(formatting_config):
    """Test that all regex patterns are valid and can be compiled."""
    patterns = formatting_config["patterns"]

    for _tool_name, tool_patterns in patterns.items():
        for pattern in tool_patterns:
            regex_pattern = pattern["pattern"]
            try:
                re.compile(regex_pattern)
            except re.error as e:
                pytest.fail(
                    f"Invalid regex pattern '{regex_pattern}' in {pattern['id']}: {e}"
                )


def test_ruff_pattern_matching():
    """Test ruff pattern matching with sample output."""
    # Sample ruff output
    ruff_output = "Found 5 errors (3 fixable with the `--fix` option)."

    # Load patterns
    config_path = (
        Path(__file__).parent.parent.parent / "self_healing" / "formatting.yml"
    )
    with open(config_path) as f:
        config = yaml.safe_load(f)

    ruff_patterns = config["patterns"]["ruff"]
    fixable_pattern = next(p for p in ruff_patterns if p["id"] == "ruff_fixable_errors")

    match = re.search(fixable_pattern["pattern"], ruff_output)
    assert match is not None, "Should match ruff fixable errors pattern"
    assert match.group(1) == "5", "Should extract total error count"
    assert match.group(2) == "3", "Should extract fixable error count"


def test_black_pattern_matching():
    """Test black pattern matching with sample output."""
    # Sample black output
    black_output = "would reformat 3 files"

    # Load patterns
    config_path = (
        Path(__file__).parent.parent.parent / "self_healing" / "formatting.yml"
    )
    with open(config_path) as f:
        config = yaml.safe_load(f)

    black_patterns = config["patterns"]["black"]
    reformat_pattern = next(
        p for p in black_patterns if p["id"] == "black_would_reformat"
    )

    match = re.search(reformat_pattern["pattern"], black_output)
    assert match is not None, "Should match black reformat pattern"
    assert match.group(1) == "3", "Should extract file count"


def test_isort_pattern_matching():
    """Test isort pattern matching with sample output."""
    # Sample isort output
    isort_output = "Fixing 2 files"

    # Load patterns
    config_path = (
        Path(__file__).parent.parent.parent / "self_healing" / "formatting.yml"
    )
    with open(config_path) as f:
        config = yaml.safe_load(f)

    isort_patterns = config["patterns"]["isort"]
    fixing_pattern = next(p for p in isort_patterns if p["id"] == "isort_would_sort")

    match = re.search(fixing_pattern["pattern"], isort_output)
    assert match is not None, "Should match isort fixing pattern"
    assert match.group(1) == "2", "Should extract file count"


def test_engine_config_structure(formatting_config):
    """Test engine configuration has required structure."""
    engine_config = formatting_config["engine_config"]

    required_fields = [
        "timeout_seconds",
        "max_file_size_mb",
        "backup_before_fix",
        "verify_syntax_after_fix",
        "allowed_file_extensions",
        "exclude_patterns",
    ]

    for field in required_fields:
        assert field in engine_config, f"Engine config missing field: {field}"

    # Validate types
    assert isinstance(engine_config["timeout_seconds"], int)
    assert isinstance(engine_config["max_file_size_mb"], int)
    assert isinstance(engine_config["backup_before_fix"], bool)
    assert isinstance(engine_config["verify_syntax_after_fix"], bool)
    assert isinstance(engine_config["allowed_file_extensions"], list)
    assert isinstance(engine_config["exclude_patterns"], list)


def test_git_config_structure(formatting_config):
    """Test git configuration has required structure."""
    git_config = formatting_config["git_config"]

    required_fields = [
        "create_commit",
        "commit_author",
        "commit_prefix",
        "include_file_count",
    ]

    for field in required_fields:
        assert field in git_config, f"Git config missing field: {field}"

    # Validate types
    assert isinstance(git_config["create_commit"], bool)
    assert isinstance(git_config["commit_author"], str)
    assert isinstance(git_config["commit_prefix"], str)
    assert isinstance(git_config["include_file_count"], bool)


def test_pattern_ids_unique(formatting_config):
    """Test that all pattern IDs are unique across all tools."""
    patterns = formatting_config["patterns"]
    all_ids = []

    for _tool_name, tool_patterns in patterns.items():
        for pattern in tool_patterns:
            pattern_id = pattern["id"]
            assert pattern_id not in all_ids, f"Duplicate pattern ID: {pattern_id}"
            all_ids.append(pattern_id)


def test_fix_commands_not_empty(formatting_config):
    """Test that all fix commands are non-empty and reasonable."""
    patterns = formatting_config["patterns"]

    for _tool_name, tool_patterns in patterns.items():
        for pattern in tool_patterns:
            fix_command = pattern["fix_command"]
            assert fix_command.strip(), f"Empty fix command in pattern {pattern['id']}"
            assert len(fix_command) > 5, (
                f"Fix command too short in pattern {pattern['id']}"
            )


def test_commit_message_templates_valid(formatting_config):
    """Test that commit message templates follow conventional commit format."""
    patterns = formatting_config["patterns"]

    # Pattern for conventional commits: type(scope): description
    commit_pattern = re.compile(
        r"^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+"
    )

    for _tool_name, tool_patterns in patterns.items():
        for pattern in tool_patterns:
            commit_template = pattern["commit_message_template"]
            assert commit_pattern.match(commit_template), (
                f"Invalid commit message template in {pattern['id']}: {commit_template}"
            )
