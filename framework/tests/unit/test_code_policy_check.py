"""Tests for code_policy_check module."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from framework.code_policy_check import (
    PolicyResult,
    Violation,
    check_cyclomatic_complexity,
    check_file_length,
    check_function_length,
    format_annotations,
    format_summary,
    run_checks,
)
from framework.code_policy_check import main as cli_main


class TestDataModel:
    def test_violation_fields(self):
        v = Violation(
            file="src/api.py",
            line=1,
            rule="file-too-long",
            message="File has 600 lines",
            severity="warning",
            current_value=600,
            threshold=500,
        )
        assert v.rule == "file-too-long"
        assert v.current_value == 600

    def test_policy_result_has_violations(self):
        v = Violation("f.py", 1, "file-too-long", "msg", "warning", 600, 500)
        result = PolicyResult(violations=[v], files_checked=1, files_clean=0)
        assert result.has_violations is True

    def test_policy_result_no_violations(self):
        result = PolicyResult(violations=[], files_checked=1, files_clean=1)
        assert result.has_violations is False


class TestFileLength:
    def test_file_under_limit_passes(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("x = 1\ny = 2\nz = 3\n")
        violations = check_file_length(f, max_lines=500)
        assert violations == []

    def test_file_over_limit_reports_violation(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(600)) + "\n")
        violations = check_file_length(f, max_lines=500)
        assert len(violations) == 1
        assert violations[0].rule == "file-too-long"
        assert violations[0].current_value == 600
        assert violations[0].threshold == 500

    def test_blank_lines_and_comments_excluded(self, tmp_path):
        f = tmp_path / "mixed.py"
        lines = []
        for i in range(300):
            lines.append(f"x_{i} = {i}")
        for _ in range(250):
            lines.append("")
        for _ in range(50):
            lines.append("# this is a comment")
        f.write_text("\n".join(lines) + "\n")
        violations = check_file_length(f, max_lines=500)
        assert violations == []  # only 300 countable lines

    def test_violation_message_references_ag_level(self, tmp_path):
        f = tmp_path / "huge.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(600)) + "\n")
        violations = check_file_length(f, max_lines=500)
        assert "Organism" in violations[0].message


class TestCyclomaticComplexity:
    def test_simple_function_passes(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("def hello():\n    return 1\n")
        violations = check_cyclomatic_complexity(f, max_cc=10)
        assert violations == []

    def test_complex_function_reports_violation(self, tmp_path):
        f = tmp_path / "complex.py"
        # Build a function with many branches (CC > 10)
        lines = ["def branchy(x):"]
        for i in range(12):
            lines.append(f"    if x == {i}:")
            lines.append(f"        return {i}")
        lines.append("    return -1")
        f.write_text("\n".join(lines) + "\n")
        violations = check_cyclomatic_complexity(f, max_cc=10)
        assert len(violations) == 1
        assert violations[0].rule == "high-complexity"
        assert violations[0].current_value > 10
        assert "branchy" in violations[0].message

    def test_multiple_functions_reports_each(self, tmp_path):
        f = tmp_path / "multi.py"
        lines = []
        for func_name in ("func_a", "func_b"):
            lines.append(f"def {func_name}(x):")
            for i in range(12):
                lines.append(f"    if x == {i}:")
                lines.append(f"        return {i}")
            lines.append("    return -1")
            lines.append("")
        f.write_text("\n".join(lines) + "\n")
        violations = check_cyclomatic_complexity(f, max_cc=10)
        assert len(violations) == 2


class TestFunctionLength:
    def test_short_function_passes(self, tmp_path):
        f = tmp_path / "short.py"
        f.write_text("def hello():\n    return 1\n")
        violations = check_function_length(f, max_lines=50)
        assert violations == []

    def test_long_function_reports_violation(self, tmp_path):
        f = tmp_path / "long_func.py"
        lines = ["def big_func():"]
        for i in range(60):
            lines.append(f"    x_{i} = {i}")
        lines.append("    return x_0")
        f.write_text("\n".join(lines) + "\n")
        violations = check_function_length(f, max_lines=50)
        assert len(violations) == 1
        assert violations[0].rule == "function-too-long"
        assert "big_func" in violations[0].message
        assert violations[0].current_value > 50

    def test_nested_methods_checked_individually(self, tmp_path):
        f = tmp_path / "nested.py"
        lines = ["class Foo:"]
        for method in ("method_a", "method_b"):
            lines.append(f"    def {method}(self):")
            for i in range(55):
                lines.append(f"        x_{i} = {i}")
            lines.append("        return x_0")
            lines.append("")
        f.write_text("\n".join(lines) + "\n")
        violations = check_function_length(f, max_lines=50)
        assert len(violations) == 2


class TestOutputFormatters:
    def _make_violation(self, **kwargs):
        defaults = {
            "file": "src/api.py",
            "line": 1,
            "rule": "file-too-long",
            "message": "File has 600 lines",
            "severity": "warning",
            "current_value": 600,
            "threshold": 500,
        }
        defaults.update(kwargs)
        return Violation(**defaults)

    def test_annotations_format(self):
        v = self._make_violation()
        result = PolicyResult(violations=[v], files_checked=1, files_clean=0)
        output = format_annotations(result)
        assert "::warning file=src/api.py,line=1,title=Code Policy::" in output
        assert "File has 600 lines" in output

    def test_annotations_multiple_violations(self):
        v1 = self._make_violation(rule="file-too-long")
        v2 = self._make_violation(
            line=42,
            rule="high-complexity",
            message="Function `foo` has CC 15",
            current_value=15,
            threshold=10,
        )
        result = PolicyResult(violations=[v1, v2], files_checked=1, files_clean=0)
        output = format_annotations(result)
        assert output.count("::warning") == 2

    def test_summary_markdown_table(self):
        v = self._make_violation()
        result = PolicyResult(violations=[v], files_checked=2, files_clean=1)
        output = format_summary(result)
        assert "## Code Policy Report" in output
        assert "src/api.py" in output
        assert "1 file" in output
        assert "2 files checked" in output

    def test_empty_results_clean_report(self):
        result = PolicyResult(violations=[], files_checked=5, files_clean=5)
        output = format_summary(result)
        assert "No violations" in output
        assert "5 files checked" in output


class TestCLI:
    def _run_main(self, args: list[str], tmp_path: Path, capsys=None):
        """Run CLI main() with given args, returning exit code."""
        old_argv = sys.argv
        old_cwd = os.getcwd()
        try:
            sys.argv = ["code_policy_check", *args]
            os.chdir(tmp_path)
            return cli_main()
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)

    def test_arg_parsing(self, tmp_path, capsys):
        f = tmp_path / "ok.py"
        f.write_text("x = 1\n")
        rc = self._run_main(
            [
                "--files",
                json.dumps([str(f)]),
                "--max-file-lines",
                "500",
                "--max-cyclomatic-complexity",
                "10",
                "--max-function-lines",
                "50",
            ],
            tmp_path,
        )
        assert rc == 0

    def test_always_exits_zero(self, tmp_path, capsys):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(600)) + "\n")
        rc = self._run_main(
            [
                "--files",
                json.dumps([str(f)]),
                "--max-file-lines",
                "500",
                "--max-cyclomatic-complexity",
                "10",
                "--max-function-lines",
                "50",
            ],
            tmp_path,
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "::warning" in captured.out

    def test_files_json_input(self, tmp_path, capsys):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("y = 2\n")
        rc = self._run_main(
            [
                "--files",
                json.dumps([str(f1), str(f2)]),
                "--max-file-lines",
                "500",
                "--max-cyclomatic-complexity",
                "10",
                "--max-function-lines",
                "50",
            ],
            tmp_path,
        )
        assert rc == 0

    def test_exclude_patterns_filter(self, tmp_path, capsys):
        f = tmp_path / "test_foo.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(600)) + "\n")
        rc = self._run_main(
            [
                "--files",
                json.dumps([str(f)]),
                "--exclude-patterns",
                "**/test_*",
                "--max-file-lines",
                "500",
                "--max-cyclomatic-complexity",
                "10",
                "--max-function-lines",
                "50",
            ],
            tmp_path,
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "::warning" not in captured.out  # excluded

    def test_github_output(self, tmp_path, capsys):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(600)) + "\n")
        gh_output = tmp_path / "gh_output.txt"
        gh_output.write_text("")
        rc = self._run_main(
            [
                "--files",
                json.dumps([str(f)]),
                "--max-file-lines",
                "500",
                "--max-cyclomatic-complexity",
                "10",
                "--max-function-lines",
                "50",
                "--github-output",
                str(gh_output),
            ],
            tmp_path,
        )
        assert rc == 0
        output_content = gh_output.read_text()
        assert "violations=1" in output_content
