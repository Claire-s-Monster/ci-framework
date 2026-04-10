# Multi-Language CI Framework

> **Three-workflow architecture for unified quality, security, and testing across Python, Rust, C/C++, Cython, and JavaScript/TypeScript**

## Overview

The CI framework provides three reusable workflows that work together or independently:

1. **`reusable-quality.yml`** — Linting, formatting, type checking
2. **`reusable-security.yml`** — Dependency audits, SAST, secrets, security posture
3. **`reusable-ci.yml`** — Full CI pipeline: quality, testing, coverage, release

Each workflow:
- Auto-detects your repository's languages
- Runs language-appropriate tools
- Uploads results to GitHub (Security tab, PR annotations, workflow summary)
- Can be used independently or combined

## Three-Workflow Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Consumer Repository Workflow                   │
│                 (e.g., ci.yml)                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ reusable-ci.yml  │  │ reusable-      │            │
│  │                  │  │ security.yml   │            │
│  │ • Quality        │  │                │            │
│  │ • Testing        │  │ • CVE audit    │            │
│  │ • Coverage       │  │ • SAST         │            │
│  │ • Hygiene        │  │ • Secrets      │            │
│  │ • Release        │  │ • Scorecard    │            │
│  │ (pixi-managed)   │  │                │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                          │
│  Optional: reusable-code-policy.yml                     │
│  • Complexity & file size checks                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Language Auto-Detection Mechanism

Each workflow runs a `detect-languages` job that checks for:

| Language | Detection Logic |
|----------|-----------------|
| Python | `pyproject.toml` or `setup.py` exists |
| Rust | `Cargo.toml` exists |
| C/C++ | `CMakeLists.txt` exists OR `.c`/`.cpp`/`.h` files present |
| Cython | `.pyx` or `.pxd` files present |
| JavaScript/TypeScript | `package.json` exists |

For explicit control, override with the `languages` input (comma-separated):

```yaml
with:
  languages: 'python,rust'
```

This skips JavaScript, C/C++, and Cython even if present.

## Which Workflow to Use When

| Scenario | Workflow(s) | Rationale |
|----------|-----------|-----------|
| **Full CI pipeline (recommended)** | `reusable-ci.yml` | Handles quality, tests, coverage, security, and release in one call |
| **Security-only checks** | `reusable-security.yml` | Use for dependency audits, secret scanning without running tests |
| **Quality-only checks** | `reusable-quality.yml` | Lightweight linting/formatting without full CI |
| **Complex monorepo** | All three separately | Each can target different directories via inputs |
| **Existing consumers (no changes needed)** | Current setup | Migration is automatic; backward compatible |

## Comparison Table: Tool Coverage by Workflow

| Tool | reusable-ci.yml | reusable-quality.yml | reusable-security.yml |
|------|-----------------|----------------------|----------------------|
| **Python Lint (ruff)** | ✓ | ✓ | — |
| **Python Format (ruff)** | ✓ | ✓ | — |
| **Python Types (mypy)** | ✓ | ✓ | — |
| **Rust Lint (clippy)** | ✓ | ✓ | — |
| **Rust Format (rustfmt)** | ✓ | ✓ | — |
| **C/C++ Lint (clang-tidy)** | ✓ | ✓ | — |
| **C/C++ Static (cppcheck)** | ✓ | ✓ | — |
| **Cython Lint** | ✓ | ✓ | — |
| **JS/TS Lint (ESLint)** | ✓ | ✓ | — |
| **Python CVE Audit (pip-audit)** | ✓ | — | ✓ |
| **Rust CVE Audit (cargo-audit)** | ✓ | — | ✓ |
| **Rust Licenses (cargo-deny)** | ✓ | — | ✓ |
| **JS/TS CVE Audit (npm audit)** | ✓ | — | ✓ |
| **SAST (Semgrep)** | ✓ | — | ✓ |
| **SAST (CodeQL)** | ✓ | — | ✓ |
| **Secret Scan (TruffleHog)** | ✓ | — | ✓ |
| **Posture (Scorecard)** | ✓ | — | ✓ |
| **Testing (pytest, cargo test, etc.)** | ✓ | — | — |
| **Coverage (pytest-cov, etc.)** | ✓ | — | — |
| **Hygiene checks** | ✓ | — | — |

## Migration Guide: Existing Consumers

**No changes required!** The framework is backward compatible.

### Current Setup (Still Works)

If you're using individual workflows:

```yaml
# Current approach — still fully supported
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main

  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main

  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
```

Continue using this approach as-is. No action needed.

### Recommended: Consolidated to `reusable-ci.yml`

For simplicity, use the comprehensive workflow instead:

```yaml
# Recommended: single call
jobs:
  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    with:
      pixi-environment: 'ci'
      python-versions: '["3.10", "3.11", "3.12"]'
    secrets: inherit
```

`reusable-ci.yml` includes security and quality checks internally. You still get the same comprehensive coverage.

### What Changed (Internally)

The workflows now auto-detect languages and skip tools for languages not present. Previously, all tools ran regardless. Now:

