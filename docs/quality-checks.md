# Quality Checks Reusable Workflow

> **Multi-language code quality, linting, formatting, and type checking**

## Overview

The Quality Checks workflow automatically detects your repository's languages and runs appropriate linting, formatting, and type-checking tools. It provides consistent code quality standards across Python, Rust, C/C++, Cython, and JavaScript/TypeScript projects.

By default, the workflow **blocks on lint and format violations** but only **warns on type-checking errors** (since type checkers can be strict). For consumers using this as a reusable workflow, quality tools are managed via pixi (if your project uses pixi); standalone installations use pip.

## Quick Start

Add to your consumer repository's workflow:

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    permissions:
      contents: read
```

**Required permissions:**
- `contents: read` — Read source code to analyze

All inputs are optional. The workflow will auto-detect your languages and use sensible defaults.

## All Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `languages` | string | `` (empty) | Comma-separated languages to check. If empty, auto-detects from: `python` (pyproject.toml/setup.py), `rust` (Cargo.toml), `c_cpp` (CMakeLists.txt/C/C++ source files), `cython` (.pyx/.pxd files), `js_ts` (package.json). Example: `python,rust` |
| `fail-on-lint` | boolean | `true` | Fail the workflow on lint violations. Set to `false` to warn only. |
| `fail-on-format` | boolean | `true` | Fail the workflow on format violations. Set to `false` to warn only. |
| `fail-on-typecheck` | boolean | `false` | Fail the workflow on type-checking errors. Default warns only. Set to `true` to enforce type safety. |
| `python-version` | string | `'3.12'` | Python version to use for linting and type-checking tools. |

## Quality Tools by Language

### Python
- **Ruff** (lint) — Fast linter for style, naming, complexity, and security anti-patterns
- **Ruff** (format) — Auto-formatting for consistent code style
- **mypy** — Static type checker for Python

### Rust
- **clippy** — Linter for idiomatic Rust and performance improvements
- **rustfmt** — Auto-formatter for Rust code style

### C/C++
- **clang-tidy** — Linter for C/C++ with LLVM analysis
- **cppcheck** — Static analyzer for C/C++ code issues

### Cython
- **cython-lint** — Linter specifically for Cython (.pyx/.pxd) files

### JavaScript/TypeScript
- **ESLint** — Linter for JavaScript and TypeScript

## Default Behavior

| Check Type | Default Action | Configurable |
|-----------|----------------|--------------|
| Lint (style, complexity) | **BLOCK** — fails workflow | `fail-on-lint` |
| Format (whitespace, indentation) | **BLOCK** — fails workflow | `fail-on-format` |
| Type checking | **WARN** — annotates PR only | `fail-on-typecheck` |

## Python Quality with Pixi vs Standalone

### When Using `reusable-ci.yml` (Pixi Environment)

If you use this workflow as part of `reusable-ci.yml`, quality tools are automatically installed in the pixi environment specified by `pixi-environment`. The workflow reuses the dependency lock from `pixi.lock`.

```yaml
jobs:
  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    with:
      pixi-environment: 'ci'
    secrets: inherit
```

Quality tools (ruff, mypy) are pre-installed in the pixi `ci` environment.

### Standalone Usage (Direct Invocation)

If you invoke `reusable-quality.yml` directly without `reusable-ci.yml`, the workflow installs quality tools via pip:

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
```

This is sufficient for basic quality checks but doesn't have access to your project's full dependency tree.

## Example Configurations

### Minimal: Auto-detect with defaults (recommended)

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    permissions:
      contents: read
```

Detects languages, blocks on lint/format, warns on types.

### Strict: Enforce type safety

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    with:
      fail-on-typecheck: true
    permissions:
      contents: read
```

Blocks on any type-checking errors. Recommended for production code.

### Explicit languages: Python only

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    with:
      languages: 'python'
    permissions:
      contents: read
```

Skips Rust, C/C++, Cython, and JavaScript checks.

### Warning-only: Development branch

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    with:
      fail-on-lint: false
      fail-on-format: false
      fail-on-typecheck: false
    permissions:
      contents: read
```

All findings appear as workflow annotations only; none block merge.

### Custom Python version: Python 3.10

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    with:
      python-version: '3.10'
    permissions:
      contents: read
```

Uses Python 3.10 for ruff and mypy instead of default 3.12.

## How Annotations Appear

Quality findings appear in the workflow run as annotations:

```
F821 Undefined name 'x'
  File: src/utils.py:42
  ruff: F821

E501 Line too long (88 > 79 characters)
  File: src/main.py:156
  ruff: E501
```

GitHub also displays these inline in PR diffs when the violation affects a changed line.

## Language Detection

The workflow auto-detects languages by checking for:

| Language | Detection | Override |
|----------|-----------|----------|
| Python | `pyproject.toml` or `setup.py` present | `languages: 'python'` |
| Rust | `Cargo.toml` present | `languages: 'rust'` |
| C/C++ | `CMakeLists.txt` or `.c`/`.cpp`/`.h` files | `languages: 'c_cpp'` |
| Cython | `.pyx` or `.pxd` files | `languages: 'cython'` |
| JavaScript/TypeScript | `package.json` present | `languages: 'js_ts'` |

## Integration with Security & Testing

Combine with other workflows for comprehensive CI:

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    permissions:
      contents: read

  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write

  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    secrets: inherit
```

All run independently and report their findings together in the PR.

## Troubleshooting

### "No matching language detected"

If the workflow skips all quality checks:
- Verify your project has the expected configuration files: `pyproject.toml`, `Cargo.toml`, `package.json`, etc.
- Use `languages: 'python'` to manually specify languages

### "Too many lint findings"

Start with warning-only mode to see all findings:

```yaml
with:
  fail-on-lint: false
```

Then address violations incrementally. Once cleared, enable `fail-on-lint: true`.

### "Type checking is too strict"

mypy can be overly conservative. Options:

1. Use `fail-on-typecheck: false` (default) — warnings only
2. Add type: ignore comments to specific violations
3. Configure mypy in `pyproject.toml`:
   ```toml
   [tool.mypy]
   ignore_missing_imports = true
   ```

### "Format and lint are conflicting"

Ruff lint and ruff format should not conflict. If they do:
- Run `ruff format .` locally to auto-fix formatting
- Commit the changes
- The lint check should then pass

### "Python version mismatch"

If you see type-checking errors related to Python version:
- Ensure `python-version` input matches your project's minimum supported version
- Example: if your project supports Python 3.10+, use `python-version: '3.10'`

---

**Workflow Version**: 1.0
**Last Updated**: April 2026
**Compatibility**: GitHub Actions, Python 3.10+, Rust 1.70+, Node.js 18+, C++17
