"""Guard: the workflows call the verify-ci-bot-token action, not inline copies.

`.github/actions/verify-ci-bot-token/action.yml` is the canonical copy of the
CI_BOT_TOKEN preflight (#355, #482). The six former inline copies in
reusable-ci.yml and reusable-security.yml (sast-semgrep, sast-codeql,
scorecard-token-preflight) call it through the remote form pinned to a
release tag: a reusable workflow cannot use `./` (#262). The two
`workflow_call` workflows self-healing and cleanup-dev-files use the same
remote form with `check-code-scanning: 'false'`. Three standalone workflows
(release-please, auto-merge-release, sync-main-to-development) call it through
the local `./` form with `check-code-scanning: 'false'`.

Those eight probe-off jobs never read `use_pat` for SARIF, but they must still
use the PAT only when the preflight accepted it (#509): a read-only classic PAT
yields `use_pat=false`. Every token selection in such a job is therefore exactly
`steps.token-preflight.outputs.use_pat == 'true' && secrets.CI_BOT_TOKEN ||
github.token`, and `use_pat` of a probe-off step never gates SARIF upload (that
needs the code-scanning probe).

This guard enforces, for every `*.yml` / `*.yaml` workflow:

  * NO inline copy (a `run:` step named like the preflight, carrying its id, or
    running its `/rate_limit` probe / a `curl` with `CI_BOT_TOKEN` env) remains
    anywhere; the
    INLINE_ALLOWLIST is empty;
  * exactly eight remote call sites exist (six probe-on in reusable-*, two
    probe-off in self-healing and cleanup-dev-files), each `uses:` the action at
    the released tag in `.release-please-manifest.json`, keeping the id, passing
    `with.token: ${{ secrets.CI_BOT_TOKEN }}` (plus `check-code-scanning:
    'false'` for the two probe-off sites) and nothing else;
  * exactly three local `./` call sites exist, each preceded by a credential-less
    sparse checkout of `.github/actions` (at the base SHA when the workflow runs
    on `pull_request`) and never in a `pull_request_target` / `workflow_run`
    workflow;
  * every remote call-site line carries the `# x-release-please-version` marker
    so a release bumps the pin;
  * the action declares every output the workflows consume through
    `steps.token-preflight.outputs.*`, wired to the step of the same id.

Walk-the-tree guards can pass vacuously, hence the exact count and the
classifier self-tests below, which run the exact helpers the real tests use.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from framework.tests.workflows.test_ci_bot_token_preflight import (
    ACTION_USES_PATTERN,
    ACTION_USES_PREFIX,
    EXPECTED_ENV_VALUE,
    PREFLIGHT_STEP_ID,
    PREFLIGHT_STEP_NAME,
    REPO_ROOT,
    SARIF_ACTION_PREFIXES,
    WORKFLOWS_DIR,
    is_action_checkout,
    iter_strings,
    job_steps,
    load_jobs,
)

ACTION_PATH = REPO_ROOT / ".github" / "actions" / "verify-ci-bot-token" / "action.yml"
MANIFEST_PATH = REPO_ROOT / ".release-please-manifest.json"
CONSUMED_OUTPUT = re.compile(
    r"steps\." + re.escape(PREFLIGHT_STEP_ID) + r"\.outputs\.([\w-]+)"
)
ALLOWED_SITE_KEYS = frozenset({"name", "id", "uses", "with"})
RELEASE_MARKER = "# x-release-please-version"

# 3 jobs (sast-semgrep, sast-codeql, scorecard-token-preflight) in each of
# reusable-ci.yml and reusable-security.yml (probe on), plus self-healing.yml
# and cleanup-dev-files.yml (probe off). EXACT by design: adding or removing a
# site is deliberate and updates these constants in the same commit.
EXPECTED_PROBE_ON_SITES = 6
EXPECTED_PROBE_OFF_SITES = 2
EXPECTED_SITES = EXPECTED_PROBE_ON_SITES + EXPECTED_PROBE_OFF_SITES
PROBE_OFF_REMOTE_FILES = frozenset({"self-healing.yml", "cleanup-dev-files.yml"})
REMOTE_PROBE_OFF_WITH = {"token": EXPECTED_ENV_VALUE, "check-code-scanning": "false"}
# release-please, auto-merge-release and sync-main-to-development, `./` form.
EXPECTED_LOCAL_SITES = 3
LOCAL_USES = "./.github/actions/verify-ci-bot-token"
LOCAL_WITH = {"token": EXPECTED_ENV_VALUE, "check-code-scanning": "false"}
LOCAL_SITE_KEYS = frozenset({"name", "id", "uses", "with"})
# `${{ ... }}` expressions, and the two token mentions a probe-off job may keep
# besides the gated selection: pure presence tests (#509).
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
PRESENCE_TEST = re.compile(r"secrets\.CI_BOT_TOKEN (?:==|!=) ''")
SARIF_USES = re.compile("|".join(re.escape(p) for p in SARIF_ACTION_PREFIXES))
BASE_SHA_REF = "${{ github.event.pull_request.base.sha }}"
UNTRUSTED_TRIGGERS = frozenset({"pull_request_target", "workflow_run"})
# Inline-copy detection, as compiled patterns (not substring tests on URLs).
# The `rate_limit` endpoint is the preflight's probe, with or without a slash.
RATE_LIMIT_PROBE = re.compile(r"\brate_limit\b")
# A token probe is an HTTP/API call: `gh api`, curl/wget, a GitHub API URL or
# `${GITHUB_API_URL}`. `gh pr`/`gh release` consumers and plain git are not.
API_CALL = re.compile(
    r"\bgh\s+api\b|\bcurl\b|\bwget\b"
    r"|https?://api\.github\.com(?:[/:\s\"']|$)"
    r"|\$\{?GITHUB_API_URL\b"
)
SECRET_REFERENCE = re.compile(r"secrets(?:\.|\[\s*['\"])CI_BOT_TOKEN\b", re.IGNORECASE)
# Jobs whose pushes must trigger downstream workflows: a set-but-rejected
# CI_BOT_TOKEN must fail them instead of silently using github.token.
REQUIRE_STEP_NAME = "Require a write-capable CI_BOT_TOKEN"
REQUIRE_STEP_ENV = {
    "HAS_PAT": "${{ secrets.CI_BOT_TOKEN != '' }}",
    "USE_PAT": "${{ steps." + PREFLIGHT_STEP_ID + ".outputs.use_pat }}",
}
EXPECTED_REQUIRE_JOBS = frozenset(
    {
        "auto-merge-release.yml:auto-merge-release",
        "release-please.yml:release-please",
        "sync-main-to-development.yml:sync-to-development",
    }
)
# No workflow may keep an inline copy of the preflight.
INLINE_ALLOWLIST: frozenset[str] = frozenset()


def workflow_yaml_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml` and `*.yaml` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def is_inline_copy(step: object) -> bool:
    """True for any `run:` step that looks like the preflight.

    Matched by name, by id, or by script content (the `/rate_limit` probe, or a
    `curl`/api call carrying the `CI_BOT_TOKEN` env), so renaming or re-id'ing a
    retained copy does not hide it. A step that merely exports the token to `gh`
    is a consumer, not a copy.
    """
    if not isinstance(step, dict) or not isinstance(step.get("run"), str):
        return False
    return (
        step.get("name") == PREFLIGHT_STEP_NAME
        or step.get("id") == PREFLIGHT_STEP_ID
        or RATE_LIMIT_PROBE.search(step["run"]) is not None
        or (
            carries_bot_token(step.get("env"))
            and API_CALL.search(step["run"]) is not None
        )
    )


def carries_bot_token(env: object) -> bool:
    """True when a step `env:` names CI_BOT_TOKEN or feeds it from the secret.

    Covers a renamed variable too (`GH_TOKEN: ${{ secrets.CI_BOT_TOKEN }}`).
    """
    if not isinstance(env, dict):
        return False
    return any(
        key == "CI_BOT_TOKEN"
        or (isinstance(value, str) and SECRET_REFERENCE.search(value) is not None)
        for key, value in env.items()
    )


def is_action_call(step: object) -> bool:
    """True for a step that `uses:` the verify-ci-bot-token action at any ref."""
    return (
        isinstance(step, dict)
        and isinstance(step.get("uses"), str)
        and step["uses"].startswith(ACTION_USES_PREFIX)
    )


def steps_matching(predicate) -> list[tuple[str, dict]]:
    """(file:job label, step) of every workflow step the predicate accepts."""
    return [
        (f"{path.name}:{job_id}", step)
        for path in workflow_yaml_files()
        for job_id, job in load_jobs(path).items()
        for step in job_steps(job)
        if predicate(step)
    ]


def is_local_call(step: object) -> bool:
    """True for a step that `uses:` the action through the local `./` form."""
    return isinstance(step, dict) and step.get("uses") == LOCAL_USES


def inline_copies() -> list[tuple[str, dict]]:
    """Inline copies in ALL workflows, minus the INLINE_ALLOWLIST files."""
    return [
        (label, step)
        for label, step in steps_matching(is_inline_copy)
        if label.split(":")[0] not in INLINE_ALLOWLIST
    ]


def allowlisted_inline_copies() -> list[tuple[str, dict]]:
    return [
        (label, step)
        for label, step in steps_matching(is_inline_copy)
        if label.split(":")[0] in INLINE_ALLOWLIST
    ]


def action_sites() -> list[tuple[str, dict]]:
    return steps_matching(is_action_call)


def local_sites() -> list[tuple[str, dict]]:
    return steps_matching(is_local_call)


def workflow_triggers(doc: object) -> set[str]:
    """Event names under `on:` (YAML parses the bare key `on` as True)."""
    if not isinstance(doc, dict):
        return set()
    on = doc.get("on", doc.get(True))
    if isinstance(on, dict):
        return set(on)
    if isinstance(on, str):
        return {on}
    return set(on) if isinstance(on, list) else set()


def local_site_problems(steps: list[dict], index: int, triggers: set[str]) -> list[str]:
    """Everything wrong with the `./` call at `steps[index]` in a job."""
    step = steps[index]
    problems: list[str] = []
    if step.get("name") != PREFLIGHT_STEP_NAME:
        problems.append(f"name must be {PREFLIGHT_STEP_NAME!r}")
    if step.get("id") != PREFLIGHT_STEP_ID:
        problems.append(f"id must be {PREFLIGHT_STEP_ID!r} (callers gate on use_pat)")
    if step.get("with") != LOCAL_WITH:
        problems.append(f"with must be exactly {LOCAL_WITH}")
    extra = sorted(set(step) - LOCAL_SITE_KEYS)
    if extra:
        problems.append(f"unexpected keys {extra}")
    if triggers & UNTRUSTED_TRIGGERS:
        problems.append(f"`./` action in a workflow triggered by {sorted(triggers)}")
    previous = steps[index - 1] if index else None
    checkout_with = (
        previous.get("with")
        if previous is not None and is_action_checkout(previous)
        else None
    )
    if not isinstance(checkout_with, dict):
        problems.append("must follow a persist-credentials: false sparse checkout")
    else:
        ref = checkout_with.get("ref")
        if "pull_request" in triggers and ref != BASE_SHA_REF:
            problems.append(f"pull_request workflow must check out {BASE_SHA_REF}")
        if "pull_request" not in triggers and ref is not None:
            problems.append(f"unexpected checkout ref {ref!r}")
    return problems


def released_tag() -> str:
    """The latest released tag, from the release-please manifest.

    release-please bumps the manifest and every `x-release-please-version`
    marker together, so a pin that differs names a tag that was never released.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return f"v{manifest['.']}"


