"""Custom workflow linter for GitHub Actions anti-patterns.

Catches issues that actionlint misses:
- Double ${{ }} wrapping in job-level if: conditions
- Cross-repo checkout steps without error handling
- Undeclared workflow_call inputs referenced in jobs
- Hardcoded versions that should be parameterized
- dependency-review-action without event guard
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LintError:
    file: str
    line: int
    rule: str
    message: str
    severity: str = "error"

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.severity}] {self.rule}: {self.message}"


@dataclass
class LintResult:
    errors: list[LintError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(e.severity == "error" for e in self.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "warning")


def _find_line_number(raw_lines: list[str], pattern: str, start: int = 0) -> int:
    """Find line number (1-indexed) containing pattern."""
    for i, line in enumerate(raw_lines[start:], start=start):
        if pattern in line:
            return i + 1
    return 0


def _find_line_number_re(
    raw_lines: list[str], regex: str, start: int = 0
) -> int:
    """Find line number (1-indexed) matching regex."""
    compiled = re.compile(regex)
    for i, line in enumerate(raw_lines[start:], start=start):
        if compiled.search(line):
            return i + 1
    return 0


def check_double_expression_wrap(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Detect double ${{ }} wrapping in job-level if: conditions.

    Job-level if: already implicitly wraps in ${{ }}, so explicit wrapping
    causes the expression to be evaluated as a string literal first, producing
    unexpected behavior or startup_failure.
    """
    errors = []
    jobs = workflow.get("jobs", {})
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        job_if = job_config.get("if")
        if job_if and isinstance(job_if, str):
            # Check for explicit ${{ }} in job-level if
            if "${{" in job_if and "}}" in job_if:
                line = _find_line_number(raw_lines, "if:")
                # Search more precisely near the job definition
                job_line = _find_line_number(raw_lines, f"  {job_name}:")
                if job_line:
                    line = _find_line_number(raw_lines, "if:", start=job_line - 1)
                errors.append(
                    LintError(
                        file=filepath,
                        line=line,
                        rule="double-expression-wrap",
                        message=(
                            f"Job '{job_name}' has explicit ${{{{ }}}} in if: condition. "
                            "Job-level if: already implicitly wraps expressions. "
                            "This can cause startup_failure."
                        ),
                    )
                )
    return errors


