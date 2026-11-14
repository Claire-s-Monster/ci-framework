"""Behavioural tests for QualityGatesAction.

A fake ``pixi`` executable placed first on PATH stands in for the real tool,
so the real command building, threading, timeout and result aggregation run
unmodified. Per-check behaviour is scripted through ``<QG_DIR>/<check>.sh``.
"""

import stat
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from framework.actions.quality_gates import QualityGatesAction

PIXI_PROJECT = '[tool.pixi.workspace]\nplatforms = ["linux-64"]\n'


@pytest.fixture
def action():
    act = QualityGatesAction()
    yield act
    act.cleanup()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A pixi project plus a fake pixi on PATH; returns (project_dir, script)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    qg_dir = tmp_path / "qg"
    qg_dir.mkdir()
    pixi = bin_dir / "pixi"
    pixi.write_text('#!/bin/sh\nf="$QG_DIR/$2.sh"\n[ -f "$f" ] && . "$f"\nexit 0\n')
    pixi.chmod(pixi.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("QG_DIR", str(qg_dir))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(PIXI_PROJECT)

    def script(check: str, body: str) -> None:
        (qg_dir / f"{check}.sh").write_text(body + "\n")

    return proj, script


class TestDetectPackageManager:
    @pytest.mark.parametrize(
        ("content", "name", "quality"),
        [
            ("[tool.pixi.workspace]\n", "pixi", "pixi run -e quality"),
            ("[tool.poetry]\nname='x'\n", "poetry", None),
            ("[tool.hatch.envs.default]\n", "hatch", "hatch run quality:test"),
            ("[tool.black]\n", "pip", None),
        ],
    )
    def test_by_pyproject_content(self, action, tmp_path, content, name, quality):
        (tmp_path / "pyproject.toml").write_text(content)
        manager = action.detect_package_manager(tmp_path)
        assert manager.name == name
        if quality:
            assert manager.quality_command == quality
        assert manager.environment_support is (name != "pip")

    def test_no_pyproject_falls_back_to_pip(self, action, tmp_path):
        manager = action.detect_package_manager(str(tmp_path))
        assert manager.name == "pip"
        assert manager.detected_files == []

    def test_unreadable_pyproject_falls_back_to_pip(self, action, tmp_path):
        (tmp_path / "pyproject.toml").mkdir()  # exists() is True, read fails
        assert action.detect_package_manager(tmp_path).name == "pip"


class TestProjectPatterns:
    def test_invalid_toml_yields_empty_config(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text("not = [valid")
        assert action._load_project_config(tmp_path) == {}

    def test_missing_pyproject_yields_empty_config(self, action, tmp_path):
        assert action._load_project_config(tmp_path) == {}

    def test_pixi_platforms_and_mypy(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pixi.workspace]\nplatforms = ["linux-64", "osx-arm64"]\n'
            "[tool.mypy]\nstrict = true\n"
        )
        patterns = action._detect_project_patterns(tmp_path)
        assert patterns == {
            "package_manager": "pixi",
            "platforms": ["linux-64", "osx-arm64"],
            "type_checker": "mypy",
        }

    def test_legacy_pixi_project_section_platforms(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pixi.project]\nplatforms = ["win-64"]\n'
        )
        assert action._detect_project_patterns(tmp_path)["platforms"] == ["win-64"]

    def test_pyright_tool_section(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.pyright]\nx = 1\n")
        assert action._detect_project_patterns(tmp_path)["type_checker"] == "pyright"

    def test_pyright_feature_dependency_beats_mypy(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pixi.feature.a.dependencies]\nmypy = '*'\n"
            "[tool.pixi.feature.b.dependencies]\npyright = '*'\n"
        )
        assert action._detect_project_patterns(tmp_path)["type_checker"] == "pyright"

    def test_mypy_feature_dependency_when_no_other_checker(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pixi.feature.a.dependencies]\nmypy = '*'\n"
        )
        assert action._detect_project_patterns(tmp_path)["type_checker"] == "mypy"

    def test_feature_mypy_does_not_override_existing_checker(self, action, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pyright]\nx = 1\n[tool.pixi.feature.a.dependencies]\nmypy = '*'\n"
        )
        assert action._detect_project_patterns(tmp_path)["type_checker"] == "pyright"


