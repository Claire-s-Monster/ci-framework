"""Drift guard: inline "Verify CI_BOT_TOKEN is valid" copies match the action.

`.github/actions/verify-ci-bot-token/action.yml` is the canonical copy of the
CI_BOT_TOKEN preflight (#355, #482). Until a release tag contains it, the six
inline copies in reusable-ci.yml and reusable-security.yml (sast-semgrep,
sast-codeql, scorecard-token-preflight) cannot use it: a reusable workflow
cannot reference `./` actions (#262) and the pinned remote form needs a tag.
So this guard keeps every inline copy byte-identical to the action in the
meantime, which stops the copies drifting apart.

This guard enforces, for every `*.yml` / `*.yaml` workflow:

  * every step named like the preflight with `id: token-preflight` has a `run`
    equal to the action's, and no keys beyond name, id, env and run;
  * its `env` has the same keys as the action's, with `inputs.token` replaced
    by `secrets.CI_BOT_TOKEN` (a composite cannot read the secrets context);
  * the action declares every output the workflows consume through
    `steps.token-preflight.outputs.*`, wired to the step of the same id.

PHASE 2 (after the release tag exists): the call sites switch to
`uses: Claire-s-Monster/ci-framework/.github/actions/verify-ci-bot-token@vX.Y.Z`.
This module should then be inverted to assert that NO inline copy remains and
that every call site is pinned to a release tag.

Walk-the-tree guards can pass vacuously, hence the floor and the classifier
self-tests below, which run the exact helpers the real tests use.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from framework.tests.workflows.test_ci_bot_token_preflight import (
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
ALLOWED_STEP_KEYS = frozenset({"name", "id", "env", "run"})
INPUT_TOKEN_REFERENCE = "inputs.token"  # pragma: allowlist secret
SECRET_TOKEN_REFERENCE = "secrets.CI_BOT_TOKEN"  # pragma: allowlist secret

# 3 jobs (sast-semgrep, sast-codeql, scorecard-token-preflight) in each of
# reusable-ci.yml and reusable-security.yml. Equals the live count by design:
# removing a copy is deliberate and updates this constant in the same commit.
MINIMUM_EXPECTED_COPIES = 6


def workflow_yaml_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml` and `*.yaml` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def is_preflight_copy(step: object) -> bool:
    """True for a step named like the preflight and carrying its fixed id."""
    return (
        isinstance(step, dict)
        and step.get("name") == PREFLIGHT_STEP_NAME
        and step.get("id") == PREFLIGHT_STEP_ID
    )


def inline_copies() -> list[tuple[str, dict]]:
    """(file:job label, step) of every inline preflight copy in every workflow."""
    return [
        (f"{path.name}:{job_id}", step)
        for path in workflow_yaml_files()
        for job_id, job in load_jobs(path).items()
        for step in job_steps(job)
        if is_preflight_copy(step)
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


def expected_env(action_env: object) -> dict:
    """The action's env as an inline copy must spell it (secret, not input)."""
    if not isinstance(action_env, dict):
        return {}
    return {
        key: str(value).replace(INPUT_TOKEN_REFERENCE, SECRET_TOKEN_REFERENCE)
        for key, value in action_env.items()
    }


def copy_problems(step: dict, canonical: dict) -> list[str]:
    """Everything that makes an inline copy differ from the action's step."""
    problems: list[str] = []
    if step.get("run") != canonical.get("run"):
        problems.append("run differs from the action's run")
    if step.get("env") != expected_env(canonical.get("env")):
        problems.append("env differs from the action's env (inputs.token -> secret)")
    extra = sorted(set(step) - ALLOWED_STEP_KEYS)
    if extra:
        problems.append(f"unexpected keys {extra}")
    return problems


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


def test_walk_finds_the_expected_number_of_inline_copies():
    found = inline_copies()
    assert len(found) >= MINIMUM_EXPECTED_COPIES, (
        f"walk found {len(found)} inline preflight copies, expected at least "
        f"{MINIMUM_EXPECTED_COPIES}; the glob or matcher may be broken"
    )


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


def test_every_inline_copy_matches_the_action():
    canonical = action_step(load_action())
    failures = [
        f"{label}: {problem}"
        for label, step in inline_copies()
        for problem in copy_problems(step, canonical)
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


def _copy(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "env": {"CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"},
        "run": _canonical()["run"],
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


def test_selftest_matching_copy_is_not_flagged():
    assert copy_problems(_copy(), _canonical()) == []


def test_selftest_single_changed_character_in_run_is_flagged():
    changed = _canonical()["run"].replace("exit 0", "exit 1")
    problems = copy_problems(_copy(run=changed), _canonical())
    assert problems == ["run differs from the action's run"]


def test_selftest_changed_env_is_flagged():
    wrong_value = _copy(env={"CI_BOT_TOKEN": "${{ inputs.token }}"})
    wrong_key = _copy(env={"OTHER": "${{ secrets.CI_BOT_TOKEN }}"})
    extra_key = _copy(env={**_copy()["env"], "EXTRA": "x"})
    for step in (wrong_value, wrong_key, extra_key):
        assert any("env differs" in p for p in copy_problems(step, _canonical()))


def test_selftest_extra_step_keys_are_flagged():
    for key in ("if", "continue-on-error", "shell"):
        problems = copy_problems(_copy(**{key: "x"}), _canonical())
        assert any("unexpected keys" in problem for problem in problems), key


def test_selftest_copy_matcher_requires_name_and_id():
    assert is_preflight_copy(_copy())
    assert not is_preflight_copy(_copy(id="other"))
    assert not is_preflight_copy(_copy(name="Something else"))
    assert not is_preflight_copy("not a dict")


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


def test_selftest_expected_env_swaps_input_for_secret():
    assert expected_env({"CI_BOT_TOKEN": "${{ inputs.token }}"}) == {
        "CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"
    }
    assert expected_env(None) == {}