def site_problems(
    step: dict, expected_tag: str | None = None, probe_off: bool = False
) -> list[str]:
    """Everything wrong with one remote action call site.

    `probe_off` selects the `check-code-scanning: 'false'` shape expected of the
    workflow_call sites in PROBE_OFF_REMOTE_FILES.
    """
    problems: list[str] = []
    if not ACTION_USES_PATTERN.fullmatch(str(step.get("uses"))):
        problems.append(
            f"uses must be pinned to a vX.Y.Z tag, got {step.get('uses')!r}"
        )
    elif expected_tag is not None and not str(step["uses"]).endswith(
        f"@{expected_tag}"
    ):
        problems.append(
            f"uses must be pinned to the released tag {expected_tag}, "
            f"got {step.get('uses')!r}"
        )
    if step.get("name") != PREFLIGHT_STEP_NAME:
        problems.append(f"name must be {PREFLIGHT_STEP_NAME!r}")
    if step.get("id") != PREFLIGHT_STEP_ID:
        problems.append(f"id must be {PREFLIGHT_STEP_ID!r}")
    expected_with = (
        REMOTE_PROBE_OFF_WITH if probe_off else {"token": EXPECTED_ENV_VALUE}
    )
    if step.get("with") != expected_with:
        problems.append(f"with must be exactly {expected_with}")
    extra = sorted(set(step) - ALLOWED_SITE_KEYS)
    if extra:
        problems.append(f"unexpected keys {extra}")
    return problems