class TestTierCommands:
    @pytest.mark.parametrize(
        ("tier", "checks"),
        [
            ("essential", ["test", "lint", "typecheck"]),
            ("extended", ["test", "lint", "typecheck", "security-scan"]),
            ("full", ["test", "lint", "typecheck", "security-scan", "check-all"]),
            ("bogus", ["test", "lint", "typecheck"]),
        ],
    )
    @pytest.mark.parametrize(
        ("manager", "prefix"),
        [
            ("pixi", "pixi run"),
            ("poetry", "poetry run"),
            ("hatch", "hatch run"),
            ("pip", "python -m"),
        ],
    )
    def test_commands_per_tier_and_manager(
        self, action, tmp_path, tier, checks, manager, prefix
    ):
        from framework.actions.quality_gates import PackageManager

        cmds = action._get_tier_commands(tier, PackageManager(name=manager))
        assert cmds == [f"{prefix} {c}" for c in checks]


class TestExecuteCommandReal:
    def test_success_and_failure_exit_codes(self, action, tmp_path):
        ok = action._execute_command("true", tmp_path, 10)
        bad = action._execute_command("false", tmp_path, 10)
        assert ok["success"] is True and ok["returncode"] == 0
        assert bad["success"] is False and bad["returncode"] == 1

    def test_captures_output_and_runs_in_project_dir(self, action, tmp_path):
        result = action._execute_command("pwd", tmp_path, 20)
        assert result["stdout"].strip() == str(tmp_path.resolve())

    def test_timeout_kills_process_and_reports(self, action, tmp_path):
        started = time.time()
        result = action._execute_command("sleep 30", tmp_path, 1)
        assert result["success"] is False
        assert result["timeout"] is True
        assert result["returncode"] == -1
        assert "timed out after 1 seconds" in result["stderr"]
        assert time.time() - started < 20
        assert action._running_processes == []

    def test_timeout_tolerates_processes_that_cannot_be_signalled(
        self, action, tmp_path, monkeypatch
    ):
        import framework.actions.quality_gates as qg

        def deny(*_a, **_k):
            raise ProcessLookupError

        monkeypatch.setattr(qg.os, "killpg", deny)
        result = action._execute_command("sleep 3", tmp_path, 1)
        assert result["timeout"] is True

    def test_missing_binary_reported_as_error(self, action, tmp_path):
        result = action._execute_command("no-such-binary-xyz --flag", tmp_path, 5)
        assert result["success"] is False
        assert result["returncode"] == -1
        assert "no-such-binary-xyz" in result["error"]


class TestExecuteCommandMockedRun:
    """When subprocess.run is a mock, _execute_command delegates to it."""

    def test_uses_mock_result(self, action, tmp_path, monkeypatch):
        run = MagicMock(return_value=MagicMock(returncode=2, stdout="o", stderr="e"))
        monkeypatch.setattr(subprocess, "run", run)
        result = action._execute_command("anything", tmp_path, 7)
        assert result == {
            "success": False,
            "stdout": "o",
            "stderr": "e",
            "returncode": 2,
        }
        assert run.call_args.kwargs["timeout"] == 7

    def test_mock_call_is_argv_list_without_shell(self, action, tmp_path, monkeypatch):
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        monkeypatch.setattr(subprocess, "run", run)
        action._execute_command("python -m ruff check; echo hi", tmp_path, 1)
        args, kwargs = run.call_args
        assert args[0] == ["python", "-m", "ruff", "check;", "echo", "hi"]
        assert kwargs.get("shell") is not True

    def test_mock_success(self, action, tmp_path, monkeypatch):
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        monkeypatch.setattr(subprocess, "run", run)
        assert action._execute_command("x", tmp_path, 1)["success"] is True

    def test_mock_timeout_is_reported(self, action, tmp_path, monkeypatch):
        run = MagicMock(side_effect=subprocess.TimeoutExpired("x", 3))
        monkeypatch.setattr(subprocess, "run", run)
        result = action._execute_command("x", tmp_path, 3)
        assert result["timeout"] is True
        assert result["success"] is False
        assert result["returncode"] == -1


