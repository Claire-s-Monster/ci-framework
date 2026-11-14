"""Behavioural tests for framework.action_shellcheck.

Complements framework/tests/workflows/test_action_shellcheck.py. That file pins
discovery and the headline suppression rules; this one covers extraction from
real YAML, source-line/column mapping, the finding filter, the fail-closed
error paths and the CLI exit codes.

Steps are built the way production builds them (`iter_run_steps` over a real
file), because `block_indent` reads `step.path` from disk. Only the shellcheck
subprocess boundary is faked; tests that need the real binary use the
pixi-pinned one and skip cleanly otherwise.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from framework import action_shellcheck as mod
from framework.action_shellcheck import (
    Finding,
    RunStep,
    block_indent,
    body_start_line,
    build_script,
    discover_action_files,
    iter_run_steps,
    main,
    neutralize_expressions,
    placeholder_spans,
    shellcheck_step,
)


def _pinned_shellcheck() -> str | None:
    found = shutil.which("shellcheck")
    prefix = os.environ.get("CONDA_PREFIX")
    if found and prefix and Path(found).is_relative_to(Path(prefix)):
        return found
    return None


requires_shellcheck = pytest.mark.skipif(
    _pinned_shellcheck() is None,
    reason="no pixi-pinned shellcheck in this environment",
)

ACTION_YAML = """\
name: demo
runs:
  using: composite
  steps:
    - name: first
      shell: bash
      run: |
        echo hello
        echo $UNQUOTED
    - shell: sh
      run: echo plain
    - name: powershell step
      shell: pwsh
      run: Write-Host hi
    - name: uses step
      uses: actions/checkout@v4
    - name: no shell
      run: echo default
"""


def _write_action(tmp_path: Path, text: str = ACTION_YAML) -> Path:
    path = tmp_path / "action.yml"
    path.write_text(text)
    return path


class _Captured:
    """What the faked shellcheck was invoked with."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.scripts: list[str] = []


def _fake_shellcheck(monkeypatch, stdout="", stderr="", returncode=0) -> _Captured:
    """Replace the subprocess boundary; return what it was called with."""
    seen = _Captured()

    def _run(cmd, **kwargs):
        seen.commands.append(cmd)
        seen.scripts.append(Path(cmd[-1]).read_text())
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr(mod.subprocess, "run", _run)
    return seen


def _block_step(tmp_path: Path, body_line: str) -> RunStep:
    """A real extracted step: block-scalar run body indented 8 columns."""
    text = (
        "runs:\n"
        "  using: composite\n"
        "  steps:\n"
        "    - name: s\n"
        "      shell: bash\n"
        "      run: |\n"
        f"        {body_line}\n"
    )
    return next(iter_run_steps(_write_action(tmp_path, text)))


class TestIterRunSteps:
    def test_extracts_run_steps_with_names_shells_and_bodies(self, tmp_path):
        steps = list(iter_run_steps(_write_action(tmp_path)))
        assert [s.step_name for s in steps] == [
            "first",
            "<unnamed>",
            "powershell step",
            "no shell",
        ]
        assert [s.shell for s in steps] == ["bash", "sh", "pwsh", mod.DEFAULT_SHELL]
        assert steps[0].body == "echo hello\necho $UNQUOTED\n"
        assert steps[1].body == "echo plain"

    def test_uses_steps_are_not_extracted(self, tmp_path):
        names = [s.step_name for s in iter_run_steps(_write_action(tmp_path))]
        assert "uses step" not in names

    def test_start_line_points_at_first_body_line(self, tmp_path):
        path = _write_action(tmp_path)
        steps = list(iter_run_steps(path))
        lines = path.read_text().splitlines()
        assert lines[steps[0].start_line - 1].strip() == "echo hello"
        # Plain scalar: the mark already is the content line.
        assert lines[steps[1].start_line - 1].strip().endswith("echo plain")

    def test_empty_file_yields_nothing(self, tmp_path):
        assert list(iter_run_steps(_write_action(tmp_path, ""))) == []

    @pytest.mark.parametrize(
        "text",
        [
            "name: x\n",
            "runs: [a, b]\n",
            "runs:\n  using: composite\n",
            "runs:\n  steps: not-a-list\n",
            "runs:\n  steps:\n    - name: x\n      run: [a]\n",
            "- just\n- a list\n",
        ],
    )
    def test_malformed_or_irrelevant_shapes_yield_nothing(self, tmp_path, text):
        assert list(iter_run_steps(_write_action(tmp_path, text))) == []

    def test_non_scalar_name_and_shell_fall_back_to_defaults(self, tmp_path):
        text = (
            "runs:\n  steps:\n"
            "    - name: [a]\n      shell: {x: y}\n      run: echo hi\n"
        )
        (step,) = iter_run_steps(_write_action(tmp_path, text))
        assert step.step_name == "<unnamed>"
        assert step.shell == mod.DEFAULT_SHELL


