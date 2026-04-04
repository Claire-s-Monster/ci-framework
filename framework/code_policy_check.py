"""Code policy checker — file size and complexity enforcement.

Checks Python files against configurable thresholds for:
- File line count (Atomic Design Hierarchy levels)
- Function/method cyclomatic complexity (via radon)
- Function/method line count (via ast)

Outputs GitHub Actions annotations and a markdown summary report.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str
    severity: str
    current_value: int
    threshold: int


@dataclass
class PolicyResult:
    violations: list[Violation]
    files_checked: int
    files_clean: int

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


# --- Atomic Design level names for violation messages ---
_AG_LEVELS = [
    (150, "Atom"),
    (300, "Molecule"),
    (500, "Organism"),
]


def _ag_level_name(max_lines: int) -> str:
    """Return the Atomic Design level name for a given max line threshold."""
    for limit, name in _AG_LEVELS:
        if max_lines <= limit:
            return name
    return "file"  # generic label for custom thresholds above 500


def check_file_length(path: Path, max_lines: int) -> list[Violation]:
    """Check file line count against threshold.

    Counts all physical lines excluding blank lines and lines where the
    first non-whitespace character is '#'. Docstrings are counted.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    countable = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        countable += 1

    if countable > max_lines:
        level = _ag_level_name(max_lines)
        return [
            Violation(
                file=str(path),
                line=1,
                rule="file-too-long",
                message=(
                    f"File has {countable} lines — "
                    f"exceeds {level} maximum of {max_lines}"
                ),
                severity="warning",
                current_value=countable,
                threshold=max_lines,
            )
        ]
    return []


def check_cyclomatic_complexity(path: Path, max_cc: int) -> list[Violation]:
    """Check per-function cyclomatic complexity using radon."""
    from radon.complexity import cc_visit

    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        blocks = cc_visit(source)
    except SyntaxError:
        return []

    violations = []
    for block in blocks:
        if block.complexity > max_cc:
            violations.append(
                Violation(
                    file=str(path),
                    line=block.lineno,
                    rule="high-complexity",
                    message=(
                        f"Function `{block.name}` has cyclomatic complexity "
                        f"{block.complexity}, max allowed {max_cc}"
                    ),
                    severity="warning",
                    current_value=block.complexity,
                    threshold=max_cc,
                )
            )
    return violations


@dataclass
class FileMetrics:
    """Aggregated metrics for a single file."""
    file: str
    line_count: int = 0
    max_lines_threshold: int = 0
    worst_cc: int = 0
    max_cc_threshold: int = 0
    worst_func_len: int = 0
    max_func_len_threshold: int = 0
    violations: list[str] = field(default_factory=list)


def aggregate_by_file(
    violations: list[Violation],
) -> dict[str, FileMetrics]:
    """Group violations by file, collecting worst value per metric."""
    files: dict[str, FileMetrics] = {}
    for v in violations:
        if v.file not in files:
            files[v.file] = FileMetrics(file=v.file)
        fm = files[v.file]
        fm.violations.append(v.rule)
        if v.rule == "file-too-long":
            fm.line_count = max(fm.line_count, v.current_value)
            fm.max_lines_threshold = v.threshold
        elif v.rule == "high-complexity":
            fm.worst_cc = max(fm.worst_cc, v.current_value)
            fm.max_cc_threshold = v.threshold
        elif v.rule == "function-too-long":
            fm.worst_func_len = max(fm.worst_func_len, v.current_value)
            fm.max_func_len_threshold = v.threshold
    return files


def format_annotations(result: PolicyResult) -> str:
    """Format violations as GitHub Actions annotation commands."""
    lines = []
    for v in result.violations:
        lines.append(
            f"::warning file={v.file},line={v.line},"
            f"title=Code Policy::{v.message}"
        )
    return "\n".join(lines)


def format_summary(result: PolicyResult) -> str:
    """Format violations as a markdown summary table."""
    lines = ["## Code Policy Report", ""]

    if not result.has_violations:
        lines.append(
            f"No violations found ({result.files_checked} files checked)"
        )
        return "\n".join(lines)

    lines.append(
        "| File | Lines | Max Lines | Worst CC | Max CC "
        "| Longest Fn | Max Fn | Violations |"
    )
    lines.append(
        "|------|-------|-----------|----------|--------"
        "|------------|--------|------------|"
    )

    file_metrics = aggregate_by_file(result.violations)
    for fm in file_metrics.values():
        rules = ", ".join(sorted(set(fm.violations))) or "\u2014"
        lines.append(
            f"| {fm.file} | {fm.line_count} | {fm.max_lines_threshold} "
            f"| {fm.worst_cc} | {fm.max_cc_threshold} "
            f"| {fm.worst_func_len} | {fm.max_func_len_threshold} | {rules} |"
        )

    violation_files = len(file_metrics)
    total_violations = len(result.violations)
    file_word = "file" if violation_files == 1 else "files"
    lines.append("")
    lines.append(
        f"**{total_violations} violations in {violation_files} {file_word}** "
        f"({result.files_checked} files checked)"
    )

    return "\n".join(lines)


