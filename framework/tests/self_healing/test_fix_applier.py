import os
from unittest.mock import MagicMock, patch

import pytest

from framework.self_healing.applier import FixApplier, RollbackException


def test_apply_success(tmp_path):
    applier = FixApplier(project_dir=tmp_path)
    fix = {"type": "dummy-fix", "details": "success"}
    applier.apply(fix)
    # Backup should exist
    assert (tmp_path / ".self_healing_backup" / "backup.txt").exists()


def test_apply_failure_triggers_rollback(tmp_path):
    applier = FixApplier(project_dir=tmp_path)
    fix = {"type": "dummy-fix", "details": "fail"}
    with pytest.raises(RollbackException):
        applier.apply(fix)
    # Backup should still exist (rollback not called yet)
    assert (tmp_path / ".self_healing_backup" / "backup.txt").exists()
    applier.rollback()
    # Backup should be removed
    assert not (tmp_path / ".self_healing_backup").exists()


def test_unknown_fix_type(tmp_path):
    applier = FixApplier(project_dir=tmp_path)
    fix = {"type": "unknown-fix"}
    with pytest.raises(RollbackException):
        applier.apply(fix)


def test_apply_dependency_fix_success(tmp_path):
    """Test successful application of dependency fix."""
    applier = FixApplier(project_dir=tmp_path)

    # Mock workflow
    mock_workflow = MagicMock()
    mock_workflow.execute_workflow.return_value = (True, "Fix applied successfully")

    fix = {
        "type": "dependency-fix",
        "pattern_id": "pixi_lock_outdated",
        "workflow": mock_workflow,
    }

    result = applier.apply(fix)

    assert result["success"] is True
    assert "Fix applied successfully" in result["message"]
    mock_workflow.execute_workflow.assert_called_once()


def test_apply_dependency_fix_failure(tmp_path):
    """Test failed application of dependency fix."""
    applier = FixApplier(project_dir=tmp_path)

    # Mock workflow that fails
    mock_workflow = MagicMock()
    mock_workflow.execute_workflow.return_value = (False, "Failed to apply fix")

    fix = {
        "type": "dependency-fix",
        "pattern_id": "pixi_conflict_detected",
        "workflow": mock_workflow,
    }

    with pytest.raises(RollbackException, match="Dependency fix failed"):
        applier.apply(fix)


def test_apply_dependency_fix_no_workflow(tmp_path):
    """Test dependency fix without workflow raises exception."""
    applier = FixApplier(project_dir=tmp_path)

    fix = {"type": "dependency-fix", "pattern_id": "pixi_lock_outdated"}

    with pytest.raises(RollbackException, match="No workflow found"):
        applier.apply(fix)
