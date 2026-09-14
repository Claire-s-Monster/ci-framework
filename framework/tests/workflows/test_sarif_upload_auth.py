"""Guard: every SARIF-uploading step in a shipped workflow can authenticate.

Issue #306. `github/codeql-action/upload-sarif` needs authorization to reach
the code-scanning API - and so does `github/codeql-action/analyze`, which
uploads SARIF *implicitly* unless the step sets `with.upload: false`. When
`upload: false` is set, `analyze` only writes SARIF to disk and a separate
`upload-sarif` step (already covered by this guard) does the actual upload,
so that shape is deliberately EXEMPT from this check - flagging it would be
a false positive, not a real auth gap. This repo satisfies the auth
requirement in one of two legitimate ways, documented at
`.github/workflows/reusable-security.yml:88-92`:

  (a) the step passes `token: ${{ secrets.CI_BOT_TOKEN || github.token }}`
      under `with:` - the idiom used by reusable workflows, because a
      reusable workflow's job permissions are capped by its CALLER and the
      workflow itself declares no top-level `permissions:` block; or
  (b) the job (or the workflow) declares `security-events: write` in a
      `permissions:` block - correct for a standalone / consumer-owned
      workflow whose `GITHUB_TOKEN` is not capped by anyone else.

A site with NEITHER is broken and fails at upload time, silently, because
every upload-sarif step carries `continue-on-error: true` - see
`NON_SCANNER_ACTION_MARKERS` in `test_security_step_continue_on_error.py` -
so the job stays green.

`framework/tests/workflows/test_workflow_validation.py
::test_security_sarif_upload_configured` predates this guard and only ever
checked one hardcoded file
(`.github/workflows/python-ci-template.yml.template`) for the presence of
`with.sarif_file`, never for authorization. It has been narrowed rather than
deleted: it still legitimately covers the template's `sarif_file` shape, a
question this module does not ask.

This module defines its own workflow walk rather than reusing
`framework.tests.utils.pixi_meta.shipped_workflow_files`: that helper
deliberately excludes `*.yml.template`, but a template carrying a broken
`upload-sarif` step ships the bug to every consumer that copies it, so
this guard must cover templates too.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Anchored to the repo root, not the process CWD: pytest's working
# directory is not guaranteed, and a relative path here would make the
# whole walk depend on where the runner happens to start.
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# `uses:` references that are a SARIF upload, matched by substring so a
# version pin (`@v3`, `@v4`) never breaks the match.
SARIF_UPLOAD_MARKER = "upload-sarif"

# `github/codeql-action/analyze` also uploads SARIF, but only implicitly and
# only when `with.upload` is not `false` - see `analyze_step_uploads` below.
CODEQL_ANALYZE_MARKER = "codeql-action/analyze"

# The 11 auth-requiring SARIF sites in this repo today, enumerated for #306:
#   8 upload-sarif sites:
#     python-ci-template.yml.template:113   reusable-quality.yml:233
#     reusable-security.yml:274, :357
#     reusable-ci.yml:485, :652, :694, :739
#   3 codeql-action/analyze sites that upload implicitly (no `upload: false`):
#     standalone-ci.yml:297      job=security       (security-events: write)
#     ci.yml:140                 job=security-scan  (security-events: write)
#     reusable-security.yml:312  job=sast-codeql     (token present)
#
# Deliberately EXCLUDED: reusable-ci.yml:688, job=sast-codeql, sets
# `with.upload: false` - it writes SARIF to disk only, a separate
# upload-sarif step does the actual upload, so requiring auth on the analyze
# step itself would be a false positive.
#
# This floor EQUALS the current count, so removing a site fails this test on
# purpose: consolidating one is a deliberate act that should update this
# constant in the same commit. The floor's real job is to fail loudly if the
# glob or the `uses:` matcher breaks and the walk silently finds near zero.
MINIMUM_EXPECTED_SITES = 11


def sarif_relevant_workflow_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml`, `*.yaml` and `*.yml.template` file directly under `directory`.

    Deliberately broader than `pixi_meta.shipped_workflow_files`: that helper
    excludes `*.yml.template` on purpose because it is scaffolding GitHub
    never runs, but a template with an `upload-sarif` step ships the same
    broken-auth bug to every consumer that copies it, so #306's walk must
    cover it too. Flat, not recursive, matching GitHub's own workflow loader.
    """
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and (path.suffix in (".yml", ".yaml") or path.name.endswith(".yml.template"))
    )


