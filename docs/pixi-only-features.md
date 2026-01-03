# Pixi-Only CI Framework Features

This document describes the pixi-first features in the CI Framework that enforce pixi-based project requirements.

## Overview

The CI Framework is designed exclusively for pixi-based Python projects. These features ensure:

1. **Pixi Project Validation** - Fail fast if pixi.toml/pixi.lock not found
2. **Editable Package Install** - Auto-install packages in editable mode within pixi
3. **Repository Hygiene Checks** - Prevent dev artifacts from being committed
4. **Expanded Security Triggers** - Detect dependency changes for security scans

All features are **enabled by default** and enforce pixi-only workflows.

---

## Feature 1: Editable Package Install

### Problem

For pixi-based projects, the local package is not automatically installed in the environment. Tests that import the package fail with `ModuleNotFoundError`.

### Solution

The CI framework automatically runs `pip install -e . --no-deps` within the pixi environment before tests.

**Key behaviors:**
- Fails if no `pixi.toml` or `pixi.lock` found (pixi-only enforcement)
- Uses `--no-deps` to prevent conflicts with pixi-managed dependencies
- Runs within the pixi environment context

### Configuration

```yaml
jobs:
  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    with:
      editable-install: true  # default: true
```

To disable (not recommended):
```yaml
    with:
      editable-install: false
```

---

## Feature 2: Repository Hygiene Checks

### Problem

Development artifacts like `__pycache__`, `.pyc` files, and cache directories can accidentally be committed to git, bloating the repository and causing issues.

### Solution

The `hygiene` job validates:

**Errors (fail the build):**
- `__pycache__` directories tracked in git
- `.pyc` files tracked in git
- `.pytest_cache` tracked in git
- `.mypy_cache` tracked in git
- Missing `.gitignore` file
- Missing `pixi.toml` or `pixi.lock` (pixi-only enforcement)

**Warnings (non-fatal):**
- `.env` files tracked in git
- OS-specific files (`.DS_Store`, `Thumbs.db`)

### Configuration

```yaml
jobs:
  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    with:
      enable-hygiene-check: true  # default: true
```

---

## Feature 3: Improved Security Scan Triggers

### Problem

Security scans only triggered on `security.yml` changes, missing dependency updates that could introduce vulnerabilities.

### Solution

Security scans now trigger on changes to:
- `.github/workflows/security.yml`
- `pyproject.toml`
- `pixi.toml`
- `pixi.lock`
- `requirements*.txt`

This ensures any dependency change triggers a security review.

---

## Pixi-Only Enforcement

The CI Framework explicitly requires pixi-based projects. If `pixi.toml` or `pixi.lock` is not found:

1. **Hygiene check** fails with clear error message
2. **Editable install** fails with clear error message
3. **All subsequent jobs** are blocked

This prevents pip-only projects from using the framework incorrectly.

### Error Message

```
::error::No pixi.toml or pixi.lock found. ci-framework requires pixi-based projects.
```

---

## Migration from pip-based Projects

To use ci-framework, migrate to pixi:

```bash
# Initialize pixi project
pixi init

# Add dependencies from requirements.txt
pixi add $(cat requirements.txt | grep -v "^#" | tr '\n' ' ')

# Add dev dependencies
pixi add --feature dev pytest ruff mypy

# Create pixi tasks
pixi task add test "pytest"
pixi task add lint "ruff check ."
pixi task add quality "ruff check . && mypy ."
```

Then commit `pixi.toml` and `pixi.lock` to your repository.