class TestExecuteTier:
    def test_all_checks_pass(self, action, project):
        proj, _ = project
        result = action.execute_tier(proj, "essential")
        assert result.success is True
        assert sorted(result.successful_checks) == ["lint", "test", "typecheck"]
        assert result.failed_checks == []
        assert result.partial_success is False
        assert result.executed_checks == ["test", "lint", "typecheck"]
        assert result.environment == "pixi-essential"
        assert result.compatibility_check is True
        assert result.timeout_seconds == 120
        assert result.execution_time > 0

    def test_dry_run_executes_nothing(self, action, project):
        proj, script = project
        script("test", "exit 1")
        result = action.execute_tier(proj, "extended", dry_run=True)
        assert result.success is True
        assert result.executed_checks == []
        assert result.successful_checks == []
        assert result.detected_patterns["package_manager"] == "pixi"

    def test_one_failure_gives_partial_success_and_details(self, action, project):
        proj, script = project
        script("lint", "echo 'lint is unhappy' >&2; exit 1")
        result = action.execute_tier(proj, "essential")
        assert result.success is False
        assert result.failed_checks == ["lint"]
        assert sorted(result.successful_checks) == ["test", "typecheck"]
        assert result.partial_success is True
        assert result.error_details == "lint: lint is unhappy\n"
        assert result.failure_reason is None

    def test_all_fail_is_not_partial(self, action, project):
        proj, script = project
        for check in ("test", "lint", "typecheck"):
            script(check, "exit 1")
        result = action.execute_tier(proj, "essential")
        assert result.success is False
        assert sorted(result.failed_checks) == ["lint", "test", "typecheck"]
        assert result.partial_success is False

    @pytest.mark.parametrize("code", ["F821", "E9"])
    def test_critical_lint_violation_fails_fast(self, action, project, code):
        proj, script = project
        script("lint", f"echo '{code} undefined name' >&2; exit 1")
        result = action.execute_tier(proj, "essential")
        assert result.success is False
        assert result.failure_reason == "critical_lint_violations"
        assert result.failed_fast is True
        assert code in result.error_details
        assert "lint" in result.failed_checks

    def test_sequential_stops_after_critical_failure(self, action, project):
        proj, script = project
        script("test", "echo 'F821 boom' >&2; exit 1")
        result = action.execute_tier(proj, "essential", parallel=False)
        assert result.success is False
        assert result.failure_reason == "critical_lint_violations"
        assert result.failed_checks == ["test"]
        assert result.successful_checks == []
        # the plan still lists everything that was scheduled
        assert result.executed_checks == ["test", "lint", "typecheck"]

    def test_sequential_noncritical_failure_continues(self, action, project):
        proj, script = project
        script("test", "echo plain failure >&2; exit 1")
        result = action.execute_tier(proj, "essential", parallel=False)
        assert result.failed_checks == ["test"]
        assert sorted(result.successful_checks) == ["lint", "typecheck"]
        assert result.partial_success is True

    def test_timeout_is_reported_as_failure_reason(self, action, project):
        proj, script = project
        script("test", "exec sleep 30")
        result = action.execute_tier(proj, "essential", timeout=1)
        assert result.success is False
        assert result.failure_reason == "timeout"
        assert result.error_details == "Command test timed out"
        assert result.timeout_seconds == 1
        assert "test" in result.failed_checks

    def test_config_overrides_are_applied(self, action, project):
        proj, _ = project
        result = action.execute_tier(
            proj,
            "essential",
            config_overrides={
                "timeouts": {"test": 77},
                "thresholds": {"coverage": 55.0},
                "tools": {"ruff": {"line-length": 99}},
            },
        )
        assert result.timeout_seconds == 77
        assert result.config.thresholds["coverage"] == 55.0
        assert result.config.thresholds["complexity"] == 10
        assert result.config.tools == {"ruff": {"line-length": 99}}

    def test_full_tier_success_writes_reports(self, action, project):
        proj, _ = project
        result = action.execute_tier(proj, "full")
        assert result.success is True
        assert len(result.successful_checks) == 5
        reports = proj / "reports"
        assert (reports / "junit.xml").read_text().startswith("<?xml")
        assert "<coverage" in (reports / "coverage.xml").read_text()
        assert '"version": "2.1.0"' in (reports / "security.sarif").read_text()

    def test_full_tier_failure_writes_no_reports(self, action, project):
        proj, script = project
        script("check-all", "exit 1")
        result = action.execute_tier(proj, "full")
        assert result.success is False
        assert result.failed_checks == ["check-all"]
        assert not (proj / "reports").exists()

    def test_non_full_tier_writes_no_reports(self, action, project):
        proj, _ = project
        action.execute_tier(proj, "extended")
        assert not (proj / "reports").exists()

    def test_executor_exception_becomes_execution_error(
        self, action, project, monkeypatch
    ):
        proj, _ = project

        def explode(*_a, **_k):
            raise RuntimeError("pool exploded")

        monkeypatch.setattr(action, "_execute_commands_parallel", explode)
        result = action.execute_tier(proj, "essential")
        assert result.success is False
        assert result.failure_reason == "execution_error"
        assert result.error_details == "pool exploded"

    def test_overall_timeout_expiry_is_reported(self, action, project, monkeypatch):
        proj, _ = project

        def expire(*_a, **_k):
            raise subprocess.TimeoutExpired("x", 5)

        monkeypatch.setattr(action, "_execute_commands_sequential", expire)
        result = action.execute_tier(proj, "essential", timeout=5, parallel=False)
        assert result.success is False
        assert result.failure_reason == "timeout"
        assert result.error_details == "Overall execution timed out after 5 seconds"

    def test_pip_project_uses_python_module_commands(self, action, project, tmp_path):
        _, _ = project  # fixture puts fake tools first on PATH
        fake_python = tmp_path / "bin" / "python"
        fake_python.write_text('#!/bin/sh\necho "module $2 missing" >&2\nexit 1\n')
        fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
        bare = tmp_path / "bare"
        bare.mkdir()
        result = action.execute_tier(bare, "essential", timeout=30)
        assert result.environment == "pip-essential"
        assert result.success is False
        assert sorted(result.failed_checks) == ["lint", "test", "typecheck"]
        assert "test: module test missing" in result.error_details


