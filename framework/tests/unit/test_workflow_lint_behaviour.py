"""Behavioural tests for framework.workflow_lint.

Each rule is exercised with known-bad YAML that MUST be flagged and a
known-good counterpart that MUST pass, using small inline fixtures written
to tmp_path and the real YAML parser.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from framework import workflow_lint
from framework.workflow_lint import (
    LintError,
    LintResult,
    check_summary_needs_completeness,
    discover_workflow_files,
    gate_tasks,
    lint_all_workflows,
    lint_workflow,
    main,
)

PYPROJECT = """
[tool.pixi.tasks]
quality = { depends-on = ["typecheck", { task = "lint" }, 7] }
typecheck = "pixi run -e quality typecheck-impl"
typecheck-impl = "mypy ."
lint = { cmd = "ruff check .", depends-on = "not-a-list" }
unrelated = "echo hi"
"""


def write(tmp_path: Path, text: str, name: str = "wf.yml") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(text).lstrip("\n"))
    return path


def rules(result: LintResult) -> list[str]:
    return [e.rule for e in result.errors]


# --------------------------------------------------------------------------
# data classes
# --------------------------------------------------------------------------


def test_lint_error_str_and_result_counts() -> None:
    err = LintError("a.yml", 3, "r", "msg")
    warn = LintError("a.yml", 4, "w", "msg2", severity="warning")
    assert str(err) == "a.yml:3: [error] r: msg"
    assert str(warn) == "a.yml:4: [warning] w: msg2"
    result = LintResult(errors=[err, warn, warn])
    assert result.has_errors
    assert result.error_count == 1
    assert result.warning_count == 2
    assert not LintResult(errors=[warn]).has_errors


# --------------------------------------------------------------------------
# lint_workflow top-level handling
# --------------------------------------------------------------------------


def test_invalid_yaml_reports_parse_error(tmp_path: Path) -> None:
    path = write(tmp_path, "jobs: [unclosed\n  - x: : :\n")
    result = lint_workflow(path)
    assert rules(result) == ["yaml-parse-error"]
    assert result.errors[0].line == 0
    assert result.errors[0].file == str(path)
    assert result.errors[0].message.startswith("Failed to parse YAML")


@pytest.mark.parametrize("body", ["", "- a\n- b\n", "just a string\n"])
def test_non_mapping_yaml_is_ignored(tmp_path: Path, body: str) -> None:
    assert lint_workflow(write(tmp_path, body)).errors == []


def test_clean_workflow_has_no_findings(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo ok
        """,
    )
    assert lint_workflow(path).errors == []


# --------------------------------------------------------------------------
# double-expression-wrap
# --------------------------------------------------------------------------


def test_double_expression_wrap_flagged_with_line(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          first:
            runs-on: x
            steps: []
          second:
            if: ${{ github.event_name == 'push' }}
            runs-on: x
            steps: []
        """,
    )
    errors = lint_workflow(path).errors
    assert rules(lint_workflow(path)) == ["double-expression-wrap"]
    assert errors[0].line == 7
    assert "'second'" in errors[0].message
    assert errors[0].severity == "error"


def test_plain_job_if_not_flagged(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          second:
            if: github.event_name == 'push'
            runs-on: x
            steps: []
        """,
    )
    assert lint_workflow(path).errors == []


def test_non_dict_job_is_skipped_by_all_job_checks(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          weird: just-a-string
        """,
    )
    assert lint_workflow(path).errors == []


# --------------------------------------------------------------------------
# cross-repo-checkout
# --------------------------------------------------------------------------


def test_cross_repo_checkout_is_warning_with_location(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          build:
            runs-on: x
            steps:
              - "just a string step"
              - name: Grab other
                uses: actions/checkout@v4
                with:
                  repository: other/repo
        """,
    )
    result = lint_workflow(path)
    assert rules(result) == ["cross-repo-checkout"]
    err = result.errors[0]
    assert err.severity == "warning"
    assert err.line == 10
    assert "other/repo" in err.message
    assert "Grab other" in err.message
    assert not result.has_errors


def test_same_repo_and_default_checkout_allowed(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          build:
            runs-on: x
            steps:
              - uses: actions/checkout@v4
              - uses: actions/checkout@v4
                with:
                  repository: ${{ github.repository }}
        """,
    )
    assert lint_workflow(path).errors == []


# --------------------------------------------------------------------------
# dependency-review-unguarded
# --------------------------------------------------------------------------


def test_dependency_review_without_guard_flagged(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          dr:
            runs-on: x
            steps:
              - "string step"
              - name: Review
                uses: actions/dependency-review-action@v4
        """,
    )
    result = lint_workflow(path)
    assert rules(result) == ["dependency-review-unguarded"]
    assert result.errors[0].line == 8
    assert "'dr'" in result.errors[0].message
    assert "'Review'" in result.errors[0].message


