"""Tests for code_policy_check module."""

from __future__ import annotations

import pytest

from framework.code_policy_check import PolicyResult, Violation
from framework.code_policy_check import check_file_length


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