class TestBodyStartLine:
    def test_block_and_plain_scalars(self, tmp_path):
        import yaml

        block = yaml.compose("run: |\n  a\n")
        plain = yaml.compose("run: a\n")
        folded = yaml.compose("run: >\n  a\n")
        assert body_start_line(block.value[0][1]) == 2
        assert body_start_line(plain.value[0][1]) == 1
        assert body_start_line(folded.value[0][1]) == 2


class TestBlockIndent:
    def test_recovers_stripped_block_indentation(self, tmp_path):
        assert block_indent(_block_step(tmp_path, "echo hi")) == 8

    def test_empty_body_is_zero(self, tmp_path):
        step = RunStep(_write_action(tmp_path), "s", "bash", "", 1)
        assert block_indent(step) == 0

    def test_start_line_beyond_file_is_zero(self, tmp_path):
        step = RunStep(_write_action(tmp_path), "s", "bash", "echo\n", 9999)
        assert block_indent(step) == 0

    def test_start_line_zero_is_zero(self, tmp_path):
        step = RunStep(_write_action(tmp_path), "s", "bash", "echo\n", 0)
        assert block_indent(step) == 0

    def test_body_own_indentation_is_subtracted(self, tmp_path):
        path = tmp_path / "a.yml"
        path.write_text("      indented\n")
        step = RunStep(path, "s", "bash", "  indented\n", 1)
        assert block_indent(step) == 4


class TestPlaceholders:
    def test_placeholder_has_exact_length(self):
        assert mod._placeholder_name(0) == ""
        assert mod._placeholder_name(-3) == ""
        assert mod._placeholder_name(1) == "G"
        name = mod._placeholder_name(20)
        assert len(name) == 20
        assert name.isidentifier()

    def test_multiline_expression_keeps_line_count_and_comments_rest(self):
        body = "echo ${{ a ==\n  b }} done\nnext\n"
        script, names = neutralize_expressions(body)
        assert script.count("\n") == body.count("\n")
        lines = script.splitlines()
        assert lines[0].startswith("echo ${") and names
        assert lines[1].startswith("#x")
        assert len(lines[1]) == len(body.splitlines()[1])

    def test_multiline_expression_blank_continuation_line(self):
        script, _ = neutralize_expressions("${{ a\n\n b }}")
        assert script.splitlines()[1] == ""

    def test_minimal_expression_gets_a_two_character_name(self):
        script, names = neutralize_expressions("echo ${{}}")
        assert names == {"GH"}
        assert script == "echo ${GH}"

    def test_spans_empty_without_names(self):
        assert placeholder_spans("echo hi\n", set()) == {}

    def test_spans_are_one_based_inclusive_columns(self):
        body = 'echo "${{ inputs.a }}" ${{ inputs.b }}\n'
        script, names = neutralize_expressions(body)
        spans = placeholder_spans(script, names)
        assert spans == {1: [(7, 21), (24, 38)]}

    def test_build_script_declares_placeholders_and_counts_preamble(self):
        step = RunStep(Path("x"), "s", "bash", 'echo "${{ a }}" ${{ bb }}\n', 1)
        script, preamble_lines, spans = build_script(step)
        assert preamble_lines == script.split("echo", 1)[0].count("\n")
        assert preamble_lines == 2
        assert all(line.endswith('=""') for line in script.splitlines()[:2])
        assert set(spans) == {3}

    def test_build_script_without_expressions_has_no_preamble(self):
        step = RunStep(Path("x"), "s", "bash", "echo hi\n", 1)
        script, preamble_lines, spans = build_script(step)
        assert (script, preamble_lines, spans) == ("echo hi\n", 0, {})


