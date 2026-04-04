"""Code policy checker — file size and complexity enforcement.

Checks Python files against configurable thresholds for:
- File line count (Atomic Design Hierarchy levels)
- Function/method cyclomatic complexity (via radon)
- Function/method line count (via ast)

Outputs GitHub Actions annotations and a markdown summary report.
"""

from __future__ import annotations

from dataclasses import dataclass
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