def test_dependency_review_with_wrong_guard_flagged(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          dr:
            runs-on: x
            steps:
              - uses: actions/dependency-review-action@v4
                if: github.ref == 'refs/heads/main'
        """,
    )
    assert rules(lint_workflow(path)) == ["dependency-review-unguarded"]


def test_dependency_review_with_pr_guard_allowed(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          dr:
            runs-on: x
            steps:
              - uses: actions/dependency-review-action@v4
                if: github.event_name == 'pull_request'
        """,
    )
    assert lint_workflow(path).errors == []


# --------------------------------------------------------------------------
# undeclared-input
# --------------------------------------------------------------------------


def test_undeclared_input_flagged_with_precise_line(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on:
          workflow_call:
            inputs:
              target_branches:
                type: string
        jobs:
          build:
            runs-on: x
            steps:
              - run: echo ${{ inputs.target_branches }}
              - run: echo ${{ inputs.target_branch }}
        """,
    )
    result = lint_workflow(path)
    assert rules(result) == ["undeclared-input"]
    err = result.errors[0]
    assert err.line == 11
    assert "inputs.target_branch'" in err.message
    assert "['target_branches']" in err.message


def test_workflow_dispatch_inputs_count_as_declared(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on:
          workflow_dispatch:
            inputs:
              target_branch:
                type: string
        jobs:
          build:
            runs-on: x
            steps:
              - run: echo ${{ github.event.inputs.target_branch }}
        """,
    )
    assert lint_workflow(path).errors == []


def test_no_declared_inputs_skips_check(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on:
          workflow_call:
            secrets: {}
          push:
        jobs:
          build:
            runs-on: x
            steps:
              - run: echo ${{ inputs.anything }}
        """,
    )
    assert lint_workflow(path).errors == []


def test_scalar_trigger_skips_input_check(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          build:
            runs-on: x
            steps:
              - run: echo ${{ inputs.anything }}
        """,
    )
    assert lint_workflow(path).errors == []


# --------------------------------------------------------------------------
# inconsistent-versions
# --------------------------------------------------------------------------


def test_inconsistent_pixi_versions_flagged(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          a:
            runs-on: x
            steps:
              # pixi-version: 9.9.9 (commented out, must be ignored)
              - uses: setup
                with:
                  pixi-version: v0.40.0
          b:
            runs-on: x
            steps:
              - uses: setup
                with:
                  pixi-version: v0.41.0
        """,
    )
    result = lint_workflow(path)
    assert rules(result) == ["inconsistent-versions"]
    assert result.errors[0].line == 9
    assert "v0.40.0" in result.errors[0].message
    assert "v0.41.0" in result.errors[0].message
    assert "9.9.9" not in result.errors[0].message


def test_consistent_or_single_pixi_version_allowed(tmp_path: Path) -> None:
    same = write(
        tmp_path,
        """
        on: push
        jobs:
          a:
            runs-on: x
            steps:
              - with: {pixi-version: v0.40.0}
              - with: {pixi-version: v0.40.0}
        """,
        "same.yml",
    )
    single = write(
        tmp_path,
        """
        on: push
        jobs:
          a:
            runs-on: x
            steps:
              - with: {pixi-version: v0.40.0}
        """,
        "single.yml",
    )
    assert lint_workflow(same).errors == []
    assert lint_workflow(single).errors == []


# --------------------------------------------------------------------------
# summary-missing-needs
# --------------------------------------------------------------------------


def test_summary_missing_needs_is_warning_listing_missing_jobs(
    tmp_path: Path,
) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          detect-changes:
            runs-on: x
            steps: []
          lint:
            runs-on: x
            steps: []
          test:
            runs-on: x
            steps: []
          summary:
            needs: lint
            runs-on: x
            steps: []
        """,
    )
    result = lint_workflow(path)
    assert rules(result) == ["summary-missing-needs"]
    err = result.errors[0]
    assert err.severity == "warning"
    assert err.line == 12
    assert "['test']" in err.message