class TestParallelAggregation:
    def test_future_exception_is_captured_per_command(
        self, action, tmp_path, monkeypatch
    ):
        def flaky(cmd, _dir, _timeout):
            if cmd.endswith("bad"):
                raise RuntimeError("worker died")
            return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

        monkeypatch.setattr(action, "_execute_command", flaky)
        results = action._execute_commands_parallel(
            ["pixi run good", "pixi run bad"], tmp_path, 5
        )
        assert results["good"]["success"] is True
        assert results["bad"] == {
            "success": False,
            "stdout": "",
            "stderr": "worker died",
            "returncode": -1,
        }

    def test_single_word_command_keyed_by_whole_command(self, action, tmp_path):
        results = action._execute_commands_parallel(["true"], tmp_path, 5)
        assert list(results) == ["true"]
        assert results["true"]["success"] is True

    def test_sequential_without_fail_fast_runs_everything(
        self, action, tmp_path, monkeypatch
    ):
        seen = []

        def fake(cmd, _dir, _timeout):
            seen.append(cmd)
            return {"success": False, "stdout": "", "stderr": "F821", "returncode": 1}

        monkeypatch.setattr(action, "_execute_command", fake)
        results = action._execute_commands_sequential(
            ["a b", "c d"], tmp_path, 5, fail_fast=False
        )
        assert seen == ["a b", "c d"]
        assert set(results) == {"b", "d"}


class TestCleanup:
    def test_cleanup_terminates_running_processes(self, action, tmp_path):
        import os

        proc = subprocess.Popen(["sleep", "60"], cwd=tmp_path, preexec_fn=os.setsid)
        action._running_processes.append(proc)
        action.cleanup()
        assert proc.poll() is not None
        assert action._running_processes == []

    def test_cleanup_removes_already_finished_processes(self, action, tmp_path):
        proc = subprocess.Popen(["true"], cwd=tmp_path)
        proc.wait()
        action._running_processes.append(proc)
        action.cleanup()
        assert action._running_processes == []

    def test_cleanup_survives_unsignalable_process(self, action):
        ghost = MagicMock()
        ghost.poll.return_value = None
        ghost.pid = 2**22 + 12345  # no such process
        action._running_processes.append(ghost)
        action.cleanup()
        assert action._running_processes == []


def test_generate_reports_creates_reports_dir(tmp_path):
    action = QualityGatesAction()
    action._generate_reports(Path(tmp_path), {}, "full")
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == [
        "coverage.xml",
        "junit.xml",
        "security.sarif",
    ]
