"""Tests for the integrated formatting workflow."""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from framework.self_healing.formatting_workflow import (
    FormattingFixWorkflow, WorkflowResult, FormattingWorkflowError
)
from framework.self_healing.formatting_engine import MatchResult
from framework.self_healing.command_executor import CommandResult
from framework.self_healing.syntax_verifier import GitCommitResult


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def workflow(temp_dir):
    """Create a FormattingFixWorkflow instance for testing."""
    return FormattingFixWorkflow(
        working_directory=str(temp_dir),
        enable_logging=False  # Disable logging for tests
    )


@pytest.fixture
def mock_match_result():
    """Create a mock MatchResult for testing."""
    return MatchResult(
        pattern_id="ruff_fixable_errors",
        tool="ruff",
        fix_command="ruff check --fix .",
        commit_message_template="fix(format): Auto-fix ruff violations",
        severity="medium",
        requires_git_commit=True,
        matched_groups=["Found 5 errors (3 fixable)", "5", "3"],
        original_output="Found 5 errors (3 fixable with the `--fix` option).",
        description="Detects when ruff finds fixable errors"
    )


@pytest.fixture
def mock_command_result():
    """Create a mock CommandResult for testing."""
    return CommandResult(
        command="ruff check --fix .",
        return_code=0,
        stdout="Fixed 3 errors",
        stderr="",
        execution_time=2.5,
        timed_out=False,
        working_directory="/test/dir"
    )


@pytest.fixture
def mock_git_commit_result():
    """Create a mock GitCommitResult for testing."""
    return GitCommitResult(
        success=True,
        commit_hash="abc123",
        message="fix(format): Auto-fix ruff violations (2 files)",
        files_committed=["test.py", "module.py"]
    )


def test_workflow_initialization(temp_dir):
    """Test workflow initialization."""
    workflow = FormattingFixWorkflow(working_directory=str(temp_dir))
    
    assert workflow.working_directory == temp_dir
    assert workflow.pattern_engine is not None
    assert workflow.command_executor is not None
    assert workflow.syntax_verifier is not None