def test_summary_with_complete_needs_allowed(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        on: push
        jobs:
          configure:
            runs-on: x
            steps: []
          lint:
            runs-on: x
            steps: []
          summary:
            needs: [lint]
            runs-on: x
            steps: []
        """,
    )
    assert lint_workflow(path).errors == []


def test_summary_check_without_summary_job_is_empty() -> None:
    assert check_summary_needs_completeness("f", [], {"jobs": {"a": {}}}) == []


# --------------------------------------------------------------------------
# gate_tasks
# --------------------------------------------------------------------------


def test_gate_tasks_follows_depends_on_and_delegation(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT)
    assert gate_tasks(pyproject) == frozenset(
        {"quality", "typecheck", "typecheck-impl", "lint"}
    )


def test_gate_tasks_empty_when_missing_file(tmp_path: Path) -> None:
    assert gate_tasks(tmp_path / "nope.toml") == frozenset()


def test_gate_tasks_empty_when_toml_invalid(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("this is = = not toml")
    assert gate_tasks(pyproject) == frozenset()


def test_gate_tasks_empty_without_root_task(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.pixi.tasks]\nother = "echo"\n')
    assert gate_tasks(pyproject) == frozenset()


def test_gate_tasks_empty_when_tasks_not_a_table(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.pixi]\ntasks = 3\n")
    assert gate_tasks(pyproject) == frozenset()


def test_gate_tasks_tolerates_odd_entries(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.pixi.tasks]\nquality = { depends-on = ["a", "missing", "b"] }\n'
        "a = 5\n"
        'b = { cmd = "pixi run quality" }\n'
    )
    # `missing` is undeclared so it is dropped; `a` (a non-str, non-table
    # entry) is recorded but contributes no edges; `b` delegates back to the
    # already-seen root without looping.
    assert gate_tasks(pyproject) == frozenset({"quality", "a", "b"})


# --------------------------------------------------------------------------
# swallowed-gate-exit
# --------------------------------------------------------------------------


@pytest.fixture
def gate_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    return tmp_path


def run_wf(run_body: str, extra: str = "") -> str:
    indented = textwrap.indent(textwrap.dedent(run_body).strip("\n"), " " * 10)
    return (
        "on: push\njobs:\n  build:\n    runs-on: x\n    steps:\n"
        f"      - name: Gate\n{extra}        run: |\n{indented}\n"
    )


@pytest.mark.parametrize(
    "line",
    [
        'pixi run -e quality typecheck || echo "ignored"',
        "pixi run typecheck || true",
        "pixi run typecheck ||true",
        "pixi run --environment quality typecheck || :",
        "pixi run typecheck ||:;",
    ],
)
def test_swallowed_gate_exit_flagged(gate_repo: Path, line: str) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(run_wf(line))
    result = lint_workflow(path)
    assert rules(result) == ["swallowed-gate-exit"]
    err = result.errors[0]
    assert err.line == 8
    assert "'typecheck'" in err.message
    assert "step 'Gate'" in err.message
    assert "job 'build'" in err.message.replace("Job", "job")


def test_swallow_on_continuation_line_is_caught(gate_repo: Path) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(run_wf("pixi run lint \\\n  || true"))
    result = lint_workflow(path)
    assert rules(result) == ["swallowed-gate-exit"]
    assert "'lint'" in result.errors[0].message
    assert "'|| true'" in result.errors[0].message


def test_each_gate_task_reported_once_per_step(gate_repo: Path) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(run_wf("pixi run typecheck || true\npixi run typecheck || true\n"))
    assert rules(lint_workflow(path)) == ["swallowed-gate-exit"]


def test_distinct_gate_tasks_each_reported(gate_repo: Path) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(run_wf("pixi run typecheck || true\npixi run lint || true\n"))
    errors = lint_workflow(path).errors
    assert sorted(e.line for e in errors) == [8, 9]
    joined = " ".join(e.message for e in errors)
    assert "gate task 'typecheck'" in joined
    assert "gate task 'lint'" in joined


@pytest.mark.parametrize(
    "line",
    [
        "pixi run typecheck",
        "pixi run unrelated || true",
        'echo "pixi run typecheck || true"',
        "pixi run typecheck  # || echo ignored",
        "true || pixi run typecheck",
        "pixi run typecheck || exit 1",
    ],
)
def test_non_swallowing_gate_usage_allowed(gate_repo: Path, line: str) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(run_wf(line))
    assert lint_workflow(path).errors == []


def test_non_run_and_non_dict_steps_ignored(gate_repo: Path) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(
        "on: push\njobs:\n  build:\n    runs-on: x\n    steps:\n"
        "      - plain string\n"
        "      - uses: some/action@v1\n"
        "      - run: [not, a, string]\n"
        "  other: nope\n"
    )
    assert lint_workflow(path).errors == []


def test_unnamed_step_reported_as_unnamed(gate_repo: Path) -> None:
    path = gate_repo / "wf.yml"
    path.write_text(
        "on: push\njobs:\n  build:\n    runs-on: x\n    steps:\n"
        "      - run: pixi run typecheck || true\n"
    )
    result = lint_workflow(path)
    assert rules(result) == ["swallowed-gate-exit"]
    assert "<unnamed>" in result.errors[0].message


def test_no_pyproject_means_no_gate_findings(tmp_path: Path, monkeypatch) -> None:
    # Stop the upward search from finding the real repo pyproject.toml.
    monkeypatch.setattr(workflow_lint, "_find_pyproject", lambda _p: None)
    path = tmp_path / "wf.yml"
    path.write_text(run_wf("pixi run typecheck || true"))
    assert lint_workflow(path).errors == []


def test_pyproject_without_gate_root_means_no_findings(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.pixi.tasks]\nx = "echo"\n')
    path = tmp_path / "wf.yml"
    path.write_text(run_wf("pixi run typecheck || true"))
    assert lint_workflow(path).errors == []


def test_find_pyproject_walks_parents(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    nested = tmp_path / ".github" / "workflows"
    nested.mkdir(parents=True)
    assert (
        workflow_lint._find_pyproject(nested) == (tmp_path / "pyproject.toml").resolve()
    )


# --------------------------------------------------------------------------
# line-number helpers
# --------------------------------------------------------------------------


def test_find_line_number_helpers() -> None:
    lines = ["a", "b needle", "c", "needle again"]
    assert workflow_lint._find_line_number(lines, "needle") == 2
    assert workflow_lint._find_line_number(lines, "needle", start=2) == 4
    assert workflow_lint._find_line_number(lines, "absent") == 0
    assert workflow_lint._find_line_number_re(lines, r"^c$") == 3
    assert workflow_lint._find_line_number_re(lines, r"^c$", start=3) == 0


# --------------------------------------------------------------------------
# discovery and directory linting
# --------------------------------------------------------------------------


def test_discover_workflow_files_both_suffixes_sorted(tmp_path: Path) -> None:
    (tmp_path / "b.yml").write_text("x: 1\n")
    (tmp_path / "a.yaml").write_text("x: 1\n")
    (tmp_path / "c.txt").write_text("x: 1\n")
    found = discover_workflow_files(tmp_path)
    assert [p.name for p in found] == ["a.yaml", "b.yml"]


def test_discover_workflow_files_missing_dir_is_empty(tmp_path: Path) -> None:
    assert discover_workflow_files(tmp_path / "missing") == []


def test_lint_all_workflows_combines_findings(tmp_path: Path) -> None:
    bad = """
    on: push
    jobs:
      j:
        if: ${{ true }}
        runs-on: x
        steps: []
    """
    write(tmp_path, bad, "one.yml")
    write(tmp_path, bad, "two.yaml")
    write(tmp_path, "on: push\njobs: {}\n", "ok.yml")
    result = lint_all_workflows(tmp_path)
    assert rules(result) == ["double-expression-wrap"] * 2
    assert sorted(Path(e.file).name for e in result.errors) == [
        "one.yml",
        "two.yaml",
    ]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

BAD_ERROR = """
on: push
jobs:
  j:
    if: ${{ true }}
    runs-on: x
    steps: []
"""

WARN_ONLY = """
on: push
jobs:
  j:
    runs-on: x
    steps:
      - uses: actions/checkout@v4
        with:
          repository: other/repo
"""


def run_main(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["workflow_lint", *args])
    return main()


def test_main_clean_file_exits_zero_silently(tmp_path, monkeypatch, capsys) -> None:
    path = write(tmp_path, "on: push\njobs: {}\n")
    assert run_main(monkeypatch, str(path)) == 0
    assert capsys.readouterr().out == ""


def test_main_error_exits_one_and_prints_summary(tmp_path, monkeypatch, capsys) -> None:
    path = write(tmp_path, BAD_ERROR)
    assert run_main(monkeypatch, str(path)) == 1
    out = capsys.readouterr().out
    assert "[error] double-expression-wrap" in out
    assert "1 error(s), 0 warning(s)" in out


def test_main_warning_only_exits_zero_unless_strict(
    tmp_path, monkeypatch, capsys
) -> None:
    path = write(tmp_path, WARN_ONLY)
    assert run_main(monkeypatch, str(path)) == 0
    out = capsys.readouterr().out
    assert "[warning] cross-repo-checkout" in out
    assert "0 errors, 1 warning(s)" in out

    assert run_main(monkeypatch, "--strict", str(path)) == 1
    assert "0 error(s), 1 warning(s)" in capsys.readouterr().out


def test_main_without_files_lints_default_directory(
    tmp_path, monkeypatch, capsys
) -> None:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    write(wf_dir, BAD_ERROR, "bad.yml")
    monkeypatch.chdir(tmp_path)
    assert run_main(monkeypatch) == 1
    assert "bad.yml" in capsys.readouterr().out


def test_main_without_files_and_clean_directory_passes(tmp_path, monkeypatch) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert run_main(monkeypatch) == 0