def unmarked_pin_lines(text: str) -> list[str]:
    """Lines that `uses:` the action without the release-please marker."""
    return [
        line.strip()
        for line in text.splitlines()
        if ACTION_USES_PREFIX in line
        and line.strip().startswith("uses:")
        and RELEASE_MARKER not in line
    ]


def load_action() -> dict:
    return yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))


def action_step(action: dict) -> dict:
    """The composite action's `token-preflight` step."""
    steps = action["runs"]["steps"]
    return next(step for step in steps if step.get("id") == PREFLIGHT_STEP_ID)


def unexpected_steps(action: dict) -> list[object]:
    """`runs.steps` entries beyond the single `token-preflight` step.

    The first step carrying the preflight id is the one allowed; every other
    entry (a different id, no id, or a duplicate id) is unexpected.
    """
    remaining = list(action["runs"]["steps"])
    for index, step in enumerate(remaining):
        if isinstance(step, dict) and step.get("id") == PREFLIGHT_STEP_ID:
            del remaining[index]
            break
    return remaining


def consumed_outputs(workflows: dict[str, object]) -> set[str]:
    """Output names read through `steps.token-preflight.outputs.<name>`."""
    return {
        match.group(1)
        for doc in workflows.values()
        for text in iter_strings(doc)
        for match in CONSUMED_OUTPUT.finditer(text)
    }


def output_problems(action: dict, consumed: set[str]) -> list[str]:
    """Consumed outputs the action does not declare, or declares miswired."""
    declared = action.get("outputs") or {}
    problems: list[str] = []
    for name in sorted(consumed):
        expected = "${{ steps." + PREFLIGHT_STEP_ID + ".outputs." + name + " }}"
        if name not in declared:
            problems.append(f"action does not declare consumed output {name!r}")
        elif declared[name].get("value") != expected:
            problems.append(f"output {name!r} must have value {expected!r}")
    return problems


def skips_code_scanning_probe(step: object) -> bool:
    """True for an action call (any form) passing `check-code-scanning: 'false'`."""
    if not (is_action_call(step) or is_local_call(step)) or not isinstance(step, dict):
        return False
    with_ = step.get("with")
    return isinstance(with_, dict) and str(with_.get("check-code-scanning")) == "false"


def probe_off_ids(job: object) -> set[str]:
    """Ids of the probe-skipping action calls of a job."""
    return {
        step["id"]
        for step in job_steps(job)
        if skips_code_scanning_probe(step) and isinstance(step.get("id"), str)
    }


def gated_token(step_id: str) -> str:
    """The one allowed token selection, gated on the job's own preflight (#509)."""
    return (
        f"steps.{step_id}.outputs.use_pat == 'true' "
        "&& secrets.CI_BOT_TOKEN || github.token"
    )


def consumes_gated_token(step: object, step_id: str) -> bool:
    """True when any string of the step holds the gated token selection."""
    gated = gated_token(step_id)
    return any(gated in " ".join(text.split()) for text in iter_strings(step))


def preflight_order_problems(job: object) -> list[str]:
    """Steps consuming the gated token before the preflight that gates it."""
    if not isinstance(job, dict):
        return []
    steps = job_steps(job)
    problems: list[str] = []
    for index, step in enumerate(steps):
        step_id = step.get("id")
        if not (skips_code_scanning_probe(step) and isinstance(step_id, str)):
            continue
        problems += [
            f"step {earlier} consumes {step_id!r} before its preflight (step {index})"
            for earlier in range(index)
            if consumes_gated_token(steps[earlier], step_id)
        ]
    return problems


