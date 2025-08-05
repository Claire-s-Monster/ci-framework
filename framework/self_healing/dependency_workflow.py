"""
Dependency resolution workflow for self-healing CI framework.

This module orchestrates the complete dependency fix workflow including
pattern matching, fix application, verification, and git commit.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .command_executor import SafeCommandExecutor as CommandExecutor
from .dependency_engine import DependencyEngine, DependencyMatch
from .syntax_verifier import SyntaxVerifierAndCommitter

logger = logging.getLogger(__name__)


class DependencyFixWorkflow:
    """
    Orchestrates the complete dependency resolution workflow.
    
    This workflow handles:
    1. Pattern matching for dependency errors
    2. Applying appropriate fixes (pixi install, etc.)
    3. Verifying the fix resolved the issue
    4. Committing changes if needed
    """
    
    def __init__(self, working_directory: str = ".", config_path: Optional[str] = None):
        """
        Initialize the dependency fix workflow.
        
        Args:
            working_directory: Directory to run fixes in
            config_path: Optional path to configuration file
        """
        self.working_directory = Path(working_directory).resolve()
        self.config_path = config_path
        self.dependency_engine = DependencyEngine()
        self.command_executor = CommandExecutor()
        self.syntax_verifier = SyntaxVerifierAndCommitter()
        
    def analyze_output(self, output: str) -> Optional[Dict[str, Any]]:
        """
        Analyze output for dependency issues.
        
        Args:
            output: The error output to analyze
            
        Returns:
            Fix information if a pattern matches, None otherwise
        """
        return self.dependency_engine.suggest_fix(output)
    
    def execute_workflow(self, output: str, dry_run: bool = False) -> Tuple[bool, str]:
        """
        Execute the complete dependency fix workflow.
        
        Args:
            output: The error output to analyze
            dry_run: If True, only simulate the workflow
            
        Returns:
            Tuple of (success, message)
        """
        # Step 1: Analyze output for dependency issues
        fix_info = self.analyze_output(output)
        
        if not fix_info:
            return False, "No dependency issues detected"
        
        logger.info(f"Detected dependency issue: {fix_info['pattern_id']}")
        
        # Step 2: Apply the fix
        success, message = self.dependency_engine.apply_fix(fix_info, dry_run=dry_run)
        
        if not success:
            return False, message
            
        # Step 3: If fix was executed, verify it worked
        if fix_info.get('action') == 'execute' and not dry_run:
            # For pixi install commands, check if the command succeeded
            if 'pixi install' in fix_info.get('fix_command', ''):
                verify_result = self._verify_pixi_install()
                if not verify_result[0]:
                    return False, f"Fix verification failed: {verify_result[1]}"
            
            # Step 4: Commit changes if required
            if fix_info.get('requires_git_commit', False):
                commit_result = self._commit_changes(fix_info['commit_message'])
                if not commit_result[0]:
                    logger.warning(f"Failed to commit changes: {commit_result[1]}")
                else:
                    message += f"\n{commit_result[1]}"
        
        return True, message
    
    def _verify_pixi_install(self) -> Tuple[bool, str]:
        """
        Verify that pixi install completed successfully.
        
        Returns:
            Tuple of (success, message)
        """
        # Check if pixi.lock exists and is up to date
        lock_file = self.working_directory / "pixi.lock"
        pyproject_file = self.working_directory / "pyproject.toml"
        
        if not lock_file.exists():
            return False, "pixi.lock file not found after install"
            
        # Run pixi info to verify environment
        result = self.command_executor.execute("pixi info", working_directory=str(self.working_directory))
        
        if result.return_code != 0:
            return False, f"Failed to verify pixi environment: {result.stderr}"
            
        # Check if lock file is newer than pyproject.toml
        if pyproject_file.exists():
            if lock_file.stat().st_mtime < pyproject_file.stat().st_mtime:
                return False, "pixi.lock appears to still be outdated"
        
        return True, "Pixi environment verified successfully"
    
    def _commit_changes(self, commit_message: str) -> Tuple[bool, str]:
        """
        Commit changes to git.
        
        Args:
            commit_message: The commit message to use
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.working_directory),
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                return True, "No changes to commit"
            
            # Add pixi.lock if it was modified
            lock_file = self.working_directory / "pixi.lock"
            if lock_file.exists():
                add_result = subprocess.run(
                    ["git", "add", "pixi.lock"],
                    cwd=str(self.working_directory),
                    capture_output=True,
                    text=True
                )
                
                if add_result.returncode != 0:
                    return False, f"Failed to stage pixi.lock: {add_result.stderr}"
            
            # Commit changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=str(self.working_directory),
                capture_output=True,
                text=True
            )
            
            if commit_result.returncode != 0:
                return False, f"Failed to commit: {commit_result.stderr}"
                
            return True, f"Changes committed: {commit_message}"
            
        except Exception as e:
            return False, f"Error during git commit: {str(e)}"
    
    def test_pattern_matching(self, output: str) -> Optional[DependencyMatch]:
        """
        Test pattern matching without applying fixes.
        
        Args:
            output: The output to test against patterns
            
        Returns:
            DependencyMatch if a pattern matches, None otherwise
        """
        return self.dependency_engine.test_pattern_matching(output)
    
    def get_suggestion_for_module(self, module_name: str) -> str:
        """
        Get a suggestion for installing a missing module.
        
        Args:
            module_name: The name of the missing module
            
        Returns:
            Suggestion message
        """
        # Map common Python modules to their conda-forge equivalents
        module_mappings = {
            'cv2': 'opencv',
            'PIL': 'pillow',
            'sklearn': 'scikit-learn',
            'skimage': 'scikit-image',
            'yaml': 'pyyaml',
            'lxml': 'lxml',
            'bs4': 'beautifulsoup4',
        }
        
        conda_name = module_mappings.get(module_name, module_name)
        
        return (
            f"Module '{module_name}' not found. Consider running:\n"
            f"  pixi add {conda_name}\n"
            f"Then verify it's available with:\n"
            f"  pixi run python -c 'import {module_name}'"
        )