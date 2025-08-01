"""Tests for syntax verification and git commit module."""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from framework.self_healing.syntax_verifier import (
    SyntaxVerifierAndCommitter, SyntaxCheckResult, GitCommitResult,
    SyntaxVerificationError, GitOperationError
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def verifier(temp_dir):
    """Create a SyntaxVerifierAndCommitter instance."""
    return SyntaxVerifierAndCommitter(working_directory=str(temp_dir))


def test_verifier_initialization():
    """Test verifier initialization."""
    verifier = SyntaxVerifierAndCommitter()
    assert verifier.working_directory == Path.cwd().resolve()


def test_verifier_initialization_with_custom_directory(temp_dir):
    """Test verifier initialization with custom directory."""
    verifier = SyntaxVerifierAndCommitter(working_directory=str(temp_dir))
    assert verifier.working_directory == temp_dir


@patch('subprocess.run')
def test_is_git_repository_true(mock_run, verifier):
    """Test git repository detection returns True."""
    mock_run.return_value = MagicMock(returncode=0)
    assert verifier.is_git_repository() is True


@patch('subprocess.run')
def test_is_git_repository_false(mock_run, verifier):
    """Test git repository detection returns False."""
    mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
    assert verifier.is_git_repository() is False


def test_check_python_syntax_valid_file(verifier, temp_dir):
    """Test syntax checking with valid Python file."""
    # Create valid Python file
    test_file = temp_dir / "valid.py"
    test_file.write_text("def hello():\n    return 'world'\n")
    
    result = verifier.check_python_syntax("valid.py")
    
    assert isinstance(result, SyntaxCheckResult)
    assert result.file_path == "valid.py"
    assert result.is_valid is True
    assert result.error_message is None


def test_check_python_syntax_invalid_file(verifier, temp_dir):
    """Test syntax checking with invalid Python file."""
    # Create invalid Python file
    test_file = temp_dir / "invalid.py"
    test_file.write_text("def hello(\n    return 'world'\n")  # Missing closing parenthesis
    
    result = verifier.check_python_syntax("invalid.py")
    
    assert isinstance(result, SyntaxCheckResult)
    assert result.file_path == "invalid.py"
    assert result.is_valid is False
    assert result.error_message is not None
    assert result.line_number is not None


def test_check_python_syntax_nonexistent_file(verifier):
    """Test syntax checking with nonexistent file."""
    result = verifier.check_python_syntax("nonexistent.py")
    
    assert result.is_valid is False
    assert "File not found" in result.error_message


@patch('subprocess.run')
def test_get_changed_files_no_changes(mock_run, verifier):
    """Test getting changed files when there are no changes."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    files = verifier.get_changed_files()
    assert files == []


@patch('subprocess.run')
def test_get_changed_files_with_changes(mock_run, verifier):
    """Test getting changed files when there are changes."""
    mock_run.return_value = MagicMock(stdout="M  test.py\n", returncode=0)
    files = verifier.get_changed_files()
    assert "test.py" in files


@patch('subprocess.run')
def test_stage_changes_all(mock_run, verifier):
    """Test staging all changes."""
    mock_run.return_value = MagicMock(returncode=0)
    with patch.object(verifier, 'get_changed_files', return_value=['test.py']):
        staged_files = verifier.stage_changes()
        assert "test.py" in staged_files


@patch('subprocess.run')
def test_stage_changes_specific_files(mock_run, verifier):
    """Test staging specific files."""
    mock_run.return_value = MagicMock(returncode=0)
    staged_files = verifier.stage_changes(files=["test1.py"])
    assert staged_files == ["test1.py"]


@patch('subprocess.run')
def test_create_commit_success(mock_run, verifier):
    """Test successful commit creation."""
    # Mock git diff --cached --name-only to return staged files
    mock_run.side_effect = [
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] Test commit message\n", returncode=0)  # git commit
    ]
    
    result = verifier.create_commit("Test commit message")
    
    assert isinstance(result, GitCommitResult)
    assert result.success is True
    assert result.message == "Test commit message (1 file)"
    assert "test.py" in result.files_committed
    assert result.commit_hash == "abc123"


@patch('subprocess.run')
def test_create_commit_with_custom_author(mock_run, verifier):
    """Test commit creation with custom author."""
    mock_run.side_effect = [
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] Test commit\n", returncode=0)  # git commit
    ]
    
    result = verifier.create_commit(
        "Test commit", 
        author="Custom Author <custom@example.com>"
    )
    
    assert result.success is True


@patch('subprocess.run')
def test_create_commit_no_file_count(mock_run, verifier):
    """Test commit creation without file count in message."""
    mock_run.side_effect = [
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] Test commit\n", returncode=0)  # git commit
    ]
    
    result = verifier.create_commit("Test commit", include_file_count=False)
    
    assert result.success is True
    assert result.message == "Test commit"


@patch('subprocess.run')
def test_verify_changed_files_syntax_success(mock_run, verifier, temp_dir):
    """Test syntax verification with valid files."""
    # Create valid Python files
    test_file1 = temp_dir / "test1.py"
    test_file1.write_text("def hello(): return 'world'")
    test_file2 = temp_dir / "test2.py"
    test_file2.write_text("print('hello')")
    
    # Mock git status to return these files
    mock_run.return_value = MagicMock(stdout="M  test1.py\nM  test2.py\n", returncode=0)
    
    results = verifier.verify_changed_files_syntax()
    
    assert len(results) == 2
    for result in results:
        assert result.is_valid is True


@patch('subprocess.run')
def test_verify_changed_files_syntax_failure(mock_run, verifier, temp_dir):
    """Test syntax verification with invalid files."""
    # Create invalid Python file
    test_file = temp_dir / "invalid.py"
    test_file.write_text("def hello(\n    return 'world'")  # Syntax error
    
    # Mock git status to return this file
    mock_run.return_value = MagicMock(stdout="M  invalid.py\n", returncode=0)
    
    with pytest.raises(SyntaxVerificationError) as exc_info:
        verifier.verify_changed_files_syntax()
    
    assert len(exc_info.value.failed_files) == 1
    assert exc_info.value.failed_files[0].file_path == "invalid.py"


@patch('subprocess.run')
def test_restore_changes(mock_run, verifier):
    """Test restoring changes."""
    mock_run.return_value = MagicMock(returncode=0)
    
    # Should not raise any exception
    verifier.restore_changes()
    
    # Verify git restore commands were called
    assert mock_run.call_count == 2


@patch('subprocess.run')
def test_atomic_format_commit_success(mock_run, verifier, temp_dir):
    """Test successful atomic format commit."""
    # Create valid Python file
    test_file = temp_dir / "test.py"
    test_file.write_text("def hello(): return 'world'")
    
    # Mock all git operations
    mock_run.side_effect = [
        MagicMock(stdout="M  test.py\n", returncode=0),  # get_changed_files (verify_syntax)
        MagicMock(returncode=0),  # git add .
        MagicMock(stdout="M  test.py\n", returncode=0),  # get_changed_files (stage_changes)
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] fix(format): Auto-fix black violations (1 file)\n", returncode=0)  # git commit
    ]
    
    result = verifier.atomic_format_commit(
        commit_message_template="fix(format): Auto-fix {tool} violations",
        tool_name="black",
        verify_syntax=True
    )
    
    assert result.success is True
    assert "black" in result.message
    assert "test.py" in result.files_committed


@patch('subprocess.run')
def test_atomic_format_commit_syntax_failure(mock_run, verifier, temp_dir):
    """Test atomic format commit with syntax error."""
    # Create invalid Python file
    test_file = temp_dir / "invalid.py"
    test_file.write_text("def hello(\n    return 'world'")  # Syntax error
    
    # Mock git status to return this file
    mock_run.side_effect = [
        MagicMock(stdout="M  invalid.py\n", returncode=0),  # get_changed_files
        MagicMock(returncode=0),  # git restore --staged .
        MagicMock(returncode=0)   # git restore .
    ]
    
    with pytest.raises(SyntaxVerificationError):
        verifier.atomic_format_commit(
            commit_message_template="fix(format): Auto-fix {tool} violations",
            tool_name="black",
            verify_syntax=True
        )


@patch('subprocess.run')
def test_atomic_format_commit_no_changes(mock_run, verifier):
    """Test atomic format commit with no changes."""
    # Mock no staged changes
    mock_run.side_effect = [
        MagicMock(stdout="", returncode=0),  # get_changed_files (verify_syntax)
        MagicMock(returncode=0),  # git add .
        MagicMock(stdout="", returncode=0),  # get_changed_files (stage_changes)
    ]
    
    result = verifier.atomic_format_commit(
        commit_message_template="fix(format): Auto-fix {tool} violations",
        tool_name="black"
    )
    
    assert result.success is False
    assert "No files to commit" in result.message


@patch('subprocess.run')
def test_atomic_format_commit_skip_syntax_verification(mock_run, verifier, temp_dir):
    """Test atomic format commit skipping syntax verification."""
    # Create invalid Python file
    test_file = temp_dir / "invalid.py"
    test_file.write_text("def hello(\n    return 'world'")  # Syntax error
    
    # Mock git operations - should succeed when syntax verification is disabled
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git add .
        MagicMock(stdout="M  invalid.py\n", returncode=0),  # get_changed_files (stage_changes)
        MagicMock(stdout="invalid.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] fix(format): Auto-fix black violations (1 file)\n", returncode=0)  # git commit
    ]
    
    result = verifier.atomic_format_commit(
        commit_message_template="fix(format): Auto-fix {tool} violations",
        tool_name="black",
        verify_syntax=False
    )
    
    assert result.success is True


@patch('subprocess.run')
def test_get_git_status_summary(mock_run, verifier):
    """Test getting git status summary."""
    mock_run.return_value = MagicMock(
        stdout="M  modified.py\nA  added.py\nD  deleted.py\nR  renamed.py\n?? untracked.py\n",
        returncode=0
    )
    
    summary = verifier.get_git_status_summary()
    
    assert isinstance(summary, dict)
    assert summary['modified'] == 1
    assert summary['added'] == 1
    assert summary['deleted'] == 1
    assert summary['renamed'] == 1
    assert summary['untracked'] == 1


@patch('subprocess.run')
def test_commit_message_template_substitution(mock_run, verifier, temp_dir):
    """Test commit message template variable substitution."""
    # Create test file
    test_file = temp_dir / "test.py"
    test_file.write_text("print('hello')")
    
    # Mock git operations
    mock_run.side_effect = [
        MagicMock(stdout="M  test.py\n", returncode=0),  # get_changed_files (verify_syntax)
        MagicMock(returncode=0),  # git add .
        MagicMock(stdout="M  test.py\n", returncode=0),  # get_changed_files (stage_changes)
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        MagicMock(stdout="[main abc123] fix(format): Auto-fix ruff violations at 2023-12-01 12:00:00 (1 file)\n", returncode=0)  # git commit
    ]
    
    result = verifier.atomic_format_commit(
        commit_message_template="fix(format): Auto-fix {tool} violations at {timestamp}",
        tool_name="ruff"
    )
    
    assert result.success is True
    assert "ruff" in result.message
    assert "20" in result.message  # Should contain year from timestamp


@patch('subprocess.run')
def test_verify_non_python_files_ignored(mock_run, verifier):
    """Test that non-Python files are ignored during syntax verification."""
    # Mock git status to return non-Python files
    mock_run.return_value = MagicMock(
        stdout="M  test.js\nM  test.txt\n",
        returncode=0
    )
    
    # Should not raise any errors since non-Python files are ignored
    results = verifier.verify_changed_files_syntax()
    assert len(results) == 0


@patch('subprocess.run')
def test_custom_file_extensions(mock_run, verifier, temp_dir):
    """Test syntax verification with custom file extensions."""
    # Create .pyi file (Python interface file)
    pyi_file = temp_dir / "test.pyi"
    pyi_file.write_text("def hello() -> str: ...")
    
    # Mock git status to return this file
    mock_run.return_value = MagicMock(stdout="M  test.pyi\n", returncode=0)
    
    results = verifier.verify_changed_files_syntax(file_extensions={'.pyi'})
    assert len(results) == 1
    assert results[0].is_valid is True


@patch('subprocess.run')
def test_git_operation_error_handling(mock_run, verifier):
    """Test error handling for git operations."""
    # Mock git command failure
    mock_run.side_effect = subprocess.CalledProcessError(1, 'git', stderr="Git error")
    
    with pytest.raises(GitOperationError):
        verifier.get_changed_files()


@patch('subprocess.run')
def test_large_file_syntax_check(mock_run, verifier, temp_dir):
    """Test syntax checking with a large Python file."""
    # Create large valid Python file
    large_content = "# Large file\n" + "\n".join([f"var_{i} = {i}" for i in range(1000)])
    
    test_file = temp_dir / "large.py"
    test_file.write_text(large_content)
    
    result = verifier.check_python_syntax("large.py")
    assert result.is_valid is True


@patch('subprocess.run') 
def test_create_commit_failure(mock_run, verifier):
    """Test commit creation failure."""
    # Mock git operations that fail
    mock_run.side_effect = [
        MagicMock(stdout="test.py\n", returncode=0),  # git diff --cached --name-only
        subprocess.CalledProcessError(1, 'git commit', stderr="Commit failed")  # git commit fails
    ]
    
    result = verifier.create_commit("Test commit")
    
    assert result.success is False
    assert "Commit failed" in result.error_message


@patch('subprocess.run')
def test_get_git_status_summary_empty(mock_run, verifier):
    """Test git status summary with no changes."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    
    summary = verifier.get_git_status_summary()
    
    assert summary['modified'] == 0
    assert summary['added'] == 0
    assert summary['deleted'] == 0
    assert summary['renamed'] == 0
    assert summary['untracked'] == 0


@patch('subprocess.run')
def test_get_git_status_summary_failure(mock_run, verifier):
    """Test git status summary with git failure."""
    mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
    
    summary = verifier.get_git_status_summary()
    assert summary == {}