def check_cross_repo_checkout(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Detect cross-repo checkout steps that add fragile external dependencies.

    In reusable workflows called remotely, cross-repo checkouts add failure
    modes: permission issues, network failures, missing paths. Prefer
    self-contained steps using pixi/pip.
    """
    errors = []
    jobs = workflow.get("jobs", {})
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        steps = job_config.get("steps", [])
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            with_config = step.get("with", {})
            if "actions/checkout" in uses and isinstance(with_config, dict):
                repo = with_config.get("repository", "")
                if repo and repo != "${{ github.repository }}":
                    step_name = step.get("name", uses)
                    line = _find_line_number(raw_lines, f"repository: {repo}")
                    errors.append(
                        LintError(
                            file=filepath,
                            line=line,
                            rule="cross-repo-checkout",
                            message=(
                                f"Job '{job_name}' checks out external repo '{repo}' "
                                f"in step '{step_name}'. This adds a fragile runtime "
                                "dependency. Prefer self-contained pixi/pip commands."
                            ),
                            severity="warning",
                        )
                    )
    return errors


def check_dependency_review_guard(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Detect dependency-review-action without pull_request event guard.

    dependency-review-action only works on pull_request, pull_request_target,
    or merge_group events. Running it on push causes failures.
    """
    errors = []
    jobs = workflow.get("jobs", {})
    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        steps = job_config.get("steps", [])
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            if "dependency-review-action" in uses:
                step_if = step.get("if", "")
                if not step_if or "pull_request" not in str(step_if):
                    step_name = step.get("name", uses)
                    line = _find_line_number(
                        raw_lines, "dependency-review-action"
                    )
                    errors.append(
                        LintError(
                            file=filepath,
                            line=line,
                            rule="dependency-review-unguarded",
                            message=(
                                f"Job '{job_name}' uses dependency-review-action "
                                f"in step '{step_name}' without a pull_request event "
                                "guard. This action only works on PR events and will "
                                "fail on push."
                            ),
                        )
                    )
    return errors


def check_undeclared_inputs(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Detect references to undeclared workflow_call inputs."""
    errors = []
    trigger = workflow.get("on", workflow.get(True, {}))
    if not isinstance(trigger, dict):
        return errors

    workflow_call = trigger.get("workflow_call", {})
    if not workflow_call:
        return errors

    declared_inputs = set()
    inputs_config = workflow_call.get("inputs", {})
    if isinstance(inputs_config, dict):
        declared_inputs = set(inputs_config.keys())

    # Find all inputs.* references in the raw text
    input_refs = re.findall(r"inputs\.([a-zA-Z0-9_-]+)", "\n".join(raw_lines))
    for ref in set(input_refs):
        if ref not in declared_inputs:
            line = _find_line_number(raw_lines, f"inputs.{ref}")
            errors.append(
                LintError(
                    file=filepath,
                    line=line,
                    rule="undeclared-input",
                    message=(
                        f"Reference to undeclared input 'inputs.{ref}'. "
                        f"Declared inputs: {sorted(declared_inputs)}"
                    ),
                )
            )

    return errors


def check_hardcoded_versions(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Detect hardcoded pixi versions that should use a single source of truth."""
    errors = []
    # Count pixi-version occurrences
    version_lines = []
    for i, line in enumerate(raw_lines):
        if "pixi-version:" in line and "#" not in line.split("pixi-version:")[0]:
            version_lines.append((i + 1, line.strip()))

    if len(version_lines) > 1:
        versions = set()
        for _, line in version_lines:
            match = re.search(r"pixi-version:\s*(\S+)", line)
            if match:
                versions.add(match.group(1))

        if len(versions) > 1:
            errors.append(
                LintError(
                    file=filepath,
                    line=version_lines[0][0],
                    rule="inconsistent-versions",
                    message=(
                        f"Multiple pixi versions found: {versions}. "
                        "Use a single source of truth (env var or input)."
                    ),
                )
            )

    return errors


def check_summary_needs_completeness(
    filepath: str, raw_lines: list[str], workflow: dict
) -> list[LintError]:
    """Check that the summary job's needs: lists all other jobs."""
    errors = []
    jobs = workflow.get("jobs", {})
    if "summary" not in jobs:
        return errors

    summary_job = jobs["summary"]
    summary_needs = summary_job.get("needs", [])
    if isinstance(summary_needs, str):
        summary_needs = [summary_needs]

    # Exclude upstream-only jobs that are transitively covered
    upstream_only = {"detect-changes", "configure"}
    all_jobs = set(jobs.keys()) - {"summary"} - upstream_only
    missing = all_jobs - set(summary_needs)

    if missing:
        line = _find_line_number(raw_lines, "summary:")
        errors.append(
            LintError(
                file=filepath,
                line=line,
                rule="summary-missing-needs",
                message=(
                    f"Summary job is missing these jobs in needs: {sorted(missing)}. "
                    "It won't wait for them to complete."
                ),
                severity="warning",
            )
        )

    return errors


ALL_CHECKS = [
    check_double_expression_wrap,
    check_cross_repo_checkout,
    check_dependency_review_guard,
    check_undeclared_inputs,
    check_hardcoded_versions,
    check_summary_needs_completeness,
]


def lint_workflow(filepath: str | Path) -> LintResult:
    """Run all lint checks on a workflow file."""
    filepath = Path(filepath)
    result = LintResult()

    raw_text = filepath.read_text()
    raw_lines = raw_text.splitlines()

    try:
        workflow = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        result.errors.append(
            LintError(
                file=str(filepath),
                line=0,
                rule="yaml-parse-error",
                message=f"Failed to parse YAML: {e}",
            )
        )
        return result

    if not isinstance(workflow, dict):
        return result

    for check in ALL_CHECKS:
        result.errors.extend(check(str(filepath), raw_lines, workflow))

    return result


def lint_all_workflows(workflow_dir: str | Path = ".github/workflows") -> LintResult:
    """Run all lint checks on all workflow files in a directory."""
    workflow_dir = Path(workflow_dir)
    combined = LintResult()

    for yml_file in sorted(workflow_dir.glob("*.yml")):
        file_result = lint_workflow(yml_file)
        combined.errors.extend(file_result.errors)

    return combined


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Custom GitHub Actions workflow linter")
    parser.add_argument(
        "files",
        nargs="*",
        default=[],
        help="Workflow files to lint (default: all in .github/workflows/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    if args.files:
        result = LintResult()
        for f in args.files:
            file_result = lint_workflow(f)
            result.errors.extend(file_result.errors)
    else:
        result = lint_all_workflows()

    for error in result.errors:
        print(error)

    errors = result.error_count
    warnings = result.warning_count

    if args.strict:
        total = errors + warnings
    else:
        total = errors

    if total > 0:
        print(f"\n{errors} error(s), {warnings} warning(s)")
        return 1
    elif warnings > 0:
        print(f"\n0 errors, {warnings} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