def test_workflow_initialization_with_config():
    """Test workflow initialization with custom config."""
    with tempfile.NamedTemporaryFile(suffix='.yml', delete=False) as config_file:
        config_path = config_file.name
    
    try:
        workflow = FormattingFixWorkflow(config_path=config_path)
        assert workflow.pattern_engine.config_path == Path(config_path)
    finally:
        Path(config_path).unlink()


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_no_match(mock_verifier, mock_executor, mock_engine, workflow):
    """Test processing tool output with no pattern match."""
    # Mock pattern engine to return no match
    mock_engine.return_value.match_output.return_value = None
    
    result = workflow.process_tool_output("No fixable issues found")
    
    assert isinstance(result, WorkflowResult)
    assert result.success is False
    assert "No fixable formatting issues detected" in result.message
    assert result.pattern_matched is None


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_dry_run(mock_verifier, mock_executor, mock_engine, workflow, mock_match_result, mock_command_result):
    """Test processing tool output in dry-run mode."""
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    
    # Mock dry-run command execution
    mock_executor.return_value.dry_run_command.return_value = mock_command_result
    
    result = workflow.process_tool_output(
        "Found 5 errors (3 fixable with the `--fix` option).",
        dry_run=True
    )
    
    assert result.success is True
    assert "Dry run completed" in result.message
    assert result.pattern_matched == "ruff_fixable_errors"
    assert result.tool_used == "ruff"
    assert result.command_executed == "ruff check --fix ."


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_success_with_commit(
    mock_verifier, mock_executor, mock_engine, workflow, 
    mock_match_result, mock_command_result, mock_git_commit_result
):
    """Test successful processing with commit."""
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    mock_engine.return_value.get_git_config.return_value = {
        'commit_author': 'Test <test@example.com>',
        'include_file_count': True
    }
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock syntax verification and git commit
    mock_verifier.return_value.atomic_format_commit.return_value = mock_git_commit_result
    
    result = workflow.process_tool_output(
        "Found 5 errors (3 fixable with the `--fix` option).",
        create_commit=True
    )
    
    assert result.success is True
    assert "Successfully fixed and committed" in result.message
    assert result.pattern_matched == "ruff_fixable_errors"
    assert result.tool_used == "ruff"
    assert result.files_fixed == ["test.py", "module.py"]
    assert result.commit_result.success is True


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_without_commit(
    mock_verifier, mock_executor, mock_engine, workflow,
    mock_match_result, mock_command_result
):
    """Test processing without creating commit."""
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock getting changed files
    mock_verifier.return_value.get_changed_files.return_value = ["test.py"]
    
    result = workflow.process_tool_output(
        "Found 5 errors (3 fixable with the `--fix` option).",
        create_commit=False
    )
    
    assert result.success is True
    assert "Successfully applied" in result.message
    assert result.files_fixed == ["test.py"]
    assert result.commit_result is None


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_commit_failure(
    mock_verifier, mock_executor, mock_engine, workflow,
    mock_match_result, mock_command_result
):
    """Test processing with commit failure."""
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    mock_engine.return_value.get_git_config.return_value = {}
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock failed commit
    failed_commit = GitCommitResult(
        success=False,
        error_message="Commit failed: no changes staged"
    )
    mock_verifier.return_value.atomic_format_commit.return_value = failed_commit
    
    result = workflow.process_tool_output(
        "Found 5 errors (3 fixable with the `--fix` option)."
    )
    
    assert result.success is False
    assert "Fix applied but commit failed" in result.message
    assert result.error_details == "Commit failed: no changes staged"


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_tool_output_syntax_error(
    mock_verifier, mock_executor, mock_engine, workflow,
    mock_match_result, mock_command_result
):
    """Test processing with syntax verification error."""
    from framework.self_healing.syntax_verifier import SyntaxVerificationError, SyntaxCheckResult
    
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    mock_engine.return_value.get_git_config.return_value = {}
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock syntax verification failure
    failed_syntax = SyntaxCheckResult(
        file_path="test.py",
        is_valid=False,
        error_message="Syntax error"
    )
    mock_verifier.return_value.atomic_format_commit.side_effect = SyntaxVerificationError(
        "Syntax errors found", [failed_syntax]
    )
    
    result = workflow.process_tool_output(
        "Found 5 errors (3 fixable with the `--fix` option)."
    )
    
    assert result.success is False
    assert "Syntax errors detected" in result.message


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_get_workflow_status(mock_verifier, mock_executor, mock_engine, workflow):
    """Test getting workflow status."""
    # Mock components
    mock_engine.return_value.patterns = {'ruff': [{'id': 'test'}]}
    mock_engine.return_value.get_all_tools.return_value = ['ruff', 'black']
    mock_engine.return_value.get_engine_config.return_value = {'timeout': 300}
    mock_engine.return_value.get_git_config.return_value = {'create_commit': True}
    
    mock_verifier.return_value.is_git_repository.return_value = True
    mock_verifier.return_value.get_git_status_summary.return_value = {'modified': 0}
    
    status = workflow.get_workflow_status()
    
    assert 'working_directory' in status
    assert 'is_git_repository' in status
    assert 'available_patterns' in status
    assert 'supported_tools' in status
    assert status['supported_tools'] == ['ruff', 'black']


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_validate_configuration_success(mock_verifier, mock_executor, mock_engine, workflow):
    """Test configuration validation with no errors."""
    # Mock successful validation
    mock_engine.return_value.validate_patterns.return_value = []
    mock_engine.return_value.get_all_tools.return_value = ['ruff']
    mock_verifier.return_value.is_git_repository.return_value = True
    mock_executor.return_value.get_command_info.return_value = {'available': True}
    
    errors = workflow.validate_configuration()
    assert len(errors) == 0


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_validate_configuration_with_errors(mock_verifier, mock_executor, mock_engine, workflow):
    """Test configuration validation with errors."""
    # Mock validation errors
    mock_engine.return_value.validate_patterns.return_value = ["Invalid pattern"]
    mock_engine.return_value.get_all_tools.return_value = ['ruff']
    mock_verifier.return_value.is_git_repository.return_value = False
    mock_executor.return_value.get_command_info.return_value = {
        'available': False, 
        'error': 'Tool not found'
    }
    
    errors = workflow.validate_configuration()
    assert len(errors) >= 3  # Pattern error, git error, tool error


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
def test_test_pattern_matching(mock_engine, workflow, mock_match_result):
    """Test pattern matching testing method."""
    mock_engine.return_value.match_output.return_value = mock_match_result
    
    result = workflow.test_pattern_matching("Found 5 errors (3 fixable)")
    
    assert result == mock_match_result
    mock_engine.return_value.match_output.assert_called_once_with("Found 5 errors (3 fixable)")