class TestExpressionArtifactDetection:
    def test_column_inside_span(self):
        assert mod._is_expression_artifact("echo xxxxx", 6, [(6, 10)])
        assert mod._is_expression_artifact("echo xxxxx", 10, [(6, 10)])
        assert not mod._is_expression_artifact("echo xxxxx", 5, [(6, 10)])
        assert not mod._is_expression_artifact("echo xxxxx", 11, [(6, 10)])

    def test_opening_quote_enclosing_placeholder(self):
        line = "echo '${P}'"
        assert mod._is_expression_artifact(line, 6, [(7, 10)])

    def test_quote_not_enclosing_placeholder(self):
        line = "echo 'abc' ${P}"
        assert not mod._is_expression_artifact(line, 6, [(12, 15)])

    def test_unterminated_quote_or_non_quote(self):
        assert mod._quoted_span("echo 'abc", 6) is None
        assert mod._quoted_span("echo abc", 6) is None
        assert mod._quoted_span("echo abc", 0) is None
        assert mod._quoted_span("echo abc", 99) is None
        assert mod._quoted_span('echo "abc"', 6) == (6, 10)


class TestShellcheckStepWithFakedBinary:
    def test_command_line_carries_shell_and_severity(self, tmp_path, monkeypatch):
        seen = _fake_shellcheck(monkeypatch)
        step = _block_step(tmp_path, "echo hi")
        assert shellcheck_step(step, "warning") == []
        cmd = seen.commands[0]
        assert cmd[0] == "shellcheck"
        assert "--shell=bash" in cmd
        assert "--severity=warning" in cmd
        assert "--format=gcc" in cmd

    def test_default_severity_is_style(self, tmp_path, monkeypatch):
        seen = _fake_shellcheck(monkeypatch)
        shellcheck_step(_block_step(tmp_path, "echo hi"))
        assert "--severity=style" in seen.commands[0]

    def test_finding_is_mapped_to_file_line_and_column(self, tmp_path, monkeypatch):
        out = "t.sh:1:6: warning: Double quote to prevent globbing [SC2086]\n"
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        step = _block_step(tmp_path, "echo $X")
        (finding,) = shellcheck_step(step)
        assert finding.level == "warning"
        assert "SC2086" in finding.message
        assert finding.step_name == "s"
        assert finding.path == step.path
        assert finding.line == step.start_line
        assert finding.column == 6 + 8
        text = step.path.read_text().splitlines()[finding.line - 1]
        assert text[finding.column - 1] == "$"

    def test_preamble_lines_are_subtracted_and_preamble_findings_dropped(
        self, tmp_path, monkeypatch
    ):
        out = (
            "t.sh:1:1: warning: scaffolding noise [SC2034]\n"
            "t.sh:2:1: warning: real one [SC9999]\n"
        )
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        step = _block_step(tmp_path, 'echo "${{ inputs.a }}"')
        (finding,) = shellcheck_step(step)
        assert "real one" in finding.message
        assert finding.line == step.start_line

    def test_artifact_findings_are_suppressed_but_sc2086_is_kept(
        self, tmp_path, monkeypatch
    ):
        out = (
            "t.sh:2:6: info: Expressions don't expand in single quotes [SC2016]\n"
            "t.sh:2:7: warning: Double quote to prevent globbing [SC2086]\n"
        )
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        step = _block_step(tmp_path, "echo '${{ inputs.json }}'")
        findings = shellcheck_step(step)
        assert [f.message for f in findings] == [
            "Double quote to prevent globbing [SC2086]"
        ]

    def test_all_findings_filtered_is_a_clean_result_not_an_error(
        self, tmp_path, monkeypatch
    ):
        out = "t.sh:2:6: info: Expressions don't expand in single quotes [SC2016]\n"
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        step = _block_step(tmp_path, "echo '${{ inputs.json }}'")
        assert shellcheck_step(step) == []

    def test_finding_beyond_script_is_kept_when_not_an_artifact(
        self, tmp_path, monkeypatch
    ):
        out = "t.sh:99:1: warning: odd [SC1234]\n"
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        (finding,) = shellcheck_step(_block_step(tmp_path, "echo hi"))
        assert finding.message == "odd [SC1234]"

    def test_finding_without_code_is_never_filtered(self, tmp_path, monkeypatch):
        out = "t.sh:2:6: error: parse trouble\n"
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        step = _block_step(tmp_path, "echo '${{ inputs.json }}'")
        assert len(shellcheck_step(step)) == 1

    def test_non_gcc_lines_are_ignored_alongside_real_ones(self, tmp_path, monkeypatch):
        out = "banner line\nt.sh:1:1: note: hello [SC1000]\n"
        _fake_shellcheck(monkeypatch, stdout=out, returncode=1)
        assert len(shellcheck_step(_block_step(tmp_path, "echo hi"))) == 1

    def test_temp_script_is_removed_afterwards(self, tmp_path, monkeypatch):
        seen = _fake_shellcheck(monkeypatch)
        shellcheck_step(_block_step(tmp_path, "echo hi"))
        assert not Path(seen.commands[0][-1]).exists()

    def test_temp_script_is_removed_when_shellcheck_raises(self, tmp_path, monkeypatch):
        seen_paths: list[str] = []

        def _boom(cmd, **kwargs):
            seen_paths.append(cmd[-1])
            raise OSError("exec failed")

        monkeypatch.setattr(mod.subprocess, "run", _boom)
        with pytest.raises(OSError, match="exec failed"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))
        assert not Path(seen_paths[0]).exists()

    @pytest.mark.parametrize("returncode", [2, 3, 127])
    def test_unexpected_exit_code_raises(self, tmp_path, monkeypatch, returncode):
        _fake_shellcheck(monkeypatch, returncode=returncode)
        with pytest.raises(RuntimeError, match="did not run"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))

    def test_stderr_output_raises_even_on_exit_zero(self, tmp_path, monkeypatch):
        _fake_shellcheck(monkeypatch, stderr="warning: something", returncode=0)
        with pytest.raises(RuntimeError, match="something"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))

    def test_empty_stderr_is_reported_as_placeholder(self, tmp_path, monkeypatch):
        _fake_shellcheck(monkeypatch, returncode=5)
        with pytest.raises(RuntimeError, match="<empty>"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))

    def test_exit_one_with_unparseable_output_raises(self, tmp_path, monkeypatch):
        _fake_shellcheck(monkeypatch, stdout="totally different format", returncode=1)
        with pytest.raises(RuntimeError, match="could be parsed"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))

    def test_exit_one_with_no_output_raises(self, tmp_path, monkeypatch):
        _fake_shellcheck(monkeypatch, stdout="", returncode=1)
        with pytest.raises(RuntimeError, match="could be parsed"):
            shellcheck_step(_block_step(tmp_path, "echo hi"))