def step_label(step: dict, index: int) -> str:
    """A stable human-readable label for a step (name, then id, then uses)."""
    for key in ("name", "id", "uses"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return f"<step {index}>"


def analyze_step_uploads(step: dict) -> bool:
    """True unless `step` sets `with.upload: false` (upload defaults to true).

    `yaml.safe_load` turns a bare `false` into the Python bool `False`, but a
    quoted `"false"` or a `${{ }}` expression arrives as a string, so both
    the bool and the string forms are treated as opting out of the upload.
    """
    with_block = step.get("with")
    if not isinstance(with_block, dict):
        return True
    upload = with_block.get("upload")
    return upload is not False and upload not in ("false", "False")


def is_sarif_upload_step(step: dict) -> bool:
    """True when `step`'s `uses:` names a SARIF upload action.

    Matches `upload-sarif` unconditionally, and `codeql-action/analyze` only
    when it actually uploads (see `analyze_step_uploads`) - an `analyze` step
    with `upload: false` writes SARIF to disk for a later upload-sarif step
    to send, so flagging it here would be a false positive.
    """
    uses = step.get("uses")
    if not isinstance(uses, str):
        return False
    uses_lower = uses.lower()
    if SARIF_UPLOAD_MARKER in uses_lower:
        return True
    return CODEQL_ANALYZE_MARKER in uses_lower and analyze_step_uploads(step)


def top_level_permissions(doc: object) -> dict:
    """The workflow's own top-level `permissions:` block, or `{}`."""
    if not isinstance(doc, dict):
        return {}
    permissions = doc.get("permissions")
    return permissions if isinstance(permissions, dict) else {}


def job_permissions(job: dict) -> dict:
    """A job's own `permissions:` block, or `{}`."""
    permissions = job.get("permissions")
    return permissions if isinstance(permissions, dict) else {}


def has_security_events_write(permissions: dict) -> bool:
    """True when `permissions` grants `security-events: write` (option b)."""
    return permissions.get("security-events") in ("write", "write-all")


def has_token_auth(step: dict) -> bool:
    """True when `step` passes a non-empty `with.token` (option a)."""
    with_block = step.get("with")
    if not isinstance(with_block, dict):
        return False
    token = with_block.get("token")
    return isinstance(token, str) and token.strip() != ""


def sarif_upload_is_authorized(
    step: dict, job_perms: dict, workflow_perms: dict
) -> bool:
    """True when `step` satisfies option (a) or (b) from the module docstring."""
    return (
        has_token_auth(step)
        or has_security_events_write(job_perms)
        or has_security_events_write(workflow_perms)
    )


def discover_sarif_upload_steps(
    path: Path, doc: object
) -> list[tuple[str, dict, dict, dict]]:
    """Every `upload-sarif` step in one parsed workflow.

    Returns `(identifier, step, job_permissions, workflow_permissions)` so a
    caller can check authorization without re-walking the document.
    """
    if not isinstance(doc, dict):
        return []
    workflow_perms = top_level_permissions(doc)
    found: list[tuple[str, dict, dict, dict]] = []
    for job_name, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        perms = job_permissions(job)
        for index, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            if not is_sarif_upload_step(step):
                continue
            identifier = f"{path.name}::{job_name}::{step_label(step, index)}"
            found.append((identifier, step, perms, workflow_perms))
    return found


def all_sarif_upload_steps() -> list[tuple[str, dict, dict, dict]]:
    """Every `upload-sarif` step across every workflow file and template."""
    discovered: list[tuple[str, dict, dict, dict]] = []
    for path in sarif_relevant_workflow_files():
        doc = yaml.safe_load(path.read_text())
        discovered.extend(discover_sarif_upload_steps(path, doc))
    return discovered


def test_every_sarif_relevant_workflow_file_parses():
    """A workflow/template failing to parse would contribute zero steps, silently."""
    files = sarif_relevant_workflow_files()
    assert files, "no workflow files discovered - the walk is broken"
    unparsed = [
        path.name
        for path in files
        if not isinstance(yaml.safe_load(path.read_text()), dict)
    ]
    assert not unparsed, (
        "these files did not parse as a mapping, so every check in this "
        f"module silently skipped them: {unparsed}"
    )


def test_walk_includes_template_files():
    """Non-vacuity: the corpus must include `*.yml.template`, not just `*.yml`.

    A careless refactor pointing this at `*.yml` only would silently drop
    `python-ci-template.yml.template` from this guard's coverage.
    """
    files = sarif_relevant_workflow_files()
    assert any(path.name.endswith(".yml.template") for path in files), (
        "no *.yml.template file was found in the corpus - the glob regressed "
        "to *.yml-only and this guard no longer covers scaffolding templates"
    )


def test_walk_finds_a_non_trivial_number_of_upload_sarif_sites():
    """Anti-vacuity: the walk must actually find upload-sarif steps.

    There are 11 such sites in this repo as of #306's audit, and the floor is
    set to exactly that. Its job is to fail loudly if the glob or the `uses:`
    matcher silently breaks and the walk finds near zero - the same vacuity
    that let the guard this module replaces pass while two sites were broken.
    """
    count = len(all_sarif_upload_steps())
    assert count >= MINIMUM_EXPECTED_SITES, (
        f"only found {count} upload-sarif steps across the whole repo; "
        f"expected at least {MINIMUM_EXPECTED_SITES} - the glob or the "
        "`uses:` matcher is broken, not the workflows (#306)"
    )


def test_every_upload_sarif_step_can_authenticate():
    """The real #306 invariant: every upload-sarif site satisfies (a) or (b).

    Collects every violation before asserting once, so a failure names all of
    them in a single run.
    """
    unauthorized = [
        identifier
        for identifier, step, perms, workflow_perms in all_sarif_upload_steps()
        if not sarif_upload_is_authorized(step, perms, workflow_perms)
    ]
    assert not unauthorized, (
        "these upload-sarif steps have neither a `with.token` nor a "
        "`security-events: write` permission (job- or workflow-level) and "
        f"will fail authentication at upload time (#306): {unauthorized}"
    )


def test_classifier_accepts_a_step_with_token_and_no_permissions():
    """Self-test: option (a) alone is sufficient."""
    step = {
        "uses": "github/codeql-action/upload-sarif@v4",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }
    assert sarif_upload_is_authorized(step, job_perms={}, workflow_perms={})


def test_classifier_accepts_a_step_with_job_level_permissions_and_no_token():
    """Self-test: option (b) at job level alone is sufficient."""
    step = {"uses": "github/codeql-action/upload-sarif@v4", "with": {}}
    assert sarif_upload_is_authorized(
        step, job_perms={"security-events": "write"}, workflow_perms={}
    )


def test_classifier_rejects_a_step_with_neither_token_nor_permissions():
    """Self-test: this proves the classifier can actually fail.

    Neither `with.token` nor `security-events: write` anywhere - this is
    exactly the shape of the #306 bug and must be REJECTED.
    """
    step = {
        "uses": "github/codeql-action/upload-sarif@v4",
        "with": {"sarif_file": "results.sarif"},
    }
    assert not sarif_upload_is_authorized(step, job_perms={}, workflow_perms={})


def test_classifier_ignores_a_non_sarif_upload_step():
    """Self-test: `actions/upload-artifact` is not `upload-sarif`."""
    step = {"uses": "actions/upload-artifact@v4", "with": {"name": "results"}}
    assert not is_sarif_upload_step(step)


def test_classifier_treats_analyze_without_upload_false_as_an_upload_site():
    """Self-test: `analyze` uploads by default, so it must be classified as a
    SARIF upload site when nothing opts it out."""
    step = {"uses": "github/codeql-action/analyze@v4", "with": {"category": "x"}}
    assert is_sarif_upload_step(step)


def test_classifier_exempts_analyze_with_upload_false():
    """Self-test: `analyze` with `upload: false` writes SARIF to disk only -
    a separate upload-sarif step does the real upload, so this must NOT be
    classified as an upload site regardless of whether YAML parsed `false`
    as a bool or it arrived as a string.
    """
    bool_step = {"uses": "github/codeql-action/analyze@v4", "with": {"upload": False}}
    assert not is_sarif_upload_step(bool_step)

    string_step = {
        "uses": "github/codeql-action/analyze@v4",
        "with": {"upload": "false"},
    }
    assert not is_sarif_upload_step(string_step)
