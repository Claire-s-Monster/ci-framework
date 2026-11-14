"""Behavioural tests for SafeCommandExecutor.

Only the process boundary is faked: allow-listed tool names (ruff, black, ...)
are shell scripts placed first on PATH, so the real subprocess, timeout,
truncation and error-mapping logic runs unmodified.
"""

import re
import signal
import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from framework.self_healing import command_executor as ce
from framework.self_healing.command_executor import (
    CommandExecutionError,
    CommandTimeoutError,
    SafeCommandExecutor,
)


def _fake_tool(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def bin_dir(tmp_path, monkeypatch):
    d = tmp_path / "bin"
    d.mkdir()
    monkeypatch.setenv("PATH", f"{d}:/usr/bin:/bin")
    return d


@pytest.fixture
def executor(tmp_path):
    return SafeCommandExecutor(default_timeout=10, working_directory=str(tmp_path))


class TestExecute:
    def test_nonzero_exit_is_returned_not_raised(self, executor, bin_dir):
        _fake_tool(bin_dir, "ruff", "echo out; echo err >&2; exit 3")
        result = executor.execute("ruff check .")
        assert result.return_code == 3
        assert result.stdout.strip() == "out"
        assert result.stderr.strip() == "err"
        assert result.timed_out is False

    def test_runs_in_requested_working_directory(self, executor, bin_dir, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _fake_tool(bin_dir, "ruff", "pwd")
        result = executor.execute("ruff", working_directory=str(sub))
        assert result.stdout.strip() == str(sub.resolve())
        assert result.working_directory == str(sub.resolve())

    def test_env_overrides_reach_the_process(self, executor, bin_dir):
        _fake_tool(bin_dir, "ruff", 'echo "$MY_FLAG"')
        result = executor.execute("ruff", env={"MY_FLAG": "on"})
        assert result.stdout.strip() == "on"

    def test_timeout_raises_with_partial_result_and_kills_process(
        self, executor, bin_dir
    ):
        _fake_tool(bin_dir, "ruff", "echo started; exec sleep 30")
        with pytest.raises(CommandTimeoutError) as exc:
            executor.execute("ruff", timeout=1)
        assert "timed out after 1 seconds" in str(exc.value)
        assert exc.value.result is not None
        assert exc.value.result.timed_out is True
        assert exc.value.result.return_code != 0
        assert exc.value.result.execution_time < 20

    def test_stdout_and_stderr_are_truncated_at_limit(self, tmp_path, bin_dir):
        _fake_tool(
            bin_dir,
            "ruff",
            "printf 'a%.0s' $(seq 1 100); printf 'b%.0s' $(seq 1 100) >&2",
        )
        small = SafeCommandExecutor(max_output_size=10, working_directory=str(tmp_path))
        result = small.execute("ruff")
        assert result.stdout == "a" * 10 + "\n[OUTPUT TRUNCATED - SIZE LIMIT EXCEEDED]"
        assert (
            result.stderr
            == "b" * 10 + "\n[ERROR OUTPUT TRUNCATED - SIZE LIMIT EXCEEDED]"
        )

    def test_missing_binary_maps_to_execution_error(self, executor):
        with pytest.raises(CommandExecutionError, match="Command not found") as exc:
            executor.execute("no-such-binary-xyz", check_allowed=False)
        assert isinstance(exc.value.__cause__, FileNotFoundError)

    def test_non_executable_file_maps_to_permission_error(self, executor, tmp_path):
        script = tmp_path / "noexec.sh"
        script.write_text("#!/bin/sh\necho hi\n")
        script.chmod(0o644)
        with pytest.raises(CommandExecutionError, match="Permission denied") as exc:
            executor.execute(str(script), check_allowed=False)
        assert isinstance(exc.value.__cause__, PermissionError)

    def test_unexpected_popen_failure_maps_to_execution_error(
        self, executor, monkeypatch
    ):
        def boom(*_a, **_k):
            raise OSError("kernel said no")

        monkeypatch.setattr(ce.subprocess, "Popen", boom)
        with pytest.raises(
            CommandExecutionError, match="Unexpected error executing command: kernel"
        ):
            executor.execute("ruff", check_allowed=False)

    def test_unbalanced_quotes_raise_value_error(self, executor):
        with pytest.raises(ValueError):
            executor.execute("ruff 'unterminated", check_allowed=False)

    @pytest.mark.parametrize(
        ("command", "message"),
        [
            ("ruff check . && echo hi", "Dangerous command pattern detected: &&"),
            ("ruff check $(whoami)", "Dangerous command pattern detected: $("),
            ("python script.py", "Command not in allowlist: python"),
            ("/usr/bin/perl -e 1", "Command not in allowlist: perl"),
            ("rm -rf /", "Dangerous command pattern detected: rm "),
            ("", "Empty command"),
        ],
    )
    def test_unsafe_commands_are_rejected_before_running(
        self, executor, command, message
    ):
        with pytest.raises(ValueError, match=re.escape(message)):
            executor.execute(command)

    def test_allowlist_uses_basename_of_path(self, executor, bin_dir):
        _fake_tool(bin_dir, "ruff", "echo ok")
        result = executor.execute(f"{bin_dir}/ruff")
        assert result.return_code == 0


class TestKillProcessGroup:
    def test_sigterm_then_sigkill(self, executor, monkeypatch):
        calls = []
        monkeypatch.setattr(ce.os, "getpgid", lambda pid: pid + 1)
        monkeypatch.setattr(ce.os, "killpg", lambda pg, sig: calls.append((pg, sig)))
        monkeypatch.setattr(ce.time, "sleep", lambda _s: None)
        executor._kill_process_group(MagicMock(pid=41))
        assert calls == [(42, signal.SIGTERM), (42, signal.SIGKILL)]

    def test_already_dead_after_sigterm_is_tolerated(self, executor, monkeypatch):
        sent = []

        def killpg(pg, sig):
            sent.append(sig)
            if sig == signal.SIGKILL:
                raise ProcessLookupError

        monkeypatch.setattr(ce.os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(ce.os, "killpg", killpg)
        monkeypatch.setattr(ce.time, "sleep", lambda _s: None)
        executor._kill_process_group(MagicMock(pid=7))
        assert sent == [signal.SIGTERM, signal.SIGKILL]

    @pytest.mark.parametrize("exc", [ProcessLookupError, PermissionError])
    def test_lookup_or_permission_error_is_swallowed(self, executor, monkeypatch, exc):
        def getpgid(_pid):
            raise exc

        monkeypatch.setattr(ce.os, "getpgid", getpgid)
        executor._kill_process_group(MagicMock(pid=7))  # must not raise


class TestExecuteFormattingCommand:
    @pytest.mark.parametrize(
        ("tool", "var", "expected"),
        [
            ("black", "BLACK_EXPERIMENTAL_STRING_PROCESSING", "1"),
            ("ruff", "RUFF_CACHE_DIR", str(Path.home() / ".cache" / "ruff")),
            ("isort", "ISORT_QUIET", "1"),
        ],
    )
    def test_tool_specific_environment(self, executor, bin_dir, tool, var, expected):
        _fake_tool(bin_dir, tool, f'echo "${var}"')
        result = executor.execute_formatting_command(tool, tool)
        assert result.stdout.strip() == expected

    def test_other_tool_gets_no_special_env(self, executor, bin_dir):
        _fake_tool(
            bin_dir,
            "yapf",
            'echo "[$ISORT_QUIET$BLACK_EXPERIMENTAL_STRING_PROCESSING]"',
        )
        result = executor.execute_formatting_command("yapf", "yapf")
        assert result.stdout.strip() == "[]"

    def test_disallowed_command_is_still_rejected(self, executor):
        with pytest.raises(ValueError, match="Dangerous command pattern"):
            executor.execute_formatting_command("black", "rm -rf /")
        with pytest.raises(ValueError, match="not in allowlist: perl"):
            executor.execute_formatting_command("black", "perl -e 1")


class TestDryRunCommand:
    @pytest.fixture(autouse=True)
    def _echo_tools(self, bin_dir):
        for name in ("black", "ruff", "isort", "pixi"):
            _fake_tool(bin_dir, name, 'echo "$@"')

    def test_black_gets_check_and_diff(self, executor):
        assert executor.dry_run_command("black src").stdout.split() == [
            "src",
            "--check",
            "--diff",
        ]

    def test_black_existing_flags_not_duplicated(self, executor):
        out = executor.dry_run_command("black --check --diff src").stdout.split()
        assert out == ["--check", "--diff", "src"]

    def test_ruff_fix_flag_is_removed(self, executor):
        out = executor.dry_run_command("ruff check --fix src").stdout.split()
        assert out == ["check", "src"]

    def test_isort_gets_check_only_and_diff(self, executor):
        out = executor.dry_run_command("isort src").stdout.split()
        assert out == ["src", "--check-only", "--diff"]

    def test_isort_existing_flags_not_duplicated(self, executor):
        out = executor.dry_run_command("isort --check-only --diff src").stdout.split()
        assert out == ["--check-only", "--diff", "src"]

    def test_other_tool_unchanged(self, executor):
        assert executor.dry_run_command("pixi run x").stdout.split() == ["run", "x"]

    def test_empty_command_rejected(self, executor):
        with pytest.raises(ValueError, match="Empty command"):
            executor.dry_run_command("   ")

    def test_result_is_still_allowlist_checked(self, executor):
        with pytest.raises(ValueError, match="not in allowlist"):
            executor.dry_run_command("python -c pass")

    def test_timeout_propagates(self, executor, bin_dir):
        _fake_tool(bin_dir, "black", "exec sleep 30")
        with pytest.raises(CommandTimeoutError):
            executor.dry_run_command("black src", timeout=1)


class TestGetCommandInfo:
    def test_unknown_tool(self, executor):
        assert executor.get_command_info("nope") == {
            "available": False,
            "error": "Unknown tool: nope",
        }

    def test_available_tool_reports_version(self, executor, bin_dir):
        _fake_tool(bin_dir, "black", 'echo "black 24.1 $@"')
        info = executor.get_command_info("black")
        assert info == {
            "available": True,
            "version": "black 24.1 --version",
            "error": None,
        }

    def test_failing_version_command_reports_stderr(self, executor, bin_dir):
        _fake_tool(bin_dir, "ruff", "echo broken >&2; exit 2")
        info = executor.get_command_info("ruff")
        assert info == {"available": False, "version": None, "error": "broken"}

    def test_missing_binary_is_reported_not_raised(self, executor, bin_dir):
        info = executor.get_command_info("autopep8")
        assert info["available"] is False
        assert "Command not found" in info["error"]

    def test_hung_version_command_is_reported_not_raised(
        self, executor, bin_dir, monkeypatch
    ):
        _fake_tool(bin_dir, "isort", "exec sleep 30")
        real_execute = executor.execute
        monkeypatch.setattr(
            executor,
            "execute",
            lambda cmd, timeout=None, check_allowed=True: real_execute(
                cmd, timeout=1, check_allowed=check_allowed
            ),
        )
        info = executor.get_command_info("isort")
        assert info["available"] is False
        assert "timed out" in info["error"]