def require_step_problems(job: object) -> list[str]:
    """Everything wrong with the fail-loud step of a job that needs the PAT.

    Exactly one step named REQUIRE_STEP_NAME, after the preflight and before any
    consumer of the gated token, unconditional, with presence and verdict passed
    through env (never `${{ }}` in the script), failing on set-but-rejected.
    """
    if not isinstance(job, dict):
        return ["not a job"]
    steps = job_steps(job)
    found = [i for i, s in enumerate(steps) if s.get("name") == REQUIRE_STEP_NAME]
    pre = [i for i, s in enumerate(steps) if s.get("id") == PREFLIGHT_STEP_ID]
    if len(found) != 1 or len(pre) != 1:
        return [f"needs exactly one {REQUIRE_STEP_NAME!r} step and one preflight"]
    step, problems = steps[found[0]], []
    if found[0] < pre[0]:
        problems.append("require step must come after the preflight")
    if any(consumes_gated_token(s, PREFLIGHT_STEP_ID) for s in steps[: found[0]]):
        problems.append("a gated consumer runs before the require step")
    if step.get("env") != REQUIRE_STEP_ENV:
        problems.append(f"env must be exactly {REQUIRE_STEP_ENV}")
    run = step.get("run")
    if not isinstance(run, str) or "${{" in run:
        problems.append("run must be a script without ${{ }}")
    elif not (
        "::error title=CI_BOT_TOKEN rejected::" in run
        and "exit 1" in run
        and 'HAS_PAT}" = "true"' in run
        and 'USE_PAT}" != "true"' in run
    ):
        problems.append("run must exit 1 with the error when HAS_PAT and not USE_PAT")
    if "if" in step or "continue-on-error" in step:
        problems.append("require step must be unconditional")
    return problems


def probe_off_token_problems(job: object, workflow_env: object = None) -> list[str]:
    """Token selections in a probe-skipping job that ignore its `use_pat` (#509).

    A probe-off caller never reads `use_pat` for SARIF, but it must still use the
    PAT only when the preflight accepted it: with a read-only classic PAT the
    action reports `use_pat=false`. Every `${{ }}` expression outside the
    preflight step that mentions `secrets.CI_BOT_TOKEN` must be the gated form of
    one of the job's own probe-off step ids, or a pure `== ''` / `!= ''`
    presence test. A probe-off step without an id cannot be gated and is flagged.
    """
    if not isinstance(job, dict):
        return []
    problems: list[str] = []
    allowed = {gated_token(step_id) for step_id in probe_off_ids(job)}
    nodes: list[object] = [{key: val for key, val in job.items() if key != "steps"}]
    if workflow_env is not None:
        nodes.append(workflow_env)
    for step in job_steps(job):
        if not skips_code_scanning_probe(step):
            nodes.append(step)
        elif not isinstance(step.get("id"), str):
            problems.append("probe-off preflight step has no id to gate on")
    for text in (text for node in nodes for text in iter_strings(node)):
        for expr in EXPRESSION.findall(text):
            normalized = " ".join(expr.split())
            if SECRET_REFERENCE.search(normalized) is None:
                continue
            if PRESENCE_TEST.fullmatch(normalized) or normalized in allowed:
                continue
            problems.append(f"token selection {normalized!r} ignores use_pat")
    return problems


def probe_off_sarif_problems(job: object) -> list[str]:
    """`use_pat` reads that feed SARIF upload in a job that skipped the probe.

    With the probe skipped, `use_pat` only means "the token is valid", NOT "the
    token can upload SARIF" (that needs the code-scanning probe), so a SARIF
    upload step, or a job output feeding `needs.*.outputs.use_pat` consumers,
    must not read it.
    """
    if not isinstance(job, dict):
        return []
    problems: list[str] = []
    sarif_steps = [
        step
        for step in job_steps(job)
        if isinstance(step.get("uses"), str) and SARIF_USES.match(step["uses"])
    ]
    for step_id in sorted(probe_off_ids(job)):
        reader = re.compile(r"steps\." + re.escape(step_id) + r"\.outputs\.use_pat\b")
        if any(reader.search(t) for s in sarif_steps for t in iter_strings(s)):
            problems.append(f"SARIF step gated on probe-off step {step_id!r} use_pat")
        if any(reader.search(t) for t in iter_strings(job.get("outputs"))):
            problems.append(f"job output exports probe-off step {step_id!r} use_pat")
    return problems


def probe_off_job_problems(job: object, workflow_env: object = None) -> list[str]:
    return (
        probe_off_token_problems(job, workflow_env)
        + probe_off_sarif_problems(job)
        + preflight_order_problems(job)
    )


def probe_off_jobs() -> list[tuple[str, object, object]]:
    """(file:job label, job, workflow-level env) of each probe-skipping job."""
    found = []
    for path in workflow_yaml_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        workflow_env = doc.get("env") if isinstance(doc, dict) else None
        for job_id, job in load_jobs(path).items():
            if any(skips_code_scanning_probe(step) for step in job_steps(job)):
                found.append((f"{path.name}:{job_id}", job, workflow_env))
    return found


def load_workflows() -> dict[str, object]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in workflow_yaml_files()
    }


# --- Real-tree tests ---------------------------------------------------------


def test_walk_finds_exactly_the_expected_action_sites():
    found = action_sites()
    assert len(found) == EXPECTED_SITES, (
        f"walk found {len(found)} verify-ci-bot-token call sites, expected "
        f"exactly {EXPECTED_SITES}; the glob or matcher may be broken"
    )


def test_no_inline_copy_remains_anywhere():
    assert not INLINE_ALLOWLIST, "the inline allowlist must stay empty"
    assert not inline_copies(), (
        "inline preflight copies must be replaced by the action: "
        f"{[label for label, _ in inline_copies()]}"
    )
    assert not allowlisted_inline_copies()
    assert not steps_matching(is_inline_copy)


