import os
import shutil
from typing import Any


class RollbackException(Exception):
    """Raised when a fix application fails and rollback is required."""


class FixApplier:
    """
    Applies a fix and supports rollback if the fix fails.
    
    Now supports both legacy dummy fixes and new formatting workflow fixes.
    """

    def __init__(self, project_dir: str = "."):
        self.project_dir = project_dir
        self._backup_dir = os.path.join(project_dir, ".self_healing_backup")

    def apply(self, fix: Any) -> Any:
        """
        Apply the given fix. If application fails, raise RollbackException.
        
        Args:
            fix: Fix object from pattern engine
            
        Returns:
            Result of fix application
        """
        self._backup()
        try:
            fix_type = fix.get("type")
            
            if fix_type == "formatting-fix":
                return self._apply_formatting_fix(fix)
            elif fix_type == "dependency-fix":
                return self._apply_dependency_fix(fix)
            elif fix_type == "dummy-fix":
                return self._apply_dummy_fix(fix)
            else:
                raise Exception(f"Unknown fix type: {fix_type}")
                
        except Exception as e:
            raise RollbackException(str(e)) from e

    def _apply_formatting_fix(self, fix: Any) -> Any:
        """Apply a formatting fix using the workflow."""
        workflow = fix.get("workflow")
        if not workflow:
            raise Exception("No workflow found in formatting fix")
        
        # Get some sample output that would trigger this fix
        # In real usage, this would be the actual CI failure output
        tool = fix.get("tool")
        
        # Create a mock tool output that would match this pattern
        if tool == "ruff":
            sample_output = "Found 5 errors (3 fixable with the `--fix` option)."
        elif tool == "black":
            sample_output = "would reformat 2 files"
        elif tool == "isort":
            sample_output = "Fixing 1 files"
        else:
            sample_output = f"Mock output for {tool}"
        
        # Process through the workflow
        result = workflow.process_tool_output(
            tool_output=sample_output,
            dry_run=False,
            verify_syntax=True,
            create_commit=True
        )
        
        if not result.success:
            raise Exception(f"Formatting fix failed: {result.message}")
        
        return result

    def _apply_dependency_fix(self, fix: Any) -> Any:
        """Apply a dependency fix using the workflow."""
        workflow = fix.get("workflow")
        if not workflow:
            raise Exception("No workflow found in dependency fix")
        
        # Get the pattern details
        pattern_id = fix.get("pattern_id")
        
        # Create sample output based on the pattern
        sample_outputs = {
            "pixi_lock_outdated": "The lock file is not up-to-date with pyproject.toml",
            "pixi_lock_missing": "pixi.lock not found",
            "module_not_found_error": "ModuleNotFoundError: No module named 'requests'",
            "pixi_conflict_detected": "Conflict detected in dependencies"
        }
        
        sample_output = sample_outputs.get(pattern_id, f"Dependency issue: {pattern_id}")
        
        # Process through the workflow
        success, message = workflow.execute_workflow(
            output=sample_output,
            dry_run=False
        )
        
        if not success:
            raise Exception(f"Dependency fix failed: {message}")
        
        return {"success": success, "message": message}

    def _apply_dummy_fix(self, fix: Any) -> None:
        """Apply legacy dummy fix for backward compatibility."""
        # Simulate a possible failure for testing rollback
        if fix.get("details") == "fail":
            raise Exception("Simulated fix failure")
        # Otherwise, pretend to succeed
        return

    def _backup(self):
        """
        Backup project files before applying fix.
        """
        # For demonstration, just create a backup marker
        os.makedirs(self._backup_dir, exist_ok=True)
        with open(os.path.join(self._backup_dir, "backup.txt"), "w") as f:
            f.write("backup")

    def rollback(self):
        """
        Restore from backup.
        """
        # For demonstration, just remove the backup marker
        if os.path.exists(self._backup_dir):
            shutil.rmtree(self._backup_dir)
