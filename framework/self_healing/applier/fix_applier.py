import os
import shutil


class RollbackException(Exception):
    """Raised when a fix application fails and rollback is required."""

class FixApplier:
    """
    Applies a fix and supports rollback if the fix fails.
    """

    def __init__(self, project_dir: str = "."):
        self.project_dir = project_dir
        self._backup_dir = os.path.join(project_dir, ".self_healing_backup")

    def apply(self, fix):
        """
        Apply the given fix. If application fails, raise RollbackException.
        """
        self._backup()
        try:
            # Simulate fix application
            if fix.get("type") == "dummy-fix":
                # Simulate a possible failure for testing rollback
                if fix.get("details") == "fail":
                    raise Exception("Simulated fix failure")
                # Otherwise, pretend to succeed
                return
            # Unknown fix type
            raise Exception("Unknown fix type")
        except Exception as e:
            raise RollbackException(str(e))

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
