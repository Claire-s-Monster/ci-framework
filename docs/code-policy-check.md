# Code Policy Check Reusable Workflow

> **Enforce structural code quality standards with configurable file size, complexity, and function length thresholds**

## Overview

The Code Policy Check workflow validates Python code against structural policy thresholds (file size, cyclomatic complexity, function length) and reports violations as inline PR annotations. It helps teams maintain code maintainability by preventing files from growing beyond reasonable limits and functions from becoming overly complex.

The workflow uses **configurable thresholds aligned with the Atomic Design Hierarchy** (Organism maximum: 500 lines), checks only PR-changed files by default to avoid legacy code noise, and runs in warning-only mode for non-breaking adoption.

## Quick Start

Add to your consumer repository's workflow:

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
```

All inputs are optional. The workflow will use default thresholds and check only changed files in pull requests.

## All Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `check-mode` | string | `'pr'` | Scope: `'pr'` (changed files in PR) or `'all'` (full repository) |
| `file-patterns` | string | `'**/*.py'` | Glob patterns for files to check (comma-separated) |
| `exclude-patterns` | string | `'**/tests/**,**/test_*'` | Patterns to exclude from checks (comma-separated) |
| `package-path` | string | `'.'` | Relative path to package directory (for monorepos) |
| `max-file-lines` | number | `500` | Maximum lines per file |
| `max-cyclomatic-complexity` | number | `10` | Maximum cyclomatic complexity per function |
| `max-function-lines` | number | `50` | Maximum lines per function/method |
| `fail-on-violation` | boolean | `false` | Fail workflow on violations (true) or warning-only (false) |

## Example Configurations

### Minimal: PR-only warnings (recommended starting point)

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
```

Uses all defaults: checks only changed Python files in PRs, warns on violations without failing.

### Strict Mode: Fail on violations

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
    with:
      fail-on-violation: true
```

Same thresholds but fails the workflow if any violations are found.

### Custom Thresholds: Enforce smaller boundaries

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
    with:
      max-file-lines: 300
      max-cyclomatic-complexity: 5
      max-function-lines: 30
      fail-on-violation: true
```

Tighter limits enforce higher modularity. Typical for teams prioritizing code readability.

### Full Repository Scan

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
    with:
      check-mode: 'all'
      fail-on-violation: false
```

Runs on the entire repository once per PR (slow for large codebases; use `check-mode: pr` for most PRs).

### Custom File Selection

```yaml
jobs:
  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
    with:
      file-patterns: 'src/**/*.py'
      exclude-patterns: 'src/legacy/**,**/migrations/**'
      max-file-lines: 400
```

Restrict to `src/`, exclude legacy and migration code, with slightly relaxed file size limit.

## How Annotations Appear

When violations are found, the workflow emits **GitHub Actions annotations** — inline comments on the PR diff and a summary in the workflow run.

### Inline Annotations

Each violation appears directly on the affected line in the PR:

```
⚠️  Code Policy  (line 1042)
File has 4041 lines — exceeds Organism maximum of 500
```

Annotations are visible in:
- **PR Files Changed tab**: Pinned comments next to the violation location
- **Workflow run summary**: List of all violations

### Summary Report

A markdown table aggregates violations by file:

```
## Code Policy Report

| File | Lines | Max Lines | Worst CC | Max CC | Violations |
|------|-------|-----------|----------|--------|------------|
| src/api.py | 4041 | 500 | 23 | 10 | file-too-long, high-complexity |
| src/utils.py | 142 | 500 | 4 | 10 | — |

3 violations in 1 file (2 files checked)
```

## Adoption Path

For repositories with existing large files:

1. **Start with defaults and `check-mode: pr`** (warnings only)
   - Developers see annotations only when editing oversized files
   - No impact on legacy untouched code

2. **Ignore pre-existing violations during initial rollout**
   - The check flags existing violations when a file is touched — this is intentional
   - It surfaces the issue at a natural refactoring moment

3. **Gradually tighten thresholds and decompose files**
   - As files are refactored, lower the thresholds in the workflow
   - Example: Start with `max-file-lines: 1000`, drop to `500` after quarterly reviews

4. **Enable `fail-on-violation: true` when ready**
   - Once most violations are resolved, enable hard enforcement
   - New violations will block merge until decomposed

## Atomic Design Hierarchy Reference

The Code Policy Check uses thresholds aligned with the **Atomic Design Hierarchy for Python code**:

| Level | Max File Lines | Max Function Lines | Max CC | Purpose |
|-------|----------------|--------------------|--------|---------|
| **Atom** | 150 | 20 | 3 | Single responsibility, minimal utility functions |
| **Molecule** | 300 | 40 | 5 | Small coordinated modules |
| **Organism** | 500 | 50 | 10 | Feature domains, stable interfaces |
| **Template** | 1000+ | 80+ | 15+ | Complex workflows (use sparingly) |
| **Page** | Unlimited | Unlimited | Unlimited | Entry points, orchestration |

**Default thresholds are Organism-level**: Suitable for most production code. Tighten for higher standards, relax for legacy code or integration layers.

## Integration with Quality Gates

The Code Policy Check complements the framework's other quality tools:

- **Quality Gates** (ruff, mypy): Catch style, types, and obvious bugs
- **Code Policy Check** (file size, complexity): Catch architectural issues
- **Change Detection**: Trigger policies on relevant file modifications

Combine in your workflow:

```yaml
jobs:
  quality-gates:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    secrets: inherit

  code-policy:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-code-policy.yml@main
```

Both run independently, reporting their findings together in the PR.

## Troubleshooting

### No violations found but expected to find some

Verify:
- `check-mode: 'pr'` only checks changed files. Use `check-mode: 'all'` for full repo.
- `exclude-patterns` may be filtering out the files you expect. Check glob patterns carefully.
- `file-patterns` defaults to `**/*.py`. Adjust if checking non-Python files.

### Annotations not showing on PR

- Annotations require the workflow to run and complete. Check the Actions tab for errors.
- Annotations only appear for files changed in the PR (when `check-mode: 'pr'`).
- Pre-existing violations in unchanged files are not annotated.

### Too many violations reported at once

- Use `check-mode: 'pr'` to focus on changed files only.
- Start with `fail-on-violation: false` to see violations in warning mode.
- Use higher thresholds initially (`max-file-lines: 1000`), then tighten over time.

### Monorepo issues

- Use `package-path` to scope checks to a specific package directory.
- Adjust `file-patterns` and `exclude-patterns` as needed per subdirectory.

---

**Workflow Version**: 1.0
**Last Updated**: April 2026
**Compatibility**: GitHub Actions, Python 3.10+