def test_remote_sites_split_into_probe_on_and_probe_off():
    found = action_sites()
    off = sorted(
        label for label, _ in found if label.split(":")[0] in PROBE_OFF_REMOTE_FILES
    )
    on = [
        label for label, _ in found if label.split(":")[0] not in PROBE_OFF_REMOTE_FILES
    ]
    assert len(off) == EXPECTED_PROBE_OFF_SITES, off
    assert len(on) == EXPECTED_PROBE_ON_SITES, on
    assert {label.split(":")[0] for label in off} == PROBE_OFF_REMOTE_FILES
    assert all(label.startswith("reusable-") for label in on), on
    for path_name in PROBE_OFF_REMOTE_FILES:
        doc = yaml.safe_load((WORKFLOWS_DIR / path_name).read_text(encoding="utf-8"))
        assert "workflow_call" in workflow_triggers(doc), path_name


def test_walk_finds_exactly_the_expected_local_sites():
    found = local_sites()
    assert len(found) == EXPECTED_LOCAL_SITES, (
        f"walk found {len(found)} `./` call sites, expected exactly "
        f"{EXPECTED_LOCAL_SITES}; the glob or matcher may be broken"
    )
    assert sorted({label.split(":")[0] for label, _ in found}) == [
        "auto-merge-release.yml",
        "release-please.yml",
        "sync-main-to-development.yml",
    ]


def test_every_local_site_is_sound_and_trusted():
    failures = []
    for path in workflow_yaml_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = workflow_triggers(doc)
        for job_id, job in load_jobs(path).items():
            steps = job_steps(job)
            for index, step in enumerate(steps):
                if is_local_call(step):
                    failures += [
                        f"{path.name}:{job_id}: {problem}"
                        for problem in local_site_problems(steps, index, triggers)
                    ]
    assert not failures, "\n".join(failures)


def test_every_site_calls_the_action_at_a_pinned_tag():
    failures = [
        f"{label}: {problem}"
        for label, step in action_sites()
        for problem in site_problems(
            step,
            released_tag(),
            probe_off=label.split(":")[0] in PROBE_OFF_REMOTE_FILES,
        )
    ]
    assert not failures, "\n".join(failures)


def test_every_site_line_carries_the_release_marker():
    failures = [
        f"{path.name}: {line}"
        for path in workflow_yaml_files()
        for line in unmarked_pin_lines(path.read_text(encoding="utf-8"))
    ]
    assert not failures, "\n".join(failures)


def test_action_has_a_single_composite_preflight_step():
    action = load_action()
    assert action["runs"]["using"] == "composite"
    assert not unexpected_steps(action), (
        "the action must contain exactly one step, token-preflight; found "
        f"{unexpected_steps(action)}"
    )
    step = action_step(action)
    assert step.get("shell") == "bash"
    assert "${{" not in step["run"], "run must not interpolate ${{ }}"
    assert step["env"] == {
        "CI_BOT_TOKEN": "${{ inputs.token }}",
        "CHECK_CODE_SCANNING": "${{ inputs.check-code-scanning }}",
    }
    assert action["inputs"]["token"].get("required") is False
    assert action["inputs"]["check-code-scanning"]["default"] == "true"
    assert action["inputs"]["check-code-scanning"].get("required") is False


def test_walk_finds_every_probe_off_job_and_each_has_a_gated_token():
    jobs = probe_off_jobs()
    assert len(jobs) == EXPECTED_PROBE_OFF_SITES + EXPECTED_LOCAL_SITES, [
        label for label, _, _ in jobs
    ]
    for label, job, _ in jobs:
        assert any(
            gated_token(step_id) in " ".join(text.split())
            for step_id in probe_off_ids(job)
            for text in iter_strings(job)
        ), f"{label}: no token selection gated on the preflight use_pat"


def test_probe_off_jobs_honour_use_pat_and_never_gate_sarif_on_it():
    failures = [
        f"{label}: {problem}"
        for label, job, workflow_env in probe_off_jobs()
        for problem in probe_off_job_problems(job, workflow_env)
    ]
    assert not failures, "\n".join(failures)


def test_fail_loud_step_exists_in_exactly_the_push_triggering_jobs():
    with_step = {
        label
        for label, job, _ in probe_off_jobs()
        if any(s.get("name") == REQUIRE_STEP_NAME for s in job_steps(job))
    }
    assert with_step == EXPECTED_REQUIRE_JOBS, with_step
    failures = [
        f"{label}: {problem}"
        for label, job, _ in probe_off_jobs()
        if label in EXPECTED_REQUIRE_JOBS
        for problem in require_step_problems(job)
    ]
    assert not failures, "\n".join(failures)


def test_action_declares_every_consumed_output():
    consumed = consumed_outputs(load_workflows())
    assert consumed, "walk found no steps.token-preflight.outputs.* consumers"
    problems = output_problems(load_action(), consumed)
    assert not problems, "\n".join(problems)


# --- Classifier self-tests (guard against a vacuously passing walk) ----------


def _canonical() -> dict:
    return {
        "id": PREFLIGHT_STEP_ID,
        "shell": "bash",
        "env": {"CI_BOT_TOKEN": "${{ inputs.token }}"},
        "run": 'if [ -z "${CI_BOT_TOKEN}" ]; then\n  exit 0\nfi\n',
    }


def _site(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "uses": f"{ACTION_USES_PREFIX}@v5.2.0",
        "with": {"token": EXPECTED_ENV_VALUE},
    }
    step.update(overrides)
    return step


def test_selftest_extra_action_steps_are_flagged():
    only = {"runs": {"steps": [_canonical()]}}
    other = {"id": "other", "run": "true"}
    assert unexpected_steps(only) == []
    assert unexpected_steps({"runs": {"steps": [_canonical(), other]}}) == [other]
    assert unexpected_steps({"runs": {"steps": [other, _canonical()]}}) == [other]
    duplicate = {"runs": {"steps": [_canonical(), _canonical()]}}
    assert len(unexpected_steps(duplicate)) == 1


