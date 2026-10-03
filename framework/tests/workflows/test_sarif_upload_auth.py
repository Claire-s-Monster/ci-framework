"""Guard: every SARIF-uploading step in a shipped workflow can authenticate.

Issues #306 and #352. `github/codeql-action/upload-sarif` needs authorization to reach
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

Option (a)'s `|| github.token` fallback only works where the job's effective
permissions include `security-events: write` or inherit the caller's grant.
In jobs whose own `permissions:` block omits it, the block REPLACES the
caller's grant and the fallback is dead (verified by a consumer run, #352), so
those sites are PAT-dependent and pinned by `PAT_DEPENDENT_SITES_ALLOWLIST`.

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

import re
from pathlib import Path

import yaml

# Anchored to the repo root, not the process CWD: pytest's working
# directory is not guaranteed, and a relative path here would make the
# whole walk depend on where the runner happens to start.
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ACTIONS_DIR = REPO_ROOT / "actions"

# `uses:` references that are a SARIF upload, matched by substring so a
# version pin (`@v3`, `@v4`) never breaks the match.
SARIF_UPLOAD_MARKER = "upload-sarif"

# `github/codeql-action/analyze` also uploads SARIF, but only implicitly and
# only when `with.upload` is not `false` - see `analyze_step_uploads` below.
CODEQL_ANALYZE_MARKER = "codeql-action/analyze"

# The 9 auth-requiring SARIF sites in this repo today, re-enumerated for
# #306's follow-up (widening the corpus to `actions/**/action.yml`) and
# reduced by #354 (both `c-cpp-lint` upload steps deleted: cpp-linter-action
# writes no SARIF file, so they uploaded nothing):
#   6 upload-sarif sites:
#     reusable-security.yml:274, :357
#     reusable-ci.yml:652, :694, :739
#     actions/security-scan/action.yml:803
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
# `python-ci-template.yml.template`'s former upload-sarif site (line 113) was
# deleted outright (#306): the audit tools it ran emit no SARIF, so the step
# was uploading a file nothing produced. `actions/security-scan/action.yml`
# is a NEW site in this inventory - it was invisible to this guard before the
# corpus widened to cover `actions/**/action.yml`, which is exactly the gap
# that let it ship unauthenticated (now fixed with `token:`). That removal
# offset that addition (11); #354 then removed the two `c-cpp-lint` sites.
#
# This floor EQUALS the current count, so removing a site fails this test on
# purpose: consolidating one is a deliberate act that should update this
# constant in the same commit. The floor's real job is to fail loudly if the
# glob or the `uses:` matcher breaks and the walk silently finds near zero.
MINIMUM_EXPECTED_SITES = 9


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


def token_expression(step: dict) -> str | None:
    """The stripped, non-empty `with.token` string of `step`, else None."""
    with_block = step.get("with")
    if not isinstance(with_block, dict):
        return None
    token = with_block.get("token")
    if isinstance(token, str) and token.strip() != "":
        return token.strip()
    return None


def has_token_auth(step: dict) -> bool:
    """True when `step` passes a non-empty `with.token` (presence only).

    This says nothing about whether the token can actually authenticate: a
    `github.token` in a job with narrowed permissions is present but dead
    (#352). Capability is decided in `sarif_upload_is_authorized`.
    """
    return token_expression(step) is not None


# Any `secrets.<NAME>` other than GITHUB_TOKEN, or any `inputs.` reference
# (a caller-supplied token; composite actions use `inputs.github-token`).
_NON_GITHUB_TOKEN_SOURCE = re.compile(
    r"secrets\.(?!GITHUB_TOKEN\b)\w+|\binputs\.", re.IGNORECASE
)


def references_github_token(expr: str) -> bool:
    """True when `expr` references `github.token` or `secrets.GITHUB_TOKEN`."""
    return "github.token" in expr or "secrets.github_token" in expr.lower()


def references_non_github_token_source(expr: str) -> bool:
    """True when `expr` can resolve to a token that is NOT the job's GITHUB_TOKEN.

    `secrets.GITHUB_TOKEN` is the same token as `github.token`, so it is not a
    PAT and does not count here; any other secret or an `inputs.` reference
    (caller-supplied) does.
    """
    return _NON_GITHUB_TOKEN_SOURCE.search(expr) is not None


def effective_permissions(job_perms: dict, workflow_perms: dict) -> dict:
    """The permissions block that actually applies to a job.

    A job-level block REPLACES the workflow-level one rather than extending it.
    `{}` means no block anywhere, i.e. the job inherits the caller's / default
    grant.
    """
    return job_perms if job_perms else workflow_perms


def github_token_can_upload(job_perms: dict, workflow_perms: dict) -> bool:
    """True when GITHUB_TOKEN can plausibly upload SARIF in this job.

    Either there is no permissions block (inherits the caller's grant, which
    works iff the caller grants `security-events: write`) or the effective
    block grants it.
    """
    effective = effective_permissions(job_perms, workflow_perms)
    return not effective or has_security_events_write(effective)


def token_fallback_is_dead(step: dict, job_perms: dict, workflow_perms: dict) -> bool:
    """True when `step` relies on github.token in a job where it cannot upload.

    VERIFIED by a consumer run (#352), not inferred: in a `workflow_call`
    workflow, a job-level `permissions:` block omitting `security-events:
    write` strips it from GITHUB_TOKEN and the upload gets 403 "Resource not
    accessible by integration", masked green by `continue-on-error`.
    """
    expr = token_expression(step)
    if expr is None or not references_github_token(expr):
        return False
    return not github_token_can_upload(job_perms, workflow_perms)


def is_pat_dependent(step: dict, job_perms: dict, workflow_perms: dict) -> bool:
    """True when the ONLY working auth for `step` is a secret/PAT (#352).

    The token names a non-GITHUB_TOKEN source and GITHUB_TOKEN cannot upload in
    this job (its effective permissions narrow away `security-events: write`).
    Covers both `secrets.X || github.token` with a dead fallback (verified by a
    consumer run, #352) and a bare `secrets.X`.
    """
    expr = token_expression(step)
    if expr is None:
        return False
    return references_non_github_token_source(expr) and not github_token_can_upload(
        job_perms, workflow_perms
    )


def sarif_upload_is_authorized(
    step: dict, job_perms: dict, workflow_perms: dict
) -> bool:
    """True when `step` satisfies option (a) or (b) from the module docstring.

    Option (a) is a capability check (#352): a token must be present AND either
    not rely on a dead github.token fallback or name a non-GITHUB_TOKEN source.
    PAT-dependent sites count as authorized (they work when the documented
    secret is supplied); `PAT_DEPENDENT_SITES_ALLOWLIST` constrains them.
    """
    if has_security_events_write(job_perms) or has_security_events_write(
        workflow_perms
    ):
        return True
    expr = token_expression(step)
    if expr is None:
        return False
    return not token_fallback_is_dead(
        step, job_perms, workflow_perms
    ) or references_non_github_token_source(expr)


def job_permissions_narrow_without_security_events_write(job_perms: dict) -> bool:
    """True when `job_perms` is a non-empty permissions block missing
    `security-events: write` - the #306 defect shape.

    No `permissions:` block at all (`{}`) is FINE: the job inherits whatever
    the caller granted, which is exactly the fix applied to `sast-semgrep`
    and `sast-codeql` in both reusable workflows. A job-level `permissions:`
    block REPLACES the caller's grant rather than extending it, though, so a
    block that narrows to e.g. `contents: read` without also listing
    `security-events: write` leaves any `|| github.token` fallback on a
    SARIF-upload step in that job permanently dead.
    """
    return bool(job_perms) and not has_security_events_write(job_perms)


def _workflow_and_job(identifier: str) -> tuple[str, str]:
    """Split a `discover_sarif_upload_steps` identifier into `(file, job)`.

    Identifiers are `f"{path.name}::{job_name}::{step_label}"` - splitting
    with `maxsplit=2` keeps a `::` that happens to appear inside a step
    label from corrupting the file/job pair.
    """
    file_name, job_name, _label = identifier.split("::", 2)
    return file_name, job_name


# Ratchet, not a blanket assert (Task 3, #306 follow-up): each pair here is a
# SARIF-upload job whose job-level `permissions:` block narrows away
# `security-events: write` and is KNOWN remaining debt, not yet fixed. This
# is an EXACT set match in the test below, so a brand-new narrowing block
# anywhere fails (nothing new is free), re-adding a block to one of the
# jobs #306 already fixed (`sast-semgrep` / `sast-codeql` in both reusable
# workflows) fails, and quietly fixing one of these without shrinking the set
# fails too - the allowlist must be edited deliberately either way.
NARROWING_WITHOUT_SECURITY_EVENTS_WRITE_ALLOWLIST: frozenset[tuple[str, str]] = (
    frozenset(
        {
            # `scorecard`'s `permissions:` block exists for OpenSSF
            # Scorecard's own Token-Permissions check (id-token / actions /
            # contents), not for SARIF auth; its upload-sarif step
            # authenticates via `with.token` (CI_BOT_TOKEN).
            ("reusable-ci.yml", "scorecard"),
            ("reusable-security.yml", "scorecard"),
        }
    )
)


# Sites whose ONLY working SARIF auth is a secret/PAT (#352): the job's own
# `permissions:` block strips `security-events: write` from GITHUB_TOKEN, so
# the `|| github.token` fallback is dead. `scorecard` is kept this way for
# OpenSSF Token-Permissions (decision tracked in #353).
# Exact set match in the test below, like the narrowing ratchet.
PAT_DEPENDENT_SITES_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("reusable-ci.yml", "scorecard"),
        ("reusable-security.yml", "scorecard"),
    }
)


def sarif_relevant_action_files(directory: Path = ACTIONS_DIR) -> list[Path]:
    """Every `action.yml`/`action.yaml` under `directory`, RECURSIVELY.

    Composite actions live one level down (`actions/security-scan/action.yml`),
    unlike the flat workflow layout, so this walk must recurse.

    A composite action cannot declare a top-level `permissions:` block - that
    is only valid in a workflow or a job - so it always inherits whatever the
    CALLING job granted its `GITHUB_TOKEN`. That makes an unauthenticated
    `upload-sarif` step inside a composite action strictly more dangerous
    than the same step in a workflow: there is no local `permissions:` fix,
    only a `with.token` input threaded through from every caller, and the bug
    ships to every workflow that references the action, not just one. This is
    precisely the shape that let `actions/security-scan/action.yml` carry a
    broken, unauthenticated `upload-sarif` step past the original #306 guard,
    which only ever walked `.github/workflows/`.
    """
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name in ("action.yml", "action.yaml")
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


def discover_composite_action_sarif_steps(
    path: Path, doc: object
) -> list[tuple[str, dict, dict, dict]]:
    """Every `upload-sarif` step in one parsed composite action.

    A composite action's steps live at `runs.steps`, not `jobs.<name>.steps`,
    and it has no `permissions:` block at all (see `sarif_relevant_action_files`
    for why), so both permission dicts are always `{}` - only `with.token`
    can authorize a site found here.
    """
    if not isinstance(doc, dict):
        return []
    runs = doc.get("runs")
    if not isinstance(runs, dict):
        return []
    steps = runs.get("steps")
    if not isinstance(steps, list):
        return []
    found: list[tuple[str, dict, dict, dict]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        if not is_sarif_upload_step(step):
            continue
        identifier = f"{path.name}::<composite>::{step_label(step, index)}"
        found.append((identifier, step, {}, {}))
    return found


def sarif_relevant_files() -> list[Path]:
    """Every workflow, template, AND composite action this guard must cover.

    #306's original walk covered `.github/workflows/` only, which is why two
    real unauthenticated `upload-sarif` sites inside `actions/**/action.yml`
    survived undetected - a composite action ships to every workflow that
    references it, and (see `sarif_relevant_action_files`) can never fix the
    gap with a `permissions:` block of its own. This is the combined corpus;
    `sarif_relevant_workflow_files` is kept separate and unchanged for any
    existing caller that only wants the flat workflow walk.
    """
    return sarif_relevant_workflow_files() + sarif_relevant_action_files()


def all_sarif_relevant_steps() -> list[tuple[str, dict, dict, dict]]:
    """Every `upload-sarif` step across the combined `sarif_relevant_files` corpus."""
    discovered: list[tuple[str, dict, dict, dict]] = []
    for path in sarif_relevant_files():
        doc = yaml.safe_load(path.read_text())
        discovered.extend(discover_sarif_upload_steps(path, doc))
        discovered.extend(discover_composite_action_sarif_steps(path, doc))
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

    There are 9 such sites in this repo as of #354
    (workflows, templates, AND composite actions combined), and the floor is
    set to exactly that. Its job is to fail loudly if the glob or the `uses:`
    matcher silently breaks and the walk finds near zero - the same vacuity
    that let the guard this module replaces pass while two sites were broken.
    """
    count = len(all_sarif_relevant_steps())
    assert count >= MINIMUM_EXPECTED_SITES, (
        f"only found {count} upload-sarif steps across the whole repo; "
        f"expected at least {MINIMUM_EXPECTED_SITES} - the glob or the "
        "`uses:` matcher is broken, not the workflows (#306)"
    )


def test_every_upload_sarif_step_can_authenticate():
    """The real #306 invariant: every upload-sarif site satisfies (a) or (b).

    Collects every violation before asserting once, so a failure names all of
    them in a single run. Walks `sarif_relevant_files` (workflows, templates,
    AND composite actions), not just workflows - a composite action step has
    no `permissions:` block of its own to grant option (b), so it can only
    ever be authorized via option (a), `with.token`.
    """
    unauthorized = [
        identifier
        for identifier, step, perms, workflow_perms in all_sarif_relevant_steps()
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


def test_widened_corpus_includes_composite_actions():
    """Non-vacuity: `sarif_relevant_files` must actually contain a composite
    action, not just workflows - proving #306's corpus-widening is real and
    not a no-op that still only walks `.github/workflows/`.
    """
    relative_paths = {
        str(path.relative_to(REPO_ROOT)) for path in sarif_relevant_files()
    }
    assert "actions/security-scan/action.yml" in relative_paths, (
        "actions/security-scan/action.yml is missing from the corpus - the "
        "widening to actions/**/action.yml regressed and this guard is back "
        "to only covering .github/workflows/ (#306)"
    )


def test_synthetic_composite_action_violation_is_detected():
    """Proves the widened corpus would catch the class of bug that escaped
    #306's original guard: an unauthenticated `upload-sarif` step inside a
    SYNTHETIC composite action must be classified as a violation, not
    silently ignored because it lives under `actions/` instead of
    `.github/workflows/`.
    """
    doc = {
        "name": "synthetic-composite-action",
        "runs": {
            "using": "composite",
            "steps": [
                {
                    "uses": "github/codeql-action/upload-sarif@v4",
                    "with": {"sarif_file": "results.sarif"},
                }
            ],
        },
    }
    path = ACTIONS_DIR / "synthetic-fixture" / "action.yml"
    found = discover_composite_action_sarif_steps(path, doc)
    assert found, "the composite-action step walk found nothing for a synthetic doc"
    _, step, job_perms, workflow_perms = found[0]
    assert not sarif_upload_is_authorized(step, job_perms, workflow_perms), (
        "a composite-action upload-sarif step with no with.token must be "
        "flagged as a violation - this is exactly the shape that escaped "
        "the guard before the corpus widened to cover actions/ (#306)"
    )


def test_widened_corpus_still_exempts_analyze_with_upload_false():
    """Integration self-test: widening the corpus to include `actions/` must
    not resurrect reusable-ci.yml's exempted `analyze` + `upload: false` site
    (line 688, job `sast-codeql`) - only its separate upload-sarif step
    (line 694) should be found for that job.
    """
    sast_codeql_sites = [
        identifier
        for identifier, _, _, _ in all_sarif_relevant_steps()
        if "reusable-ci.yml" in identifier and "sast-codeql" in identifier
    ]
    assert len(sast_codeql_sites) == 1, (
        "expected exactly one SARIF site for reusable-ci.yml's sast-codeql "
        f"job (its upload-sarif step) but found {sast_codeql_sites} - the "
        "`upload: false` analyze exemption regressed when the corpus widened"
    )


def test_every_narrowing_job_permissions_block_includes_security_events_write():
    """Ratchet (#306 follow-up): a job-level `permissions:` block on a
    SARIF-upload job must include `security-events: write`, or it silently
    kills any `|| github.token` fallback on that job's upload step - see
    `job_permissions_narrow_without_security_events_write`.

    Asserted as an EXACT set match against
    `NARROWING_WITHOUT_SECURITY_EVENTS_WRITE_ALLOWLIST`, not a subset check,
    so three things all fail this test: a brand-new narrowing block anywhere
    in the corpus, re-adding a block to one of the three jobs #306 already
    fixed (`sast-semgrep` / `sast-codeql`), and silently fixing one of the
    allowlisted jobs without shrinking the constant to match.
    """
    violations = {
        _workflow_and_job(identifier)
        for identifier, _step, perms, _workflow_perms in all_sarif_relevant_steps()
        if job_permissions_narrow_without_security_events_write(perms)
    }
    assert violations == NARROWING_WITHOUT_SECURITY_EVENTS_WRITE_ALLOWLIST, (
        "the set of SARIF-upload jobs whose permissions: block narrows away "
        "security-events: write changed - update "
        "NARROWING_WITHOUT_SECURITY_EVENTS_WRITE_ALLOWLIST in this file to "
        f"match (found: {sorted(violations)})"
    )


def _pat_dependent_sites() -> set[tuple[str, str]]:
    """`(file, job)` pairs for every upload site that is PAT-dependent."""
    return {
        _workflow_and_job(identifier)
        for identifier, step, perms, workflow_perms in all_sarif_relevant_steps()
        if is_pat_dependent(step, perms, workflow_perms)
    }


def test_pat_dependent_sites_match_allowlist():
    """Ratchet (#352): the PAT-dependent SARIF sites equal the allowlist exactly.

    A new site whose github.token fallback is dead, or fixing one without
    shrinking `PAT_DEPENDENT_SITES_ALLOWLIST`, both fail - the set must be
    edited deliberately.
    """
    found = _pat_dependent_sites()
    assert found == PAT_DEPENDENT_SITES_ALLOWLIST, (
        "the set of PAT-dependent SARIF-upload jobs changed - update "
        "PAT_DEPENDENT_SITES_ALLOWLIST and the CI_BOT_TOKEN descriptions "
        f"(#352); found: {sorted(found)}"
    )


def test_pat_dependent_jobs_are_documented_in_ci_bot_token_description():
    """Each PAT-dependent job must be named as REQUIRED in its workflow's
    `CI_BOT_TOKEN` description (#352), so docs cannot drift from the guard."""
    jobs_by_file: dict[str, set[str]] = {}
    for file_name, job_name in _pat_dependent_sites():
        jobs_by_file.setdefault(file_name, set()).add(job_name)
    assert jobs_by_file, "no PAT-dependent sites found - the walk is broken"
    problems: list[str] = []
    for file_name, jobs in sorted(jobs_by_file.items()):
        doc = yaml.safe_load((WORKFLOWS_DIR / file_name).read_text())
        # yaml.safe_load parses the bare key `on` as Python True.
        triggers = doc.get("on") or doc.get(True) or {}
        secrets = (triggers.get("workflow_call") or {}).get("secrets") or {}
        description = (secrets.get("CI_BOT_TOKEN") or {}).get("description") or ""
        if "REQUIRED" not in description:
            problems.append(f"{file_name}: description lacks the word REQUIRED")
        problems.extend(
            f"{file_name}: description does not name `{job}`"
            for job in sorted(jobs)
            if job not in description
        )
    assert not problems, (
        "docs and guard drifted (#352): CI_BOT_TOKEN descriptions must say "
        f"REQUIRED and name every PAT-dependent job: {problems}"
    )


_PAT_STEP = {
    "uses": "github/codeql-action/upload-sarif@v4",
    "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
}


def _bare_step(token: str) -> dict:
    return {
        "uses": "github/codeql-action/upload-sarif@v4",
        "with": {"token": token},
    }


def test_classifier_rejects_bare_github_token_in_narrowed_job():
    """Self-test: github.token alone, job block lacks security-events: write."""
    step = _bare_step("${{ github.token }}")
    assert not sarif_upload_is_authorized(step, {"contents": "read"}, {})


def test_classifier_accepts_bare_github_token_when_inheriting():
    """Self-test: no permissions block anywhere means the caller's grant applies."""
    step = _bare_step("${{ github.token }}")
    assert sarif_upload_is_authorized(step, {}, {})


def test_classifier_rejects_bare_github_token_under_narrow_workflow_block():
    """Self-test: a workflow-level block applies when the job has none."""
    step = _bare_step("${{ github.token }}")
    assert not sarif_upload_is_authorized(step, {}, {"contents": "read"})


def test_classifier_marks_pat_fallback_in_narrowed_job_as_pat_dependent():
    """Self-test: PAT || github.token in a narrowed job is authorized but PAT-dependent."""
    perms = {"contents": "read"}
    assert sarif_upload_is_authorized(_PAT_STEP, perms, {})
    assert is_pat_dependent(_PAT_STEP, perms, {})


def test_classifier_marks_pat_fallback_when_inheriting_as_not_pat_dependent():
    """Self-test: PAT || github.token with no block can fall back, so not PAT-dependent."""
    assert sarif_upload_is_authorized(_PAT_STEP, {}, {})
    assert not is_pat_dependent(_PAT_STEP, {}, {})


def test_classifier_marks_bare_secret_in_narrowed_job_as_pat_dependent():
    """Self-test: a bare `secrets.X` token in a narrowed job is PAT-dependent too."""
    step = _bare_step("${{ secrets.CI_BOT_TOKEN }}")
    perms = {"contents": "read"}
    assert sarif_upload_is_authorized(step, perms, {})
    assert is_pat_dependent(step, perms, {})


def test_classifier_rejects_secrets_github_token_in_narrowed_job():
    """Self-test: secrets.GITHUB_TOKEN is the same dead token, not a PAT."""
    step = _bare_step("${{ secrets.GITHUB_TOKEN }}")
    assert not sarif_upload_is_authorized(step, {"contents": "read"}, {})


def test_classifier_accepts_inputs_token_and_is_not_pat_dependent():
    """Self-test: a caller-supplied `inputs.github-token` is authorized."""
    step = _bare_step("${{ inputs.github-token }}")
    assert sarif_upload_is_authorized(step, {}, {})
    assert not is_pat_dependent(step, {}, {})


def test_classifier_flags_narrow_permissions_on_a_job_with_upload_sarif_step():
    """Self-test: `permissions: {contents: read}` on a job with an
    upload-sarif step IS flagged."""
    doc = {
        "jobs": {
            "synthetic-job": {
                "permissions": {"contents": "read"},
                "steps": [
                    {
                        "uses": "github/codeql-action/upload-sarif@v4",
                        "with": {"sarif_file": "x.sarif"},
                    }
                ],
            }
        }
    }
    path = WORKFLOWS_DIR / "synthetic-fixture.yml"
    sites = discover_sarif_upload_steps(path, doc)
    assert len(sites) == 1
    _, _step, perms, _workflow_perms = sites[0]
    assert job_permissions_narrow_without_security_events_write(perms)


def test_classifier_does_not_flag_job_with_security_events_write():
    """Self-test: adding `security-events: write` to the job's permissions
    clears the flag."""
    doc = {
        "jobs": {
            "synthetic-job": {
                "permissions": {"contents": "read", "security-events": "write"},
                "steps": [
                    {
                        "uses": "github/codeql-action/upload-sarif@v4",
                        "with": {"sarif_file": "x.sarif"},
                    }
                ],
            }
        }
    }
    path = WORKFLOWS_DIR / "synthetic-fixture.yml"
    sites = discover_sarif_upload_steps(path, doc)
    assert len(sites) == 1
    _, _step, perms, _workflow_perms = sites[0]
    assert not job_permissions_narrow_without_security_events_write(perms)


def test_classifier_does_not_flag_job_with_no_permissions_block():
    """Self-test: no `permissions:` block at all means the job inherits the
    caller's grant, so it must NOT be flagged."""
    doc = {
        "jobs": {
            "synthetic-job": {
                "steps": [
                    {
                        "uses": "github/codeql-action/upload-sarif@v4",
                        "with": {"sarif_file": "x.sarif"},
                    }
                ],
            }
        }
    }
    path = WORKFLOWS_DIR / "synthetic-fixture.yml"
    sites = discover_sarif_upload_steps(path, doc)
    assert len(sites) == 1
    _, _step, perms, _workflow_perms = sites[0]
    assert not job_permissions_narrow_without_security_events_write(perms)


def test_classifier_ignores_narrow_job_whose_only_codeql_step_is_upload_false():
    """Self-test: `permissions: {contents: read}` on a job whose only codeql
    step is `analyze` with `upload: false` is NOT flagged - it is not a
    SARIF-upload SITE at all (the analyze step writes to disk only), so it
    must never reach the permissions check."""
    doc = {
        "jobs": {
            "synthetic-job": {
                "permissions": {"contents": "read"},
                "steps": [
                    {
                        "uses": "github/codeql-action/analyze@v4",
                        "with": {"upload": False, "category": "x"},
                    }
                ],
            }
        }
    }
    path = WORKFLOWS_DIR / "synthetic-fixture.yml"
    assert discover_sarif_upload_steps(path, doc) == []