class TestFindingStr:
    def test_str_format(self):
        finding = Finding(Path("a/action.yml"), 7, 3, "warning", "msg [SC1]", "step")
        assert str(finding) == "a/action.yml:7:3: warning: msg [SC1]  (step: step)"


@requires_shellcheck
class TestRealShellcheck:
    def test_known_bad_input_is_flagged_at_the_right_file_position(self, tmp_path):
        """Vacuity guard: a defect IS reported, mapped to its exact source char."""
        path = _write_action(tmp_path)
        step = next(iter_run_steps(path))
        findings = shellcheck_step(step)
        assert findings, "unquoted $UNQUOTED was not flagged"
        finding = findings[0]
        assert "SC2086" in finding.message
        source = path.read_text().splitlines()[finding.line - 1]
        assert source[finding.column - 1 :].startswith("$UNQUOTED")

    def test_clean_input_is_not_flagged(self, tmp_path):
        assert shellcheck_step(_block_step(tmp_path, 'echo "hi"')) == []

    def test_cli_reports_defect_and_exits_one(self, tmp_path, capsys):
        path = _write_action(tmp_path)
        assert main([str(path)]) == 1
        out = capsys.readouterr().out
        assert "SC2086" in out
        assert "finding(s)" in out

    def test_severity_filter_hides_style_only_findings(self, tmp_path, capsys):
        path = _write_action(
            tmp_path,
            "runs:\n  steps:\n    - shell: bash\n      run: |\n"
            "        x=$(echo hi)\n        echo $x\n",
        )
        assert main([str(path)]) == 1
        capsys.readouterr()
        assert main([str(path), "--severity", "error"]) == 0