def test_selftest_sound_site_is_not_flagged():
    assert site_problems(_site()) == []


def test_selftest_unpinned_or_wrong_ref_is_flagged():
    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"  # pragma: allowlist secret
    for ref in ("main", "v5", sha, "v5.2.0-rc1"):
        step = _site(uses=f"{ACTION_USES_PREFIX}@{ref}")
        assert any("pinned" in p for p in site_problems(step)), ref


def test_selftest_unreleased_tag_is_flagged():
    step = _site(uses=f"{ACTION_USES_PREFIX}@v5.2.1")
    assert site_problems(step) == []  # syntactically valid on its own
    assert any("released tag" in p for p in site_problems(step, "v5.2.0"))
    assert site_problems(_site(), "v5.2.0") == []


def test_released_tag_reads_the_manifest():
    assert re.fullmatch(r"v\d+\.\d+\.\d+", released_tag())


def test_selftest_changed_inputs_or_extra_keys_are_flagged():
    assert site_problems(_site(**{"with": {}}))
    assert site_problems(_site(**{"with": {"token": "${{ github.token }}"}}))
    assert site_problems(_site(id="other"))
    assert site_problems(_site(name="Something else"))
    for key in ("if", "continue-on-error", "env", "run"):
        problems = site_problems(_site(**{key: "x"}))
        assert any("unexpected keys" in problem for problem in problems), key


def test_selftest_inline_and_call_matchers_are_distinct():
    inline = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "env": {},
        "run": "true",
    }
    assert is_inline_copy(inline)
    assert not is_inline_copy(_site())
    # Renamed / re-id'd copies are still caught, by content or by env.
    assert is_inline_copy(
        {**inline, "id": "other"} | {"name": "x", "run": "curl /rate_limit"}
    )
    probe = {"run": "curl -H x https://example.test", "env": {"CI_BOT_TOKEN": "x"}}
    assert is_inline_copy(probe)
    # A legitimate token consumer (env + a non-probe script) is not a copy.
    assert not is_inline_copy(
        {"run": "export GH_TOKEN=$T", "env": {"CI_BOT_TOKEN": "x"}}
    )
    assert not is_inline_copy({"run": "echo hi"})
    # Renamed token variable and a `gh api` probe (no curl, no /rate_limit
    # slash) must not evade the guard.
    renamed_env = {"GH_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"}
    assert is_inline_copy({"run": "gh api rate_limit", "env": {}})
    assert is_inline_copy({"run": "gh api /user", "env": renamed_env})
    assert is_inline_copy({"run": "gh api user", "env": {"CI_BOT_TOKEN": "x"}})
    assert is_inline_copy(
        {"run": 'wget "https://api.github.com/user"', "env": renamed_env}
    )
    assert is_inline_copy(
        {
            "run": 'curl "${GITHUB_API_URL}/user"',
            "env": {"X": "${{ secrets.CI_BOT_TOKEN }}"},
        }
    )
    # A gh consumer (pr/push, no API probe) is not a copy, even with the token.
    assert not is_inline_copy(
        {
            "run": 'export GH_TOKEN="$CI_BOT_TOKEN"\ngh pr create --fill\ngit push',
            "env": {"CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"},
        }
    )
    assert not is_inline_copy({"run": "gh api user", "env": {"GH_TOKEN": "x"}})
    assert not is_inline_copy({**inline, "run": None, "id": "other", "name": "x"})
    assert not is_inline_copy("not a dict")
    assert is_action_call(_site())
    assert not is_action_call(inline)
    assert not is_action_call({"uses": "actions/checkout@v7"})
    assert not is_action_call("not a dict")


def _checkout(**with_overrides: object) -> dict:
    return {
        "uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "with": {
            "sparse-checkout": ".github/actions",
            "persist-credentials": False,
            **with_overrides,
        },
    }


def _local(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "uses": LOCAL_USES,
        "with": dict(LOCAL_WITH),
    }
    step.update(overrides)
    return step


def _without_id(step: dict) -> dict:
    return {key: value for key, value in step.items() if key != "id"}


def test_selftest_local_site_rules():
    push = {"push"}
    assert local_site_problems([_checkout(), _local()], 1, push) == []
    pr_checkout = _checkout(ref=BASE_SHA_REF)
    assert local_site_problems([pr_checkout, _local()], 1, {"pull_request"}) == []
    # pull_request without the base ref, or any ref on a push workflow.
    assert local_site_problems([_checkout(), _local()], 1, {"pull_request"})
    assert local_site_problems([pr_checkout, _local()], 1, push)
    # Untrusted triggers, a missing/unsafe checkout, wrong inputs, extra keys.
    for trigger in sorted(UNTRUSTED_TRIGGERS):
        assert local_site_problems([_checkout(), _local()], 1, {trigger})
    assert local_site_problems([_local()], 0, push)
    assert local_site_problems(
        [_checkout(**{"persist-credentials": True}), _local()], 1, push
    )
    assert local_site_problems(
        [_checkout(), _local(**{"with": {"token": "x"}})], 1, push
    )
    assert local_site_problems([_checkout(), _local(**{"if": "true"})], 1, push)
    assert local_site_problems([_checkout(), _local(id="other")], 1, push)
    assert local_site_problems([_checkout(), _without_id(_local())], 1, push)
    assert is_local_call(_local())
    assert not is_local_call(_site())
    assert not is_local_call("not a dict")


def test_selftest_local_site_rejects_a_checkout_path():
    push = {"push"}
    assert local_site_problems([_checkout(), _local()], 1, push) == []
    for path in ("../outside", "sub", "."):
        problems = local_site_problems([_checkout(path=path), _local()], 1, push)
        assert any("sparse checkout" in p for p in problems), path


