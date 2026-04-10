# Security Scanning Reusable Workflow

> **Multi-language security scanning with dependency audits, SAST, secret detection, and security posture scoring**

## Overview

The Security Scanning workflow automatically detects your repository's languages and runs comprehensive security checks. It combines dependency vulnerability scanning (CVE detection), static analysis (SAST via Semgrep and CodeQL), secret detection (TruffleHog), and security posture scoring (OpenSSF Scorecard) to provide defense-in-depth security coverage.

By default, the workflow **blocks on CVEs and secrets** (fails the workflow), but only **warns on SAST findings** (to avoid high false-positive rates). All security findings are uploaded to GitHub's Security tab via SARIF reports.

## Quick Start

Add to your consumer repository's workflow:

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

**Required permissions:**
- `security-events: write` — Upload SARIF reports to GitHub Security tab
- `contents: read` — Read source code
- `actions: read` — Read workflow metadata
- `id-token: write` — For CodeQL authentication

All inputs are optional. The workflow will auto-detect your languages and use sensible defaults.

## All Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `languages` | string | `` (empty) | Comma-separated languages to check. If empty, auto-detects from: `python` (pyproject.toml/setup.py), `rust` (Cargo.toml), `c_cpp` (CMakeLists.txt/C/C++ source files), `cython` (.pyx/.pxd files), `js_ts` (package.json). Example: `python,rust` |
| `fail-on-cve` | boolean | `true` | Fail the workflow on known dependency CVEs. Set to `false` to warn only. |
| `fail-on-sast` | boolean | `false` | Fail the workflow on SAST findings (Semgrep, CodeQL). Default warns only due to false-positive rates. |
| `fail-on-secrets` | boolean | `true` | Fail the workflow on detected secrets (TruffleHok). Set to `false` to warn only. |
| `scorecard` | boolean | `true` | Run OpenSSF Scorecard for security posture scoring. |

## Security Tools by Language

### Python
- **pip-audit** — Scans pyproject.toml and requirements.txt for known CVEs in PyPI packages

### Rust
- **cargo-audit** — Audits Cargo.toml dependencies against the RustSec Advisory Database
- **cargo-deny** — Enforces license policies and additional advisory checks

### JavaScript/TypeScript
- **npm audit** — Built-in npm vulnerability scanning for package.json dependencies

### All Languages (Multi-language SAST)
- **Semgrep** — Pattern-based static analysis for security anti-patterns (high-confidence rules only)
- **CodeQL** — Semantic code analysis for Python, C/C++, JavaScript/TypeScript

### All Languages (Secret Detection & Posture)
- **TruffleHog** — Scans for accidentally committed secrets (API keys, credentials, tokens)
- **OpenSSF Scorecard** — Evaluates repository security practices (code review, CI/CD, dependency management, etc.)

## Default Behavior

| Finding Type | Default Action | Configurable |
|--------------|----------------|--------------|
| CVE (known vulnerability) | **BLOCK** — fails workflow | `fail-on-cve` |
| Secret (API key, credential) | **BLOCK** — fails workflow | `fail-on-secrets` |
| SAST (code pattern issue) | **WARN** — annotates PR only | `fail-on-sast` |
| Scorecard (posture) | **REPORT** — appears in workflow summary | (informational) |

## SARIF Integration

Several tools upload results to GitHub's Security tab:

| Tool | SARIF Upload | GitHub UI |
|------|--------------|-----------|
| CodeQL | Yes | Security → Code scanning |
| Semgrep | Yes | Security → Code scanning |
| TruffleHog | Yes | Security → Secret scanning |
| pip-audit | No | Workflow run summary only |
| cargo-audit | No | Workflow run summary only |
| npm audit | No | Workflow run summary only |
| OpenSSF Scorecard | No | Workflow run summary only |

## Example Configurations

### Minimal: Auto-detect with defaults (recommended)

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

Detects languages, blocks on CVEs and secrets, warns on SAST, runs Scorecard.

### Strict: Block everything

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      fail-on-sast: true
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

Fails workflow on any SAST findings (use if your repository has strict security requirements).

### Explicit languages: Python + Rust only

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      languages: 'python,rust'
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

Skips JavaScript, C/C++, and Cython checks even if present.

### Warning-only: Development branch

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      fail-on-cve: false
      fail-on-secrets: false
      fail-on-sast: false
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

All findings appear as workflow annotations only; none block merge. Useful for initial rollout on existing codebases.

### No Scorecard: Fast feedback

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      scorecard: false
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

Skips OpenSSF Scorecard (which takes 1-2 minutes). Useful if you run security checks frequently.

## How Findings Appear

### Workflow Annotations

Security findings appear in the workflow run as annotations:

```
❌ Security Scanning
Found 1 CVE in requirements.txt
  - django==3.1.0 has CVE-2021-33571
```

### GitHub Security Tab

SARIF-enabled tools (CodeQL, Semgrep, TruffleHog) upload findings to:
- **Code scanning** (SAST): `/security/code-scanning`
- **Secret scanning**: `/security/secret-scanning`

### Inline PR Comments

When findings affect changed files, GitHub automatically displays them in the PR diff.

## Language Detection

The workflow auto-detects languages by checking for:

| Language | Detection | Override |
|----------|-----------|----------|
| Python | `pyproject.toml` or `setup.py` present | `languages: 'python'` |
| Rust | `Cargo.toml` present | `languages: 'rust'` |
| C/C++ | `CMakeLists.txt` or `.c`/`.cpp`/`.h` files | `languages: 'c_cpp'` |
| Cython | `.pyx` or `.pxd` files | `languages: 'cython'` |
| JavaScript/TypeScript | `package.json` present | `languages: 'js_ts'` |

## Integration with Quality & Testing

Combine with `reusable-ci.yml` for comprehensive checks:

```yaml
jobs:
  quality:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-ci.yml@main
    secrets: inherit

  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    permissions:
      security-events: write
      contents: read
      actions: read
      id-token: write
```

Both run independently and report together in the PR.

## Troubleshooting

### "No matching language detected"

If the workflow skips all security checks:
- Verify your project has the expected files: `pyproject.toml`, `Cargo.toml`, `package.json`, etc.
- Use `languages: 'python'` to manually specify languages

### "CVE found but not failing"

- Check that `fail-on-cve: true` is set (default)
- Verify the workflow run shows the failure step in the Actions tab

### "Too many SAST findings"

- SAST tools (Semgrep, CodeQL) can produce false positives in some codebases
- Use `fail-on-sast: false` (default) to warn only
- Suppress specific rules in a `.semgrep.yml` or `.github/codeql/codeql-config.yml`

### "Scorecard is slow"

- OpenSSF Scorecard requires cloning the repository and analyzing commit history
- Use `scorecard: false` to skip it if you run security checks on every push

### Secret scanning is missing

- TruffleHok scans the entire repository, including commit history
- If no secrets are found, the step completes silently
- Secrets are only reported if detected; there's no "Secrets: 0 found" summary

---

**Workflow Version**: 1.0
**Last Updated**: April 2026
**Compatibility**: GitHub Actions, Python 3.10+, Rust 1.70+, Node.js 18+, C++17
