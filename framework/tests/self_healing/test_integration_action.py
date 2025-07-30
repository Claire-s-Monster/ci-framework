import os
import subprocess
import sys
import tempfile


def test_action_integration(tmp_path):
    # Simulate running the engine as the action would
    status_file = tmp_path / ".self_healing_status"
    cmd = [
        sys.executable,
        "-m",
        "framework.self_healing.engine",
        "--project-dir",
        str(tmp_path),
    ]
    subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert status_file.exists()
    with open(status_file) as f:
        status = dict(line.strip().split("=", 1) for line in f if "=" in line)
    assert status["healed"] == "true"
    assert status["rollback"] == "false"
    assert status["error"] == ""

def test_action_integration_rollback(tmp_path):
    # Simulate a fix that will fail and trigger rollback
    from framework.self_healing.engine import FailurePatternEngine
    orig_analyze = FailurePatternEngine.analyze
    def fail_analyze(self):
        return {"type": "dummy-fix", "details": "fail"}
    FailurePatternEngine.analyze = fail_analyze

    status_file = tmp_path / ".self_healing_status"
    cmd = [
        sys.executable,
        "-m",
        "framework.self_healing.engine",
        "--project-dir",
        str(tmp_path),
    ]
    subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert status_file.exists()
    with open(status_file) as f:
        status = dict(line.strip().split("=", 1) for line in f if "=" in line)
    assert status["healed"] == "false"
    assert status["rollback"] == "true"
    assert "Rollback triggered" in status["error"]

    # Restore original method
    FailurePatternEngine.analyze = orig_analyze