def check_function_length(path: Path, max_lines: int) -> list[Violation]:
    """Check per-function line count using AST parsing."""
    import ast

    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue
            start = node.body[0].lineno
            end = node.end_lineno or node.body[-1].lineno
            length = end - start + 1
            if length > max_lines:
                violations.append(
                    Violation(
                        file=str(path),
                        line=node.lineno,
                        rule="function-too-long",
                        message=(
                            f"Function `{node.name}` has {length} lines, "
                            f"max allowed {max_lines}"
                        ),
                        severity="warning",
                        current_value=length,
                        threshold=max_lines,
                    )
                )
    return violations


def _filter_files(
    files: list[str], exclude_patterns: list[str],
) -> list[str]:
    """Filter file list by exclude patterns using fnmatch."""
    if not exclude_patterns:
        return files
    result = []
    for f in files:
        if not any(fnmatch(f, pat) for pat in exclude_patterns):
            result.append(f)
    return result


def run_checks(
    files: list[str],
    exclude_patterns: list[str],
    max_file_lines: int,
    max_cc: int,
    max_function_lines: int,
) -> PolicyResult:
    """Run all policy checks on the given files."""
    filtered = _filter_files(files, exclude_patterns)
    all_violations: list[Violation] = []
    files_clean = 0

    for file_path in filtered:
        path = Path(file_path)
        if not path.exists():
            continue
        file_violations: list[Violation] = []
        file_violations.extend(check_file_length(path, max_file_lines))
        file_violations.extend(check_cyclomatic_complexity(path, max_cc))
        file_violations.extend(check_function_length(path, max_function_lines))
        if file_violations:
            all_violations.extend(file_violations)
        else:
            files_clean += 1

    return PolicyResult(
        violations=all_violations,
        files_checked=len(filtered),
        files_clean=files_clean,
    )


def main() -> int:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check Python files against code policy thresholds"
    )
    files_group = parser.add_mutually_exclusive_group(required=True)
    files_group.add_argument(
        "--files",
        help="JSON array of file paths to check",
    )
    files_group.add_argument(
        "--files-from",
        help="Path to a file containing a JSON array of file paths",
    )
    parser.add_argument(
        "--exclude-patterns", default="",
        help="Comma-separated glob patterns to exclude",
    )
    parser.add_argument(
        "--max-file-lines", type=int, default=500,
        help="Maximum lines per file (default: 500)",
    )
    parser.add_argument(
        "--max-cyclomatic-complexity", type=int, default=10,
        help="Maximum cyclomatic complexity per function (default: 10)",
    )
    parser.add_argument(
        "--max-function-lines", type=int, default=50,
        help="Maximum lines per function (default: 50)",
    )
    parser.add_argument(
        "--output-format", choices=["annotations", "json"],
        default="annotations",
        help="Output format (default: annotations)",
    )
    parser.add_argument(
        "--github-output", default=None,
        help="Path to $GITHUB_OUTPUT file for writing violation count",
    )
    args = parser.parse_args()

    if args.files_from:
        files = json.loads(Path(args.files_from).read_text())
    else:
        files = json.loads(args.files)
    exclude = [p.strip() for p in args.exclude_patterns.split(",") if p.strip()]

    result = run_checks(
        files=files,
        exclude_patterns=exclude,
        max_file_lines=args.max_file_lines,
        max_cc=args.max_cyclomatic_complexity,
        max_function_lines=args.max_function_lines,
    )

    if args.output_format == "annotations":
        annotations = format_annotations(result)
        if annotations:
            print(annotations)
    else:
        print(json.dumps([
            {"file": v.file, "line": v.line, "rule": v.rule,
             "message": v.message, "current_value": v.current_value,
             "threshold": v.threshold}
            for v in result.violations
        ], indent=2))

    # Write markdown summary
    summary = format_summary(result)
    Path("policy-report.md").write_text(summary)

    # Write violation count to $GITHUB_OUTPUT if specified
    if args.github_output:
        with open(args.github_output, "a") as f:
            f.write(f"violations={len(result.violations)}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
