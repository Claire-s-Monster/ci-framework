"""Guard: the workflows call the verify-ci-bot-token action, not inline copies.

`.github/actions/verify-ci-bot-token/action.yml` is the canonical copy of the
CI_BOT_TOKEN preflight (#355, #482). The six former inline copies in
reusable-ci.yml and reusable-security.yml (sast-semgrep, sast-codeql,
scorecard-token-preflight) call it through the remote form pinned to a
release tag: a reusable workflow cannot use `./` (#262). Three standalone
workflows (release-please, auto-merge-release, sync-main-to-development) call
it through the local `./` form with `check-code-scanning: 'false'`.

This guard enforces, for every `*.yml` / `*.yaml` workflow:

  * NO inline copy (a `run:` step named like the preflight, carrying its id, or
    running its `/rate_limit` probe / `CI_BOT_TOKEN` env) remains anywhere,
    except in the explicit INLINE_ALLOWLIST of `workflow_call` workflows;
  * exactly six remote call sites exist, each `uses:` the action at the released
    tag in `.release-please-manifest.json`,
    keeping the id, passing `with.token: ${{ secrets.CI_BOT_TOKEN }}` and
    nothing else;
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
# reusable-ci.yml and reusable-security.yml. EXACT by design: adding or removing
# a site is deliberate and updates this constant in the same commit.
EXPECTED_SITES = 6
# release-please, auto-merge-release and sync-main-to-development, `./` form.
EXPECTED_LOCAL_SITES = 3
LOCAL_USES = "./.github/actions/verify-ci-bot-token"
LOCAL_WITH = {"token": EXPECTED_ENV_VALUE, "check-code-scanning": "false"}
LOCAL_SITE_KEYS = frozenset({"name", "uses", "with"})
BASE_SHA_REF = "${{ github.event.pull_request.base.sha }}"
UNTRUSTED_TRIGGERS = frozenset({"pull_request_target", "workflow_run"})
# The only workflows allowed to keep an inline copy: both are `workflow_call`
# reusables whose `./` would resolve against the caller's checkout (#262) and
# that need the remote pinned form instead.
# TODO(follow-up): move them to the remote form and empty this allowlist.
INLINE_ALLOWLIST = frozenset({"self-healing.yml", "cleanup-dev-files.yml"})


def workflow_yaml_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml` and `*.yaml` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def is_inline_copy(step: object) -> bool:
    """True for any `run:` step that looks like the preflight.

    Matched by name, by id, or by script content (the `/rate_limit` probe or the
    `CI_BOT_TOKEN` env), so renaming or re-id'ing a retained copy does not hide it.
    """
    if not isinstance(step, dict) or not isinstance(step.get("run"), str):
        return False
    env = step.get("env")
    return (
        step.get("name") == PREFLIGHT_STEP_NAME
        or step.get("id") == PREFLIGHT_STEP_ID
        or "/rate_limit" in step["run"]
        or (isinstance(env, dict) and "CI_BOT_TOKEN" in env)
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
    if step.get("with") != LOCAL_WITH:
        problems.append(f"with must be exactly {LOCAL_WITH}")
    extra = sorted(set(step) - LOCAL_SITE_KEYS)
    if extra:
        problems.append(f"unexpected keys {extra}")
    if triggers & UNTRUSTED_TRIGGERS:
        problems.append(f"`./` action in a workflow triggered by {sorted(triggers)}")
    previous = steps[index - 1] if index else None
    if not is_action_checkout(previous):
        problems.append("must follow a persist-credentials: false sparse checkout")
    else:
        ref = previous["with"].get("ref")
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


def site_problems(step: dict, expected_tag: str | None = None) -> list[str]:
    """Everything wrong with one action call site."""
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
    if step.get("with") != {"token": EXPECTED_ENV_VALUE}:
        problems.append(f"with must be exactly token: {EXPECTED_ENV_VALUE}")
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


def test_no_inline_copy_remains_outside_the_allowlist():
    assert not inline_copies(), (
        "inline preflight copies must be replaced by the action: "
        f"{[label for label, _ in inline_copies()]}"
    )


def test_inline_allowlist_is_exactly_the_two_workflow_call_files():
    # Non-vacuity: the allowlist names exactly the files that still carry an
    # inline preflight, and both are workflow_call reusables.
    copies = allowlisted_inline_copies()
    assert {label.split(":")[0] for label, _ in copies} == INLINE_ALLOWLIST
    named = [s for _, s in copies if s.get("name") == PREFLIGHT_STEP_NAME]
    assert len(named) == len(INLINE_ALLOWLIST)
    for name in INLINE_ALLOWLIST:
        doc = yaml.safe_load((WORKFLOWS_DIR / name).read_text(encoding="utf-8"))
        assert "workflow_call" in workflow_triggers(doc), name


def test_remote_sites_are_only_in_reusable_workflows():
    stray = [label for label, _ in action_sites() if not label.startswith("reusable-")]
    assert not stray, f"remote-pinned call outside a reusable-* workflow: {stray}"


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
        for problem in site_problems(step, released_tag())
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
    assert is_inline_copy({"run": "true", "env": {"CI_BOT_TOKEN": "x"}})
    assert not is_inline_copy({"run": "echo hi"})
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
        "uses": LOCAL_USES,
        "with": dict(LOCAL_WITH),
    }
    step.update(overrides)
    return step


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
    assert is_local_call(_local())
    assert not is_local_call(_site())
    assert not is_local_call("not a dict")


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


def test_selftest_allowlist_names_only_the_two_workflow_call_files():
    inline = {"name": PREFLIGHT_STEP_NAME, "run": "curl /rate_limit"}
    assert is_inline_copy(inline)
    assert "self-healing.yml" in INLINE_ALLOWLIST
    assert "release-please.yml" not in INLINE_ALLOWLIST


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
