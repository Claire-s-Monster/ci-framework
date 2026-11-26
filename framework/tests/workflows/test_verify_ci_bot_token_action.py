"""Guard: the reusable workflows call the verify-ci-bot-token action, pinned.

`.github/actions/verify-ci-bot-token/action.yml` is the canonical copy of the
CI_BOT_TOKEN preflight (#355, #482). The six former inline copies in
reusable-ci.yml and reusable-security.yml (sast-semgrep, sast-codeql,
scorecard-token-preflight) now call it through the remote form pinned to a
release tag: a reusable workflow cannot use `./` (#262).

This guard enforces, for every `*.yml` / `*.yaml` workflow:

  * NO inline copy (a step named like the preflight with `id: token-preflight`
    and a `run:`) remains anywhere;
  * exactly six call sites exist, each `uses:` the action at a `vX.Y.Z` tag,
    keeping the id, passing `with.token: ${{ secrets.CI_BOT_TOKEN }}` and
    nothing else;
  * every call-site line carries the `# x-release-please-version` marker so a
    release bumps the pin;
  * the action declares every output the workflows consume through
    `steps.token-preflight.outputs.*`, wired to the step of the same id.

Walk-the-tree guards can pass vacuously, hence the exact count and the
classifier self-tests below, which run the exact helpers the real tests use.
"""

from __future__ import annotations

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
    iter_strings,
    job_steps,
    load_jobs,
)

ACTION_PATH = REPO_ROOT / ".github" / "actions" / "verify-ci-bot-token" / "action.yml"
CONSUMED_OUTPUT = re.compile(
    r"steps\." + re.escape(PREFLIGHT_STEP_ID) + r"\.outputs\.([\w-]+)"
)
ALLOWED_SITE_KEYS = frozenset({"name", "id", "uses", "with"})
RELEASE_MARKER = "# x-release-please-version"

# 3 jobs (sast-semgrep, sast-codeql, scorecard-token-preflight) in each of
# reusable-ci.yml and reusable-security.yml. EXACT by design: adding or removing
# a site is deliberate and updates this constant in the same commit.
EXPECTED_SITES = 6


def workflow_yaml_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml` and `*.yaml` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def is_inline_copy(step: object) -> bool:
    """True for a step named like the preflight, with its fixed id and a `run:`."""
    return (
        isinstance(step, dict)
        and step.get("name") == PREFLIGHT_STEP_NAME
        and step.get("id") == PREFLIGHT_STEP_ID
        and "run" in step
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


def inline_copies() -> list[tuple[str, dict]]:
    return steps_matching(is_inline_copy)


def action_sites() -> list[tuple[str, dict]]:
    return steps_matching(is_action_call)


def site_problems(step: dict) -> list[str]:
    """Everything wrong with one action call site."""
    problems: list[str] = []
    if not ACTION_USES_PATTERN.fullmatch(str(step.get("uses"))):
        problems.append(
            f"uses must be pinned to a vX.Y.Z tag, got {step.get('uses')!r}"
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


def test_no_inline_copy_remains():
    assert not inline_copies(), (
        "inline preflight copies must be replaced by the action: "
        f"{[label for label, _ in inline_copies()]}"
    )


def test_every_site_calls_the_action_at_a_pinned_tag():
    failures = [
        f"{label}: {problem}"
        for label, step in action_sites()
        for problem in site_problems(step)
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
    assert step["env"] == {"CI_BOT_TOKEN": "${{ inputs.token }}"}
    assert action["inputs"]["token"].get("required") is False


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
    assert not is_inline_copy({**inline, "id": "other"})
    assert not is_inline_copy("not a dict")
    assert is_action_call(_site())
    assert not is_action_call(inline)
    assert not is_action_call({"uses": "actions/checkout@v7"})
    assert not is_action_call("not a dict")


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