def _gated(step_id: str = "token-preflight") -> str:
    return "${{ " + gated_token(step_id) + " }}"


def _remote_off(**overrides: object) -> dict:
    return _site(**{"with": dict(REMOTE_PROBE_OFF_WITH)}) | overrides


def test_selftest_probe_off_token_gated_on_use_pat_is_not_flagged():
    consumer = {"env": {"GH_TOKEN": _gated()}}
    multiline = {
        "with": {
            "token": "${{ steps.token-preflight.outputs.use_pat\n"
            "  == 'true' && secrets.CI_BOT_TOKEN || github.token }}"
        }
    }
    presence = {
        "run": "echo ${{ secrets.CI_BOT_TOKEN != '' }} ${{ secrets.CI_BOT_TOKEN == '' }}"
    }
    for site in (_local(id="token-preflight"), _remote_off()):
        job = {"steps": [site, consumer, multiline, presence]}
        assert probe_off_job_problems(job) == []


def test_selftest_probe_off_bare_or_misgated_token_is_flagged():
    site = _local(id="token-preflight")
    bad = [
        "${{ secrets.CI_BOT_TOKEN || github.token }}",
        "${{ secrets.CI_BOT_TOKEN || secrets.GITHUB_TOKEN }}",
        "${{ secrets.CI_BOT_TOKEN }}",
        "${{ steps.token-preflight.outputs.use_pat == 'false' "
        "&& secrets.CI_BOT_TOKEN || github.token }}",
        "${{ steps.other.outputs.use_pat == 'true' "
        "&& secrets.CI_BOT_TOKEN || github.token }}",
        "${{ github.token && secrets.CI_BOT_TOKEN != '' }}",
    ]
    for token in bad:
        for key in ("env", "with"):
            job = {"steps": [site, {key: {"X": token}}]}
            assert probe_off_token_problems(job), (key, token)
    # Job-level env is walked too, and an id-less probe-off step cannot be gated.
    assert probe_off_token_problems({"env": {"T": bad[0]}, "steps": [site]})
    idless = _without_id(_local())
    assert probe_off_token_problems({"steps": [idless, {"env": {"T": _gated()}}]})
    assert probe_off_token_problems("not a dict") == []


def test_selftest_probe_off_use_pat_must_not_gate_sarif_upload():
    site = _local(id="pf")
    upload = {
        "uses": "github/codeql-action/upload-sarif@abc",
        "with": {"token": "${{ steps.pf.outputs.use_pat == 'true' && 'x' }}"},
    }
    gated_if = {
        "uses": "github/codeql-action/analyze@abc",
        "if": "steps.pf.outputs.use_pat",
    }
    exported = {
        "outputs": {"use_pat": "${{ steps.pf.outputs.use_pat }}"},
        "steps": [site],
    }
    assert probe_off_sarif_problems({"steps": [site, upload]})
    assert probe_off_sarif_problems({"steps": [site, gated_if]})
    assert probe_off_sarif_problems(exported)
    remote = _remote_off(id="pf")
    assert probe_off_sarif_problems({"steps": [remote, upload]})
    # Not flagged: a non-SARIF consumer, a probe-on site, or no read at all.
    plain = {
        "uses": "actions/checkout@v7",
        "with": {"token": "${{ steps.pf.outputs.use_pat }}"},
    }
    assert probe_off_sarif_problems({"steps": [site, plain]}) == []
    assert probe_off_sarif_problems({"steps": [_site(id="pf"), upload]}) == []
    assert probe_off_sarif_problems({"steps": [site, {"run": "true"}]}) == []
    assert probe_off_sarif_problems("not a dict") == []
    assert not skips_code_scanning_probe(_site())
    assert skips_code_scanning_probe(_local())
    assert not skips_code_scanning_probe("not a dict")


def test_selftest_probe_off_walk_finds_jobs_in_a_synthetic_tree(tmp_path: Path):
    good = {"steps": [_local(id="token-preflight"), {"env": {"T": _gated()}}]}
    bad = {"steps": [_remote_off(), {"env": {"T": "${{ secrets.CI_BOT_TOKEN }}"}}]}
    other = {"steps": [_site(), {"run": "true"}]}
    doc = {"jobs": {"good": good, "bad": bad, "other": other}}
    (tmp_path / "w.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    jobs = {
        job_id: job
        for job_id, job in load_jobs(tmp_path / "w.yml").items()
        if any(skips_code_scanning_probe(step) for step in job_steps(job))
    }
    assert sorted(jobs) == ["bad", "good"]
    assert probe_off_job_problems(jobs["good"]) == []
    assert probe_off_job_problems(jobs["bad"])


def test_selftest_workflow_triggers_handles_yaml_on_forms():
    assert workflow_triggers(yaml.safe_load("on:\n  push:\n  pull_request:\n")) == {
        "push",
        "pull_request",
    }
    assert workflow_triggers(yaml.safe_load("on: push\n")) == {"push"}
    assert workflow_triggers(yaml.safe_load("on: [push, workflow_run]\n")) == {
        "push",
        "workflow_run",
    }
    assert workflow_triggers("not a dict") == set()


def test_selftest_inline_copy_classifier_detects_a_copy_in_a_tree(tmp_path: Path):
    # Non-vacuity: the classifier the real guard uses must flag a real inline copy.
    inline = {"name": PREFLIGHT_STEP_NAME, "run": "curl /rate_limit"}
    assert is_inline_copy(inline)
    doc = {"jobs": {"j": {"steps": [inline, _site()]}}}
    (tmp_path / "w.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    flagged = [
        step
        for job in load_jobs(tmp_path / "w.yml").values()
        for step in job_steps(job)
        if is_inline_copy(step)
    ]
    assert flagged == [inline]


