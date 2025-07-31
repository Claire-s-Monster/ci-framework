import os
import sys
from pathlib import Path

# Add the framework root to Python path for imports
# Note: E402 suppressed as sys.path modification is required before imports
framework_root = Path(__file__).parent.parent.parent
if str(framework_root) not in sys.path:
    sys.path.insert(0, str(framework_root))

from framework.self_healing.engine import main as engine_main  # noqa: E402
from framework.self_healing.pattern_engine import FailurePatternEngine  # noqa: E402


def test_action_integration(tmp_path, monkeypatch):
    """Test engine integration by directly calling main function"""
    status_file = tmp_path / ".self_healing_status"

    # Mock sys.argv to simulate command line arguments
    mock_argv = [
        "engine",
        "--project-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", mock_argv)

    # Call engine main function directly
    engine_main()

    # Verify status file was created
    assert status_file.exists()
    with open(status_file) as f:
        status = dict(line.strip().split("=", 1) for line in f if "=" in line)
    assert status["healed"] == "true"
    assert status["rollback"] == "false"
    assert status["error"] == ""


def test_action_integration_rollback(tmp_path, monkeypatch):
    """Test rollback behavior when fix fails"""
    status_file = tmp_path / ".self_healing_status"

    # Mock the analyze method to simulate failure
    orig_analyze = FailurePatternEngine.analyze

    def fail_analyze(self):
        return {"type": "dummy-fix", "details": "fail"}

    FailurePatternEngine.analyze = fail_analyze

    try:
        # Mock sys.argv to simulate command line arguments
        mock_argv = [
            "engine",
            "--project-dir",
            str(tmp_path),
        ]
        monkeypatch.setattr(sys, "argv", mock_argv)

        # Call engine main function directly
        engine_main()

        # Verify status file and rollback behavior
        assert status_file.exists()
        with open(status_file) as f:
            status = dict(line.strip().split("=", 1) for line in f if "=" in line)
        assert status["healed"] == "false"
        assert status["rollback"] == "true"
        assert "Rollback triggered" in status["error"]

    finally:
        # Restore original method
        FailurePatternEngine.analyze = orig_analyze
