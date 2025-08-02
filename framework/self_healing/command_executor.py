"""
Safe command execution module for formatting tools.

This module provides a robust wrapper around subprocess execution with 
timeout handling, output capture, and security considerations.
"""

import os
import subprocess
import shlex
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of command execution."""
    command: str
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    timed_out: bool
    working_directory: str


class CommandExecutionError(Exception):
    """Raised when command execution fails in an unexpected way."""
    
    def __init__(self, message: str, result: Optional[CommandResult] = None):
        super().__init__(message)
        self.result = result


class CommandTimeoutError(CommandExecutionError):
    """Raised when command execution times out."""
    pass


class SafeCommandExecutor:
    """
    Safe command executor for formatting tools with timeout and security controls.
    """
    
    # Allowed formatting commands (security whitelist) 
    ALLOWED_COMMANDS = {
        'ruff', 'black', 'isort', 'autopep8', 'yapf', 'pyupgrade',
        'autoflake', 'docformatter', 'prettier', 'eslint', 'rustfmt',
        'pixi'  # Added for dependency resolution
    }
    
    # Dangerous command patterns to reject
    DANGEROUS_PATTERNS = [
        'rm ', 'sudo ', 'chmod +x', '&&', '||', ';', '|', '>', '>>', 
        '<', 'curl', 'wget', 'ssh', 'scp', 'rsync', '$(', '`'
    ]
    
    def __init__(
        self, 
        default_timeout: int = 300,  # 5 minutes default
        max_output_size: int = 10 * 1024 * 1024,  # 10MB max output
        working_directory: Optional[str] = None
    ):
        """
        Initialize the safe command executor.
        
        Args:
            default_timeout: Default timeout in seconds
            max_output_size: Maximum output size in bytes
            working_directory: Default working directory for commands
        """
        self.default_timeout = default_timeout
        self.max_output_size = max_output_size
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        
    def execute(
        self, 
        command: str, 
        timeout: Optional[int] = None,
        working_directory: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        check_allowed: bool = True
    ) -> CommandResult:
        """
        Execute a command safely with timeout and output capture.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds (uses default if None)
            working_directory: Working directory for command execution
            env: Environment variables to set
            check_allowed: Whether to check command against allowlist
            
        Returns:
            CommandResult with execution details
            
        Raises:
            CommandExecutionError: If command execution fails
            CommandTimeoutError: If command times out
            ValueError: If command is not allowed
        """
        if check_allowed:
            self._validate_command_safety(command)
        
        # Set up execution parameters
        timeout = timeout or self.default_timeout
        work_dir = Path(working_directory or self.working_directory).resolve()
        start_time = time.time()
        
        # Prepare command and environment
        cmd_args = shlex.split(command)
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)
        
        try:
            # Execute command with timeout
            process = subprocess.Popen(
                cmd_args,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=exec_env,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                # Kill the process group to ensure cleanup
                self._kill_process_group(process)
                stdout, stderr = process.communicate()
                timed_out = True
            
            execution_time = time.time() - start_time
            
            # Check output size limits
            if len(stdout) > self.max_output_size:
                stdout = stdout[:self.max_output_size] + "\n[OUTPUT TRUNCATED - SIZE LIMIT EXCEEDED]"
            if len(stderr) > self.max_output_size:
                stderr = stderr[:self.max_output_size] + "\n[ERROR OUTPUT TRUNCATED - SIZE LIMIT EXCEEDED]"
            
            result = CommandResult(
                command=command,
                return_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                timed_out=timed_out,
                working_directory=str(work_dir)
            )
            
            if timed_out:
                raise CommandTimeoutError(
                    f"Command timed out after {timeout} seconds: {command}",
                    result=result
                )
            
            return result
            
        except CommandTimeoutError:
            # Re-raise timeout errors as-is
            raise
        except FileNotFoundError as e:
            raise CommandExecutionError(f"Command not found: {command}") from e
        except PermissionError as e:
            raise CommandExecutionError(f"Permission denied executing command: {command}") from e
        except Exception as e:
            raise CommandExecutionError(f"Unexpected error executing command: {e}") from e
    
    def _validate_command_safety(self, command: str) -> None:
        """
        Validate that the command is safe to execute.
        
        Args:
            command: Command to validate
            
        Raises:
            ValueError: If command is not allowed
        """
        # Check for dangerous patterns
        command_lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command_lower:
                raise ValueError(f"Dangerous command pattern detected: {pattern}")
        
        # Extract the base command
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            raise ValueError("Empty command")
        
        base_command = Path(cmd_parts[0]).name
        
        # Check against allowlist
        if base_command not in self.ALLOWED_COMMANDS:
            raise ValueError(f"Command not in allowlist: {base_command}")
    
    def _kill_process_group(self, process: subprocess.Popen) -> None:
        """
        Kill a process and its children safely.
        
        Args:
            process: Process to kill
        """
        try:
            if os.name != 'nt':
                # Unix-like systems - kill process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(1)
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process already dead
            else:
                # Windows - kill process tree
                process.terminate()
                time.sleep(1)
                process.kill()
        except (ProcessLookupError, PermissionError):
            # Process already dead or we don't have permission
            pass
    
    def execute_formatting_command(
        self, 
        tool: str, 
        fix_command: str, 
        timeout: Optional[int] = None,
        working_directory: Optional[str] = None
    ) -> CommandResult:
        """
        Execute a formatting command with tool-specific optimizations.
        
        Args:
            tool: Name of the formatting tool (ruff, black, etc.)
            fix_command: Command to execute
            timeout: Timeout in seconds
            working_directory: Working directory for execution
            
        Returns:
            CommandResult with execution details
        """
        # Tool-specific environment variables or optimizations
        env_vars = {}
        
        if tool == 'black':
            # Ensure black uses consistent line endings
            env_vars['BLACK_EXPERIMENTAL_STRING_PROCESSING'] = '1'
        elif tool == 'ruff':
            # Enable ruff performance optimizations
            env_vars['RUFF_CACHE_DIR'] = str(Path.home() / '.cache' / 'ruff')
        elif tool == 'isort':
            # Disable isort's interactive prompts
            env_vars['ISORT_QUIET'] = '1'
        
        return self.execute(
            command=fix_command,
            timeout=timeout,
            working_directory=working_directory,
            env=env_vars,
            check_allowed=True
        )
    
    def dry_run_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_directory: Optional[str] = None
    ) -> CommandResult:
        """
        Execute a command in dry-run mode if supported by the tool.
        
        Args:
            command: Command to execute in dry-run mode
            timeout: Timeout in seconds
            working_directory: Working directory for execution
            
        Returns:
            CommandResult with dry-run execution details
        """
        # Add dry-run flags based on tool
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            raise ValueError("Empty command")
        
        base_command = Path(cmd_parts[0]).name
        
        # Tool-specific dry-run modifications
        if base_command == 'black':
            # Black: --check --diff shows what would be changed
            if '--check' not in cmd_parts:
                cmd_parts.append('--check')
            if '--diff' not in cmd_parts:
                cmd_parts.append('--diff')
        elif base_command == 'ruff':
            # Ruff: remove --fix to see what would be fixed
            cmd_parts = [part for part in cmd_parts if part != '--fix']
        elif base_command == 'isort':
            # isort: --check-only --diff shows what would be changed
            if '--check-only' not in cmd_parts:
                cmd_parts.append('--check-only')  
            if '--diff' not in cmd_parts:
                cmd_parts.append('--diff')
        
        dry_run_command = ' '.join(shlex.quote(part) for part in cmd_parts)
        
        return self.execute(
            command=dry_run_command,
            timeout=timeout,
            working_directory=working_directory,
            check_allowed=True
        )
    
    def get_command_info(self, tool: str) -> Dict[str, Any]:
        """
        Get information about a formatting tool.
        
        Args:
            tool: Tool name
            
        Returns:
            Dictionary with tool information
        """
        info_commands = {
            'black': 'black --version',
            'ruff': 'ruff --version', 
            'isort': 'isort --version',
            'autopep8': 'autopep8 --version',
            'yapf': 'yapf --version'
        }
        
        if tool not in info_commands:
            return {'available': False, 'error': f'Unknown tool: {tool}'}
        
        try:
            result = self.execute(info_commands[tool], timeout=10, check_allowed=True)
            return {
                'available': result.return_code == 0,
                'version': result.stdout.strip() if result.return_code == 0 else None,
                'error': result.stderr.strip() if result.return_code != 0 else None
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}