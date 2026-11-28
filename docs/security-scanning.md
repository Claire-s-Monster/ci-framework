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
    with:
      codeql: true  # this example does not call reusable-ci.yml, so it owns CodeQL
    permissions:
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
```

Since v5 CodeQL is off by default in `reusable-security.yml` (it is owned by
`reusable-ci.yml`). Drop `codeql: true` if you also call `reusable-ci.yml`;
without it, and without `reusable-ci.yml`, the SAST coverage is Semgrep only.

**Required permissions:**
- `contents: read` — Read source code
- `actions: read` — Read workflow metadata
- `id-token: write` — Lets OpenSSF Scorecard publish results (`publish_results`)
- `security-events: write` — Grant it and every SARIF upload (Semgrep, CodeQL, Scorecard) reaches the Security tab with `GITHUB_TOKEN`. It costs nothing on Scorecard's Token-Permissions check: a job-level write under a read-only top-level `permissions:` only produces a warning, and Scorecard never reads the remote reusable workflow (verified in #353). If you cannot grant it, supply `CI_BOT_TOKEN` instead.

**`CI_BOT_TOKEN` (secret, pass via `secrets: inherit`):** an optional PAT with the `security_events` scope, an alternative for when you cannot grant `security-events: write`. The SARIF jobs (Semgrep, CodeQL, Scorecard) declare no `permissions:` block of their own, so they inherit your grant and fall back to `github.token` when it is set (a job-level block would replace the caller's grant, #352; the Scorecard block was removed in #353). Without either the grant or the PAT, the jobs still run and stay green, but their SARIF never reaches the Security tab. Keep the PAT valid: an expired or revoked token is still non-empty, so it wins `CI_BOT_TOKEN || github.token` and is rejected with HTTP 401 instead of falling back (#355). To catch this, every job that consumes `CI_BOT_TOKEN` starts with a "Verify CI_BOT_TOKEN is valid" step, except the Scorecard job, whose `publish_results` verification forbids extra steps (the SAST jobs in the same run perform the check). The step calls `GET /rate_limit` with the token. It fails the job with an actionable error on HTTP 401 (including the SARIF jobs, whose upload steps would otherwise fail silently), does nothing when the secret is unset, and only warns on other or transient responses. Either rotate the token or delete the secret to fall back to `github.token`.

All inputs are optional. The workflow will auto-detect your languages and use sensible defaults.

## All Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `languages` | string | `` (empty) | Comma-separated languages to check. If empty, auto-detects from: `python` (pyproject.toml/setup.py), `rust` (Cargo.toml), `c_cpp` (CMakeLists.txt/C/C++ source files), `cython` (.pyx/.pxd files), `js_ts` (package.json). Example: `python,rust` |
| `pixi-environment` | string | `ci` | Pixi environment the Python dependency audit installs and runs `safety-check` in. If the audit tool is not installed there (exit code 127) the audit is skipped with a `::warning::` and `fail-on-cve` does not fail the job. If the audit tool crashes (non-zero exit with a Python `Traceback` in its output, or an exit code above 128 meaning it was killed by a signal, e.g. 139 segfault or 137 SIGKILL/OOM) the step reports `status=crashed` with a `::error title=Dependency audit tool crashed::` annotation: the audit did not complete and this is not a vulnerability finding. A crash always fails the job (via the `Fail on audit tool crash` step), regardless of `fail-on-cve`, because the dependencies were not audited at all. Other non-zero exits report `status=findings`. |
| `codeql` | boolean | `false` | Run CodeQL here. CodeQL moved to `reusable-ci.yml` as of v5; set `true` only if this repo does NOT call `reusable-ci.yml`. Setting it while also calling `reusable-ci.yml` duplicates `codeql-<lang>` uploads (#215). When skipped, the summary job emits a `CodeQL moved to reusable-ci` warning. |
| `codeql-languages` | string | `` (empty) | CodeQL-only language allowlist (`python`, `c-cpp`, `javascript-typescript`). Empty auto-detects. Only used when `codeql: true`; the owner `reusable-ci.yml` has its own `codeql-languages`. |
| `codeql-config-file` | string | `` (empty) | Path to a CodeQL config file, passed to `codeql-action/init`. Only used when `codeql: true`. |
| `codeql-packs` | string | `` (empty) | Comma-separated published CodeQL packs (`scope/name[@version]`; checked-in pack paths are not supported), passed to `codeql-action/init`. Only used when `codeql: true`. A non-empty value replaces the `packs` of `codeql-config-file` unless prefixed with `+`. The same value goes to EVERY language in the CodeQL matrix, so a language-specific pack can break the other analyses; multi-language repos should declare packs per language in `codeql-config-file`. |
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
- **CodeQL** — Semantic code analysis for Python, C/C++, JavaScript/TypeScript. Owned by `reusable-ci.yml` (on by default); runs here only with `codeql: true`

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

## Why SAST Defaults to Advisory

Semgrep runs with `SEMGREP_RULES: p/python p/security-audit`. `p/security-audit` is an audit ruleset tuned for review breadth, not for gating: it is deliberately broad, and by design it carries a high false-positive rate. That breadth is useful in PR review — a human can skim and dismiss noise — but it is a poor basis for automatically failing a build. CVEs and secrets are binary, high-confidence findings; the audit ruleset is not. That distinction is why `fail-on-cve` and `fail-on-secrets` default to `true` and block, while `fail-on-sast` defaults to `false` and only warns.

Defaulting `fail-on-sast` to `false` does not mean SAST findings go unreported. The Semgrep step still runs on every invocation, uploads its results to GitHub's Security tab as SARIF, and annotates the PR when findings touch changed files (see [SARIF Integration](#sarif-integration) and [How Findings Appear](#how-findings-appear) below). Only the job's pass/fail status is unaffected by default.

To opt in, set `fail-on-sast: true`. If you gate on SAST, consider narrowing `SEMGREP_RULES` to a higher-confidence rule set rather than gating on `p/security-audit` as-is — otherwise the gate will fail on advisory findings rather than real ones.

This is a deliberate, permanent default — decided in #305 — not a pending decision. It is documented here so a future reader does not mistake it for an oversight and file it again as a bug.

## SARIF Integration

Several tools upload results to GitHub's Security tab:

| Tool | SARIF Upload | GitHub UI |
|------|--------------|-----------|
| CodeQL (from `reusable-ci.yml`, or here with `codeql: true`) | Yes | Security → Code scanning |
| Semgrep | Yes | Security → Code scanning |
| TruffleHog | No | Workflow run summary only |
| pip-audit | No | Workflow run summary only |
| cargo-audit | No | Workflow run summary only |
| npm audit | No | Workflow run summary only |
| OpenSSF Scorecard | Yes (needs `security-events: write` or CI_BOT_TOKEN) | Security → Code scanning |

Uploads run with `continue-on-error: true`, so a failed upload leaves the job green; check the upload step's log for `Resource not accessible by integration`.

## Example Configurations

The examples below call `reusable-security.yml` alone. CodeQL is off by default
there (since v5 it belongs to `reusable-ci.yml`), so add `codeql: true` to any of
them that should keep CodeQL and does not also call `reusable-ci.yml`.

### Minimal: Auto-detect with defaults (recommended)

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      codeql: true  # only if this repo does not also call reusable-ci.yml
    permissions:
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
```

