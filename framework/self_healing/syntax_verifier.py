"""
Syntax verification and atomic git commit module for formatting fixes.

This module verifies that automated fixes haven't introduced syntax errors
and commits changes atomically with descriptive messages.
"""

import ast
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SyntaxCheckResult:
    """Result of syntax checking operation."""
    file_path: str
    is_valid: bool
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None


@dataclass
class GitCommitResult:
    """Result of git commit operation."""
    success: bool
    commit_hash: Optional[str] = None
    message: str = ""
    files_committed: List[str] = None  # type: ignore
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.files_committed is None:
            self.files_committed = []


class SyntaxVerificationError(Exception):
    """Raised when syntax verification fails."""
    
    def __init__(self, message: str, failed_files: List[SyntaxCheckResult]):
        super().__init__(message)
        self.failed_files = failed_files


class GitOperationError(Exception):
    """Raised when git operations fail."""
    pass


class SyntaxVerifierAndCommitter:
    """
    Handles syntax verification and atomic git commits for formatting fixes.
    """
    
    # File extensions that support AST parsing
    PYTHON_EXTENSIONS = {'.py', '.pyx', '.pyi'}
    
    def __init__(self, working_directory: Optional[str] = None):
        """
        Initialize the syntax verifier and committer.
        
        Args:
            working_directory: Working directory for operations
        """
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        
    def get_changed_files(self) -> List[str]:
        """
        Get list of files that have been modified according to git.
        
        Returns:
            List of modified file paths
            
        Raises:
            GitOperationError: If git status command fails
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            
            changed_files = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                # Parse git status output format: XY filename
                status = line[:2]
                filename = line[3:]
                
                # Include modified, added, and renamed files
                if status[0] in 'MAR' or status[1] in 'MAR':
                    changed_files.append(filename)
            
            return changed_files
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get git status: {e.stderr}")
    
    def check_python_syntax(self, file_path: str) -> SyntaxCheckResult:
        """
        Check Python file syntax using AST parsing.
        
        Args:
            file_path: Path to Python file to check
            
        Returns:
            SyntaxCheckResult with validation details
        """
        abs_path = self.working_directory / file_path
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Parse with AST to check syntax
            ast.parse(source_code, filename=str(abs_path))
            
            return SyntaxCheckResult(
                file_path=file_path,
                is_valid=True
            )
            
        except SyntaxError as e:
            return SyntaxCheckResult(
                file_path=file_path,
                is_valid=False,
                error_message=str(e),
                line_number=e.lineno,
                column_number=e.offset
            )
        except FileNotFoundError:
            return SyntaxCheckResult(
                file_path=file_path,
                is_valid=False,
                error_message=f"File not found: {abs_path}"
            )
        except Exception as e:
            return SyntaxCheckResult(
                file_path=file_path,
                is_valid=False,
                error_message=f"Unexpected error checking syntax: {e}"
            )
    
    def verify_changed_files_syntax(self, file_extensions: Optional[Set[str]] = None) -> List[SyntaxCheckResult]:
        """
        Verify syntax of all changed Python files.
        
        Args:
            file_extensions: Set of file extensions to check (defaults to Python extensions)
            
        Returns:
            List of SyntaxCheckResult for all checked files
            
        Raises:
            SyntaxVerificationError: If any files have syntax errors
        """
        if file_extensions is None:
            file_extensions = self.PYTHON_EXTENSIONS
        
        changed_files = self.get_changed_files()
        results = []
        failed_files = []
        
        for file_path in changed_files:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in file_extensions:
                result = self.check_python_syntax(file_path)
                results.append(result)
                
                if not result.is_valid:
                    failed_files.append(result)
        
        if failed_files:
            raise SyntaxVerificationError(
                f"Syntax errors found in {len(failed_files)} files",
                failed_files
            )
        
        return results
    
    def restore_changes(self) -> None:
        """
        Restore all changes using git restore.
        
        Raises:
            GitOperationError: If git restore fails
        """
        try:
            # Restore staged and unstaged changes
            subprocess.run(
                ['git', 'restore', '--staged', '.'],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            
            subprocess.run(
                ['git', 'restore', '.'],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to restore changes: {e.stderr}")
    
    def stage_changes(self, files: Optional[List[str]] = None) -> List[str]:
        """
        Stage changes for commit.
        
        Args:
            files: Specific files to stage (stages all changes if None)
            
        Returns:
            List of staged files
            
        Raises:
            GitOperationError: If git add fails
        """
        try:
            if files:
                # Stage specific files
                for file_path in files:
                    subprocess.run(
                        ['git', 'add', file_path],
                        cwd=self.working_directory,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                staged_files = files
            else:
                # Stage all changes
                subprocess.run(
                    ['git', 'add', '.'],
                    cwd=self.working_directory,
                    capture_output=True,
                    text=True,
                    check=True
                )
                staged_files = self.get_changed_files()
            
            return staged_files
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to stage changes: {e.stderr}")
    
    def create_commit(
        self, 
        message: str, 
        author: Optional[str] = None,
        include_file_count: bool = True
    ) -> GitCommitResult:
        """
        Create a git commit with the specified message.
        
        Args:
            message: Commit message
            author: Commit author (uses git config if None)
            include_file_count: Whether to include file count in message
            
        Returns:
            GitCommitResult with commit details
        """
        try:
            # Get staged files for commit
            staged_files = []
            try:
                result = subprocess.run(
                    ['git', 'diff', '--cached', '--name-only'],
                    cwd=self.working_directory,
                    capture_output=True,
                    text=True,
                    check=True
                )
                staged_files = [f for f in result.stdout.strip().split('\n') if f]
            except subprocess.CalledProcessError:
                pass  # Continue with commit attempt
            
            # Enhance message with file count if requested
            if include_file_count and staged_files:
                file_count = len(staged_files)
                if file_count == 1:
                    message += " (1 file)"
                else:
                    message += f" ({file_count} files)"
            
            # Prepare commit command
            commit_cmd = ['git', 'commit', '-m', message]
            if author:
                commit_cmd.extend(['--author', author])
            
            # Create commit
            result = subprocess.run(
                commit_cmd,
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract commit hash from output
            commit_hash = None
            for line in result.stdout.split('\n'):
                if line.startswith('[') and ']' in line:
                    # Format: [branch commit_hash] message
                    parts = line.split()
                    if len(parts) >= 2:
                        commit_hash = parts[1].rstrip(']')
                    break
            
            return GitCommitResult(
                success=True,
                commit_hash=commit_hash,
                message=message,
                files_committed=staged_files
            )
            
        except subprocess.CalledProcessError as e:
            return GitCommitResult(
                success=False,
                message=message,
                error_message=f"Commit failed: {e.stderr}"
            )
    
    def atomic_format_commit(
        self,
        commit_message_template: str,
        tool_name: str,
        author: Optional[str] = None,
        include_file_count: bool = True,
        verify_syntax: bool = True
    ) -> GitCommitResult:
        """
        Perform atomic commit with syntax verification and rollback on failure.
        
        Args:
            commit_message_template: Template for commit message
            tool_name: Name of the formatting tool used
            author: Commit author
            include_file_count: Whether to include file count in message
            verify_syntax: Whether to verify syntax before committing
            
        Returns:
            GitCommitResult with operation details
            
        Raises:
            SyntaxVerificationError: If syntax verification fails
            GitOperationError: If git operations fail
        """
        try:
            # Verify syntax if requested
            if verify_syntax:
                self.verify_changed_files_syntax()
            
            # Stage all changes
            staged_files = self.stage_changes()
            
            if not staged_files:
                return GitCommitResult(
                    success=False,
                    message="No files to commit",
                    error_message="No changes detected"
                )
            
            # Generate commit message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = commit_message_template
            
            # Replace template variables
            commit_message = commit_message.replace("{tool}", tool_name)
            commit_message = commit_message.replace("{timestamp}", timestamp)
            
            # Create commit
            result = self.create_commit(
                message=commit_message,
                author=author,
                include_file_count=include_file_count
            )
            
            if not result.success:
                # Rollback staged changes on commit failure
                self.restore_changes()
                raise GitOperationError(f"Commit failed: {result.error_message}")
            
            return result
            
        except SyntaxVerificationError:
            # Rollback all changes on syntax error
            self.restore_changes()
            raise
        except Exception as e:
            # Rollback on any unexpected error
            self.restore_changes()
            raise GitOperationError(f"Atomic commit failed: {e}")
    
    def get_git_status_summary(self) -> Dict[str, int]:
        """
        Get summary of git repository status.
        
        Returns:
            Dictionary with counts of different file statuses
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            
            status_counts = {
                'modified': 0,
                'added': 0, 
                'deleted': 0,
                'renamed': 0,
                'untracked': 0
            }
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                status = line[:2]
                
                if status[0] == 'M' or status[1] == 'M':
                    status_counts['modified'] += 1
                elif status[0] == 'A' or status[1] == 'A':
                    status_counts['added'] += 1
                elif status[0] == 'D' or status[1] == 'D':
                    status_counts['deleted'] += 1
                elif status[0] == 'R' or status[1] == 'R':
                    status_counts['renamed'] += 1
                elif status == '??':
                    status_counts['untracked'] += 1
            
            return status_counts
            
        except subprocess.CalledProcessError:
            return {}
    
    def is_git_repository(self) -> bool:
        """
        Check if the working directory is a git repository.
        
        Returns:
            True if directory is a git repository
        """
        try:
            subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.working_directory,
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False