@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
def test_get_tool_info(mock_executor, workflow):
    """Test getting tool information."""
    expected_info = {'available': True, 'version': '0.1.0'}
    mock_executor.return_value.get_command_info.return_value = expected_info
    
    result = workflow.get_tool_info('ruff')
    
    assert result == expected_info
    mock_executor.return_value.get_command_info.assert_called_once_with('ruff')


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_multiple_outputs(
    mock_verifier, mock_executor, mock_engine, workflow,
    mock_match_result, mock_command_result, mock_git_commit_result
):
    """Test processing multiple tool outputs."""
    # Mock pattern matching for both outputs
    mock_engine.return_value.match_output.return_value = mock_match_result
    mock_engine.return_value.get_git_config.return_value = {}
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock successful commits
    mock_verifier.return_value.atomic_format_commit.return_value = mock_git_commit_result
    
    outputs = [
        "Found 5 errors (3 fixable with the `--fix` option).",
        "Found 2 errors (1 fixable with the `--fix` option)."
    ]
    
    results = workflow.process_multiple_outputs(outputs)
    
    assert len(results) == 2
    assert all(result.success for result in results)


@patch('framework.self_healing.formatting_workflow.FormattingPatternEngine')
@patch('framework.self_healing.formatting_workflow.SafeCommandExecutor')
@patch('framework.self_healing.formatting_workflow.SyntaxVerifierAndCommitter')
def test_process_multiple_outputs_failure(
    mock_verifier, mock_executor, mock_engine, workflow,
    mock_match_result, mock_command_result
):
    """Test processing multiple outputs with failure."""
    # Mock pattern matching
    mock_engine.return_value.match_output.return_value = mock_match_result
    mock_engine.return_value.get_git_config.return_value = {}
    
    # Mock command execution
    mock_executor.return_value.execute_formatting_command.return_value = mock_command_result
    
    # Mock first commit success, second commit failure
    mock_verifier.return_value.atomic_format_commit.side_effect = [
        GitCommitResult(success=True, commit_hash="abc123"),
        GitCommitResult(success=False, error_message="Commit failed")
    ]
    
    outputs = [
        "Found 5 errors (3 fixable with the `--fix` option).",
        "Found 2 errors (1 fixable with the `--fix` option)."
    ]
    
    results = workflow.process_multiple_outputs(outputs)
    
    assert len(results) == 2  # Should process both
    assert results[0].success is True
    assert results[1].success is False


def test_workflow_result_dataclass():
    """Test WorkflowResult dataclass initialization."""
    result = WorkflowResult(
        success=True,
        message="Test message",
        pattern_matched="test_pattern",
        tool_used="ruff"
    )
    
    assert result.success is True
    assert result.message == "Test message"
    assert result.pattern_matched == "test_pattern"
    assert result.tool_used == "ruff"
    assert result.files_fixed == []  # Should initialize to empty list


def test_workflow_result_with_files():
    """Test WorkflowResult with files specified."""
    files = ["test.py", "module.py"]
    result = WorkflowResult(
        success=True,
        message="Test message",
        files_fixed=files
    )
    
    assert result.files_fixed == files