- **Python project without Rust?** cargo-audit is skipped
- **Rust project without JavaScript?** npm audit is skipped
- **C++ project without Python?** pip-audit is skipped

This makes CI faster and cleaner, with fewer false negatives.

## Permissions Required

### For `reusable-ci.yml` (full pipeline)

```yaml
jobs:
  ci:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    permissions:
      contents: write
      pull-requests: write
      security-events: write
      id-token: write
      checks: write
    secrets: inherit
```

- `contents: write` — Create/update releases and badges
- `pull-requests: write` — Post coverage reports to PRs
- `security-events: write` — Upload SARIF to Security tab
- `id-token: write` — For CodeQL and PyPI token exchange
- `checks: write` — Annotations in workflow summary
- `secrets: inherit` — Access repository secrets for publishing

### For `reusable-quality.yml` (quality only)

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-quality.yml@main
    permissions:
      contents: read
```

### For `reusable-security.yml` (security only)

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

## Recommended Companion: CodeRabbit for AI PR Review

Pair the CI framework with **CodeRabbit** for intelligent automated PR review:

```yaml
jobs:
  coderabbit:
    uses: coderabbitai/coderabbit/.github/workflows/coderabbit-review.yml@main
```

CodeRabbit complements the CI framework by:
- Analyzing code logic and design patterns (CI checks syntax/style)
- Suggesting refactorings and improvements
- Reviewing test coverage and completeness
- Catching architectural issues the linters miss

**Combined workflow:**
1. **CI framework** → Ensures code quality, security, tests pass
2. **CodeRabbit** → Provides intelligent code review and suggestions
3. **Human review** → Makes final approval decision

## Pixi Integration

If your project uses **pixi** for dependency management, `reusable-ci.yml` automatically integrates:

```yaml
pixi-environment: 'ci'  # Use the 'ci' environment from pixi.toml
```

Quality tools (ruff, mypy, clippy, etc.) are installed from your `pixi.lock`, ensuring consistency across CI and local development.

## Results and Reporting

| Tool | Report Location | Format |
|------|-----------------|--------|
| Lint/Format | Workflow run + PR diff annotations | GitHub annotations |
| Type checking | Workflow run + PR diff annotations | GitHub annotations |
| Security findings (SARIF tools) | GitHub Security tab | SARIF + annotations |
| Coverage | PR comment | Markdown table + trend |
| Release notes | GitHub Release | Markdown + auto-generated changelog |
| Hygiene | Workflow run summary | Text report |

## Troubleshooting

### "Workflow is too slow"

- Quality checks: normally 1-2 minutes
- Security checks: 2-5 minutes (Scorecard adds 1-2 min)
- Full CI (testing + all above): 5-15 minutes depending on test suite

To speed up:
- Use `fail-on-sast: false` and `fail-on-typecheck: false` to skip some checks
- Disable `scorecard: false` in security workflow
- Parallelize test jobs across Python versions in `reusable-ci.yml`

### "Too many false positives"

- **Lint findings:** Configure rule allowlists in `pyproject.toml` (Python), `.eslintrc` (JS), etc.
- **Type checking:** Add `# type: ignore` comments or configure mypy to be less strict
- **SAST findings:** Use Semgrep baseline to suppress pre-existing issues

### "Secrets are flagged that aren't real"

TruffleHok can flag test credentials. Suppress with `.semgrep.yml`:

```yaml
# .semgrep.yml
rules:
  - id: suppress-trufflehog-test-secrets
    pattern: |
      $VAR = "test-api-key"
```

### "Language detection is wrong"

If a language is detected incorrectly:

```yaml
with:
  languages: 'python'  # Explicitly specify only Python
```

This overrides auto-detection.

## Example: Complete Consumer Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  ci:
    runs-on: ubuntu-latest
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    with:
      pixi-environment: 'ci'
      python-versions: '["3.10", "3.11", "3.12"]'
    permissions:
      contents: write
      pull-requests: write
      security-events: write
      id-token: write
      checks: write
    secrets: inherit
```

This single job gives you:
- Quality checks (lint, format, types)
- Security scanning (CVE, SAST, secrets)
- Testing (all Python versions)
- Coverage reporting
- Security posture scoring
- Hygiene checks
- Release automation

## Key Features

| Feature | Benefit |
|---------|---------|
| **Language auto-detection** | No configuration needed for multi-language projects |
| **Tool auto-selection** | Only relevant tools run; no false findings |
| **Pixi integration** | Consistent environment between CI and local dev |
| **SARIF uploads** | Security findings visible in GitHub Security tab |
| **PR annotations** | Violations appear inline in diffs |
| **Configurable severity** | Block on critical issues, warn on non-critical |
| **Backward compatible** | Existing consumers work unchanged |
| **CodeRabbit ready** | Pairs well with AI-powered PR review |

---

**Framework Version**: 2.5.0
**Last Updated**: April 2026
**Supported Languages**: Python, Rust, C/C++, Cython, JavaScript/TypeScript
**GitHub Actions**: v6 checkout, v6 setup-python, latest-stable Rust toolchain
