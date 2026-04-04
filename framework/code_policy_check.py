"""Code policy checker — file size and complexity enforcement.

Checks Python files against configurable thresholds for:
- File line count (Atomic Design Hierarchy levels)
- Function/method cyclomatic complexity (via radon)
- Function/method line count (via ast)

Outputs GitHub Actions annotations and a markdown summary report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
