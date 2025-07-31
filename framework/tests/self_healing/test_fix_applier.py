import os

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