def test_selftest_probe_off_remote_site_shape():
    off = _site(**{"with": dict(REMOTE_PROBE_OFF_WITH)})
    assert site_problems(off, probe_off=True) == []
    assert site_problems(off)  # probe-on shape rejects it
    assert site_problems(_site(), probe_off=True)  # and vice versa


def test_selftest_walk_classifies_a_synthetic_tree(tmp_path: Path):
    doc = {"jobs": {"j": {"steps": [_site(), {"run": "true"}]}}}
    (tmp_path / "w.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    steps = [
        step
        for job in load_jobs(tmp_path / "w.yml").values()
        for step in job_steps(job)
        if is_action_call(step)
    ]
    assert len(steps) == 1


def test_selftest_marker_check_flags_an_unmarked_pin():
    uses = f"uses: {ACTION_USES_PREFIX}@v5.2.0"
    assert unmarked_pin_lines(f"        {uses}  {RELEASE_MARKER}\n") == []
    assert unmarked_pin_lines(f"        {uses}\n") == [uses]
    assert unmarked_pin_lines("        uses: actions/checkout@v7\n") == []


def test_selftest_consumed_outputs_are_found_anywhere_in_a_workflow():
    doc = {
        "jobs": {
            "a": {"outputs": {"x": "${{ steps.token-preflight.outputs.use_pat }}"}},
            "b": {"steps": [{"if": "steps.token-preflight.outputs.extra == 'y'"}]},
            "c": {"steps": [{"run": "echo steps.other.outputs.ignored"}]},
        }
    }
    assert consumed_outputs({"w.yml": doc}) == {"use_pat", "extra"}


def test_selftest_secret_reference_matches_every_syntax_and_case():
    for text in (
        "secrets.CI_BOT_TOKEN",
        "secrets['CI_BOT_TOKEN']",
        'secrets["CI_BOT_TOKEN"]',
        "secrets[ 'CI_BOT_TOKEN' ]",
        "secrets.ci_bot_token",
        "SECRETS.Ci_Bot_Token",
    ):
        assert SECRET_REFERENCE.search(text), text
        assert carries_bot_token({"GH_TOKEN": "${{ " + text + " }}"}), text
        job = {
            "steps": [
                _local(id="token-preflight"),
                {"env": {"T": "${{ " + text + " }}"}},
            ]
        }
        assert probe_off_token_problems(job), text
    assert not SECRET_REFERENCE.search("secrets.CI_BOT_TOKEN_OTHER")
    assert not SECRET_REFERENCE.search("secrets.OTHER")


def test_selftest_probe_off_workflow_level_env_is_scanned():
    job = {"steps": [_local(id="token-preflight"), {"run": "true"}]}
    bare = {"T": "${{ secrets.CI_BOT_TOKEN }}"}
    assert probe_off_token_problems(job) == []
    assert probe_off_token_problems(job, bare)
    assert probe_off_job_problems(job, bare)
    assert probe_off_job_problems(job, {"T": _gated()}) == []


def test_selftest_preflight_must_precede_gated_consumers():
    site = _local(id="token-preflight")
    consumer = {"env": {"GH_TOKEN": _gated()}}
    assert preflight_order_problems({"steps": [site, consumer]}) == []
    assert preflight_order_problems({"steps": [consumer, site]})
    assert probe_off_job_problems({"steps": [consumer, site]})
    assert preflight_order_problems("not a dict") == []


def _require(**overrides: object) -> dict:
    step: dict = {
        "name": REQUIRE_STEP_NAME,
        "env": dict(REQUIRE_STEP_ENV),
        "run": (
            'if [ "${HAS_PAT}" = "true" ] && [ "${USE_PAT}" != "true" ]; then\n'
            "  echo '::error title=CI_BOT_TOKEN rejected::no downstream triggers'\n"
            "  exit 1\nfi\n"
        ),
    }
    step.update(overrides)
    return step


def test_selftest_require_step_rules():
    site = _local(id="token-preflight")
    consumer = {"env": {"GH_TOKEN": _gated()}}
    assert require_step_problems({"steps": [site, _require(), consumer]}) == []
    # Missing, duplicated, before the preflight, or after a gated consumer.
    assert require_step_problems({"steps": [site, consumer]})
    assert require_step_problems({"steps": [site, _require(), _require()]})
    assert require_step_problems({"steps": [_require(), site, consumer]})
    assert require_step_problems({"steps": [site, consumer, _require()]})
    # Wrong env, interpolated or non-failing script, conditional step.
    assert require_step_problems({"steps": [site, _require(env={"X": "y"})]})
    assert require_step_problems(
        {"steps": [site, _require(run="echo ${{ secrets.CI_BOT_TOKEN }}")]}
    )
    assert require_step_problems({"steps": [site, _require(run="true")]})
    assert require_step_problems({"steps": [site, _require(**{"if": "false"})]})
    assert require_step_problems("not a dict")


def test_selftest_require_step_job_set_is_exact():
    site = _local(id="token-preflight")
    jobs = {
        "a": {"steps": [site, _require()]},
        "b": {"steps": [site, {"run": "true"}]},
    }
    with_step = {
        key
        for key, job in jobs.items()
        if any(s.get("name") == REQUIRE_STEP_NAME for s in job_steps(job))
    }
    assert with_step == {"a"}
    assert with_step != {"a", "b"}


def test_selftest_undeclared_or_miswired_output_is_flagged():
    action = {
        "outputs": {
            "use_pat": {"value": "${{ steps.token-preflight.outputs.use_pat }}"},
            "miswired": {"value": "${{ steps.other.outputs.miswired }}"},
        }
    }
    assert output_problems(action, {"use_pat"}) == []
    assert any("missing" in p for p in output_problems(action, {"missing"}))
    assert any("miswired" in p for p in output_problems(action, {"miswired"}))