class TestMainExitCodes:
    @staticmethod
    def _with_shellcheck_on_path(monkeypatch):
        monkeypatch.setattr(mod.shutil, "which", lambda _name: "/usr/bin/shellcheck")

    def test_missing_shellcheck_exits_two(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
        assert main([str(_write_action(tmp_path))]) == 2
        assert "shellcheck not found" in capsys.readouterr().err

    def test_no_discovered_actions_exits_two(self, monkeypatch, capsys):
        self._with_shellcheck_on_path(monkeypatch)
        monkeypatch.setattr(mod, "discover_action_files", lambda: [])
        assert main([]) == 2
        assert "refusing to report success" in capsys.readouterr().err

    def test_default_discovery_is_used_when_no_paths_given(
        self, tmp_path, monkeypatch, capsys
    ):
        self._with_shellcheck_on_path(monkeypatch)
        path = _write_action(tmp_path)
        monkeypatch.setattr(mod, "discover_action_files", lambda: [path])
        monkeypatch.setattr(mod, "shellcheck_step", lambda step, sev: [])
        assert main([]) == 0
        assert "3 run block(s) across 1 action file(s), 0 finding(s)" in (
            capsys.readouterr().out
        )

    def test_only_unsupported_shells_exits_two(self, tmp_path, monkeypatch, capsys):
        self._with_shellcheck_on_path(monkeypatch)
        path = _write_action(
            tmp_path,
            "runs:\n  steps:\n    - shell: pwsh\n      run: Write-Host hi\n",
        )
        assert main([str(path)]) == 2
        assert "no shellcheckable run: bodies" in capsys.readouterr().err

    def test_file_with_no_run_steps_exits_two(self, tmp_path, monkeypatch):
        self._with_shellcheck_on_path(monkeypatch)
        path = _write_action(tmp_path, "name: x\n")
        assert main([str(path)]) == 2

    def test_runtime_error_from_shellcheck_exits_two(
        self, tmp_path, monkeypatch, capsys
    ):
        self._with_shellcheck_on_path(monkeypatch)

        def _raise(step, severity):
            raise RuntimeError("blind gate")

        monkeypatch.setattr(mod, "shellcheck_step", _raise)
        assert main([str(_write_action(tmp_path))]) == 2
        assert "blind gate" in capsys.readouterr().err

    def test_findings_exit_one_sorted_and_skipped_shells_listed(
        self, tmp_path, monkeypatch, capsys
    ):
        self._with_shellcheck_on_path(monkeypatch)
        path = _write_action(tmp_path)

        def _fake(step, severity):
            assert severity == "warning"
            return [
                Finding(step.path, 9, 2, "warning", "later", step.step_name),
                Finding(step.path, 3, 5, "warning", "earlier", step.step_name),
            ]

        monkeypatch.setattr(mod, "shellcheck_step", _fake)
        assert main([str(path), "--severity", "warning"]) == 1
        out = capsys.readouterr().out
        assert out.index("earlier") < out.index("later")
        assert "skipped (shellcheck cannot check this shell)" in out
        assert "shell=pwsh" in out
        assert "powershell step" in out
        assert "finding(s)" in out

    def test_clean_run_exits_zero(self, tmp_path, monkeypatch, capsys):
        self._with_shellcheck_on_path(monkeypatch)
        monkeypatch.setattr(mod, "shellcheck_step", lambda step, sev: [])
        assert main([str(_write_action(tmp_path))]) == 0
        assert "0 finding(s)" in capsys.readouterr().out

    def test_invalid_severity_is_rejected_by_argparse(self, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            main([str(_write_action(tmp_path)), "--severity", "bogus"])
        assert excinfo.value.code == 2


class TestDiscoverActionFiles:
    def test_finds_both_filenames_and_ignores_missing_roots(self, tmp_path):
        (tmp_path / "a" / "x").mkdir(parents=True)
        (tmp_path / "a" / "x" / "action.yml").write_text("")
        (tmp_path / "a" / "action.yaml").write_text("")
        (tmp_path / "a" / "other.yml").write_text("")
        found = discover_action_files((tmp_path / "a", tmp_path / "missing"))
        assert found == sorted(
            [tmp_path / "a" / "x" / "action.yml", tmp_path / "a" / "action.yaml"]
        )