Detects languages, blocks on CVEs and secrets, warns on SAST (Semgrep, plus
CodeQL because of `codeql: true`), runs Scorecard.

### Strict: Block everything

```yaml
jobs:
  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    with:
      fail-on-sast: true
      codeql: true  # reusable-security runs CodeQL only when asked (v5); drop if you also call reusable-ci.yml
    permissions:
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
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
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
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
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
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
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
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

SARIF-enabled tools (CodeQL, Semgrep, OpenSSF Scorecard) upload findings to:
- **Code scanning**: `/security/code-scanning`

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
    permissions:
      contents: read
      actions: read
      id-token: write  # OpenSSF Scorecard
      security-events: write  # CodeQL/Semgrep/Scorecard SARIF upload
    secrets: inherit  # optional: CI_BOT_TOKEN

  security:
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-security.yml@main
    permissions:
      security-events: write  # SAST SARIF upload via GITHUB_TOKEN
      contents: read
      actions: read
      id-token: write
    secrets: inherit  # optional: CI_BOT_TOKEN
```

**Token scope warning.** `reusable-ci.yml` sets no job-level `permissions:`
(a job block would replace the caller's grant), so a caller-level
`security-events: write` is inherited by every job in that call, including the
jobs that run your repository's test and build code. For pull requests from
forks GitHub downgrades the token to read-only, so the risk is limited to
same-repo PRs (and anything that runs repository code with write access).
The least-privilege alternative is to omit `security-events: write` and pass a
narrowly scoped `CI_BOT_TOKEN` (a PAT with only the `security_events` scope):
each SARIF upload uses `CI_BOT_TOKEN` only when a preflight confirms the PAT
can read the code-scanning API (`GET .../code-scanning/analyses` returns 200),
and otherwise uses `github.token`. A 401 fails the preflight; a 403 or 404
(missing `security_events` scope) falls back to `github.token`, which then
needs the caller's `security-events: write` grant, so a PAT lacking the scope
cannot substitute for that grant. The preflight fails closed on an unknown
result: it retries a curl failure or HTTP 5xx up to 3 attempts (sleeping 2s,
then 4s), then fails the run, and it also fails if `curl` is missing. For a
classic PAT it reads the `X-OAuth-Scopes` header of `/rate_limit`: without
`repo` or `public_repo` (or `security_events` when probing code scanning) the
token is reported read-only and `github.token` is used. Fine-grained PATs and
App tokens send no such header, so their write access is unchecked (the probe
only checks read access; a write probe for them is a possible follow-up). The
PAT reaches only the upload steps. Choose the grant only if you trust
every contributor who can open same-repo PRs. CodeQL's SARIF is written to
`${{ runner.temp }}`, outside the checkout, so a PR cannot commit a forged
`.sarif` for upload.

Both run independently and report together in the PR. CodeQL runs only in
`reusable-ci.yml` here (its `codeql` input defaults to `true`); `reusable-security.yml`
skips it, so `codeql-<lang>` is uploaded once. Use `codeql: true` on
`reusable-security.yml` only when you do not call `reusable-ci.yml`.

CodeQL uploads from the `reusable-ci.yml` caller job, so that job needs
`security-events: write` (as above) or a valid `CI_BOT_TOKEN`; the grant on the
`security` job does not carry over. Without either, the CodeQL upload fails
non-fatally and the results never reach the Security tab.

## Upgrading to v5 — CodeQL ownership

As of v5, `reusable-ci.yml` is the single CodeQL owner (`codeql` defaults to
`true`) and `reusable-security.yml` runs CodeQL only with `codeql: true`
(default `false`). This ends the duplicate `codeql-<lang>` uploads for callers
of both workflows (#215). Every `reusable-security.yml` run that skips CodeQL
emits a `CodeQL moved to reusable-ci` warning and a step-summary note.

- **Upgrading from v2.9.1, or from any version after 64aedd1 that did not set `codeql: true`:** you (re)gain CodeQL in `reusable-ci.yml` and may see NEW code-scanning alerts. Uploads use `upload-sarif` with `continue-on-error`, so repos without Code Security or without `security-events: write` stay green.
- **Repos calling only `reusable-security.yml`:** add `codeql: true` to keep CodeQL.
- **Repos calling both:** update both workflow references to v5 together; the duplicate uploads then disappear. Three things to carry over first:
  - If you set `codeql: false` on `reusable-ci.yml` to avoid duplicates while `reusable-security.yml` owned CodeQL, remove it (or set `true`). Left in place, and with the new `reusable-security.yml` default of `false`, neither workflow runs CodeQL.
  - If you limited CodeQL with `languages` or `codeql-languages` on `reusable-security.yml`, set the equivalent `codeql-languages` on `reusable-ci.yml`, which builds its own matrix from filesystem detection. Otherwise the scan can become broader, or an explicitly enabled language can be missed. Move any `codeql-config-file` / `codeql-packs` there too.
  - Grant `security-events: write` (or supply `CI_BOT_TOKEN`) to the `reusable-ci.yml` caller job, since CodeQL now uploads from there.
- **Staggered upgrades:** a `reusable-ci.yml` at v5 alongside a pre-v5 `reusable-security.yml` runs CodeQL in both and re-creates the duplicate `codeql-<lang>` uploads, so set `codeql: false` on `reusable-ci.yml` until `reusable-security.yml` is also on v5. The reverse order (`reusable-security.yml` on v5 first, with `reusable-ci.yml` still pre-v5, where CodeQL defaults off) leaves NO CodeQL, so set `codeql: true` on `reusable-security.yml` until `reusable-ci.yml` is on v5, then remove it.
- **Repos with their own CodeQL workflow, or GitHub's CodeQL default setup:** set `codeql: false` on `reusable-ci.yml`. GitHub rejects advanced-workflow SARIF while default setup is enabled, so otherwise CodeQL runs redundantly and its upload fails (tolerated, but wasted).
- **Repos with an expired or revoked `CI_BOT_TOKEN`:** the CodeQL job runs the same fail-closed `Verify CI_BOT_TOKEN is valid` preflight as the Semgrep job, so a stale token fails the run with an error naming `CI_BOT_TOKEN`. The same preflight also fails when the token cannot be checked (missing `curl`, or HTTP 000/5xx after 3 attempts). Python repos already hit this through Semgrep; repos whose only CodeQL languages are `c-cpp` or `javascript-typescript` now hit it too. Rotate the secret, or delete it to fall back to `github.token`.

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
**Compatibility**: GitHub Actions, Python 3.11+, Rust 1.70+, Node.js 18+, C++17
