"""Guards for reusable-dependabot-auto-merge.yml.

The workflow runs with write tokens on Dependabot PRs, so the security-relevant
shape is pinned: pull_request only, an author+actor+same-repo gate, no checkout,
and no `${{ }}` expression inside any `run:` script.

The negative checks (no checkout, no interpolation) pass trivially on an empty
parse, so a non-vacuity test asserts steps and run blocks were actually found.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "reusable-dependabot-auto-merge.yml"
EXPR_RE = re.compile(r"\$\{\{")


def load() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "workflow did not parse as a mapping"
    return doc


def on_block(doc: dict) -> dict:
    # PyYAML parses the bare key `on` as boolean True.
    block = doc.get("on", doc.get(True))
    assert isinstance(block, dict), "no `on:` mapping found"
    return block


def job() -> dict:
    jobs = load()["jobs"]
    assert len(jobs) == 1, "expected exactly one job"
    return next(iter(jobs.values()))


def steps() -> list[dict]:
    return job()["steps"]


def run_blocks() -> list[str]:
    return [s["run"] for s in steps() if "run" in s]


def has_interpolation(run_body: str) -> bool:
    return EXPR_RE.search(run_body) is not None


def test_parse_is_not_vacuous():
    assert len(steps()) > 0
    assert len(run_blocks()) > 0
    assert has_interpolation('echo "${{ inputs.x }}"')
    assert not has_interpolation('echo "$X"')


def test_is_workflow_call_only():
    assert set(on_block(load())) == {"workflow_call"}


def test_has_no_top_level_permissions():
    assert "permissions" not in load()


def test_inputs_names_types_and_defaults():
    inputs = on_block(load())["workflow_call"]["inputs"]
    assert set(inputs) == {
        "merge-method",
        "approve",
        "include-major",
        "require-app-token",
    }
    assert inputs["require-app-token"]["type"] == "boolean"
    assert inputs["require-app-token"]["default"] is False
    assert inputs["require-app-token"]["required"] is False
    assert inputs["merge-method"]["type"] == "string"
    assert inputs["merge-method"]["default"] == "squash"
    assert inputs["approve"]["type"] == "boolean"
    assert inputs["approve"]["default"] is True
    assert inputs["include-major"]["type"] == "boolean"
    assert inputs["include-major"]["default"] is False


def test_secrets_are_optional():
    secrets = on_block(load())["workflow_call"]["secrets"]
    assert set(secrets) == {"APP_CLIENT_ID", "APP_PRIVATE_KEY"}
    for secret in secrets.values():
        assert secret["required"] is False


def step_index(predicate) -> int:
    for index, step in enumerate(steps()):
        if predicate(step):
            return index
    raise AssertionError("no step matched")


GATE_CLAUSES = {
    "github.event.pull_request.user.login == 'dependabot[bot]'",
    "github.actor == 'dependabot[bot]'",
    "github.triggering_actor == 'dependabot[bot]'",
    "github.event.pull_request.head.repo.full_name == github.repository",
}


def gate_clauses(condition: str) -> set[str]:
    """Normalise whitespace, reject `||`, return the `&&`-separated clauses."""
    normalised = " ".join(str(condition).split())
    assert "||" not in normalised, normalised
    return {clause.strip() for clause in normalised.split("&&")}


def test_job_gate_has_exactly_author_actor_triggering_actor_and_same_repo():
    assert gate_clauses(job()["if"]) == GATE_CLAUSES


def test_gate_parser_rejects_or_and_clause_changes():
    base = " && ".join(sorted(GATE_CLAUSES))
    assert gate_clauses(base) == GATE_CLAUSES
    assert gate_clauses(f"  {base.replace(' && ', chr(10) + '&& ')}") == GATE_CLAUSES
    assert gate_clauses(f"{base} && true") != GATE_CLAUSES
    dropped = " && ".join(sorted(GATE_CLAUSES)[1:])
    assert gate_clauses(dropped) != GATE_CLAUSES
    try:
        gate_clauses(f"{base} || true")
    except AssertionError:
        pass
    else:
        raise AssertionError("`||` was not rejected")


def test_concurrency_is_job_level_keyed_on_pr_number():
    assert "concurrency" not in load(), "workflow-level concurrency displaces runs"
    concurrency = job()["concurrency"]
    assert "github.workflow" not in concurrency["group"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_job_has_timeout():
    assert job()["timeout-minutes"] == 10


def test_first_step_rejects_non_pull_request_events():
    first = steps()[0]
    assert first["env"]["EVENT_NAME"] == "${{ github.event_name }}"
    assert '"$EVENT_NAME" != "pull_request"' in first["run"]
    assert "::error" in first["run"]
    assert "exit 1" in first["run"]


def test_no_step_checks_out_code():
    uses = [str(s["uses"]) for s in steps() if "uses" in s]
    assert uses, "no `uses:` step found"
    assert not [u for u in uses if u.startswith("actions/checkout")]


GIT_FETCH_RE = re.compile(
    r"\bgit\b(?:[ \t]+-{1,2}[^\s;&|]+(?:[ \t]+[^\s;&|-][^\s;&|]*)?)*"
    r"[ \t]+(fetch|checkout|clone|pull|switch|worktree|submodule|remote[ \t]+update)\b"
)
GH_REPO_OPT = r"(?:[ \t]+(?:-R|--repo)(?:[ \t]+|=)[^\s;&|]+)*"
GH_FETCH_RE = re.compile(
    rf"\bgh{GH_REPO_OPT}[ \t]+(?:pr[ \t]+checkout|repo[ \t]+clone)\b"
)


def test_git_fetch_regex_handles_global_options():
    positives = (
        "git fetch",
        "git -C d fetch",
        "git -c a=b checkout x",
        "git pull",
        "git -C d switch main",
        "git worktree add x",
        "git submodule update",
        "git remote update",
        "git -C d remote update",
    )
    for positive in positives:
        assert GIT_FETCH_RE.search(positive), positive
    negatives = (
        "echo git; fetch",
        "gitfetch",
        "git log",
        "git\nfetch",
        "git status",
        "echo pull",
        "git remote -v",
    )
    for negative in negatives:
        assert not GIT_FETCH_RE.search(negative), negative


def test_gh_checkout_and_clone_regex_self_test():
    positives = (
        "gh pr checkout 1",
        "gh  repo clone o/r",
        "gh -R o/r pr checkout 1",
        "gh --repo=o/r repo clone o/r",
    )
    for positive in positives:
        assert GH_FETCH_RE.search(positive), positive
    for negative in ("gh pr view 1", "gh pr merge --auto x", "echo checkout"):
        assert not GH_FETCH_RE.search(negative), negative


def test_no_run_block_uses_gh_to_fetch_code():
    scanned = run_blocks()
    assert len(scanned) > 0, "no run blocks scanned"
    offenders = [r for r in scanned if GH_FETCH_RE.search(r)]
    assert not offenders, offenders


def test_no_run_block_fetches_code_with_git():
    scanned = run_blocks()
    assert len(scanned) > 0, "no run blocks scanned"
    offenders = [r for r in scanned if GIT_FETCH_RE.search(r)]
    assert not offenders, offenders
    assert GIT_FETCH_RE.search("git  checkout main")
    assert GIT_FETCH_RE.search("git fetch origin")
    assert not GIT_FETCH_RE.search("echo gitfetch; gh pr view")


def test_no_run_block_interpolates_expressions():
    offenders = [
        s.get("name") for s in steps() if "run" in s and has_interpolation(s["run"])
    ]
    assert not offenders, offenders


MERGE_CALL_RE = re.compile(rf"\bgh{GH_REPO_OPT}[ \t]+pr[ \t]+merge\b[^\n;&|]*")
AUTO_FLAG_RE = re.compile(r"(?<![\w-])--auto(?![\w-])")
ENABLE_ALLOWED_FLAGS = frozenset({"--auto", '--"$MERGE_METHOD"', "--match-head-commit"})
DISARM_ALLOWED_FLAGS = frozenset({"--disable-auto"})


def has_only_allowed_flags(call: str, allowed: frozenset[str]) -> bool:
    """No `-`-prefixed token may remain once the exact known flags are removed."""
    return all(not t.startswith("-") or t in allowed for t in call.split())


def assert_only_auto_enable_or_disarm_merges(runs: list[str]) -> None:
    """Every `gh pr merge` is the pinned `--auto` enable or the `--disable-auto`."""
    calls = [call for run in runs for call in MERGE_CALL_RE.findall(run)]
    enables = [
        c
        for c in calls
        if AUTO_FLAG_RE.search(c)
        and "--disable-auto" not in c
        and '--match-head-commit "$HEAD_SHA"' in c
        and c.startswith("gh pr merge ")
        and has_only_allowed_flags(c, ENABLE_ALLOWED_FLAGS)
    ]
    disarms = [
        c
        for c in calls
        if "--disable-auto" in c
        and not AUTO_FLAG_RE.search(c)
        and c.startswith("gh pr merge ")
        and has_only_allowed_flags(c, DISARM_ALLOWED_FLAGS)
    ]
    others = [c for c in calls if c not in enables and c not in disarms]
    assert not others, f"unexpected gh pr merge invocations: {others}"
    assert len(enables) == 1, enables
    assert len(disarms) == 1, disarms


def test_every_merge_call_is_auto_enable_or_disarm():
    assert_only_auto_enable_or_disarm_merges(run_blocks())


def test_merge_call_asserter_rejects_extra_and_unpinned_calls():
    enable = (
        'gh pr merge --auto --"$MERGE_METHOD" --match-head-commit "$HEAD_SHA" "$PR_URL"'
    )
    disarm = 'gh pr merge --disable-auto "$PR_URL"'
    assert_only_auto_enable_or_disarm_merges([f"if ! {enable}; then\nfi", disarm])
    for flag in ("--admin", "--delete-branch"):
        with pytest.raises(AssertionError):
            assert_only_auto_enable_or_disarm_merges(
                [enable.replace("--auto", f"--auto {flag}"), disarm]
            )
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges(
            [enable, disarm.replace("--disable-auto", "--disable-auto --admin")]
        )
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges(
            [enable, disarm, 'gh -R o/r pr merge --squash "$PR_URL"']
        )
    extra = 'gh pr merge --squash "$PR_URL"'
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges([enable, disarm, extra])
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges([enable, f"{disarm}\n{extra}"])
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges(
            ['gh pr merge --auto --squash "$PR_URL"', disarm]
        )
    with pytest.raises(AssertionError):
        assert_only_auto_enable_or_disarm_merges([enable])
    for chained in (
        f'{disarm}; gh pr merge "$PR_URL"',
        f'{disarm} && gh pr merge "$PR_URL"',
        f'{disarm} || gh pr merge --admin "$PR_URL"',
        f'{disarm} | gh pr merge "$PR_URL"',
        f'{disarm} & gh pr merge "$PR_URL"',
    ):
        with pytest.raises(AssertionError, match="unexpected"):
            assert_only_auto_enable_or_disarm_merges([enable, chained])


def test_merge_step_uses_auto():
    merge = [s for s in steps() if "gh pr merge --auto" in s.get("run", "")]
    assert len(merge) == 1
    assert "--auto" in merge[0]["run"]
    assert '--"$MERGE_METHOD"' in merge[0]["run"]
    assert merge[0]["env"]["MERGE_METHOD"] == "${{ inputs.merge-method }}"
    assert "Allow auto-merge" in merge[0]["run"]
    assert '--match-head-commit "$HEAD_SHA"' in merge[0]["run"]
    assert merge[0]["env"]["HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"


def test_approve_step_is_gated_on_input_and_eligibility():
    approve = [s for s in steps() if "/reviews" in s.get("run", "")]
    assert len(approve) == 1
    assert "inputs.approve" in approve[0]["if"]
    assert "eligible == 'true'" in approve[0]["if"]


def test_approve_uses_reviews_api_pinned_to_head_sha():
    approve = next(s for s in steps() if "/reviews" in s.get("run", ""))
    run = approve["run"]
    assert "gh api --method POST" in run
    assert "event=APPROVE" in run
    assert 'commit_id="$HEAD_SHA"' in run
    assert approve["env"]["HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert approve["env"]["REPO"] == "${{ github.repository }}"
    assert approve["env"]["PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert not [r for r in run_blocks() if "gh pr review" in r]


def test_mint_runs_in_app_mode_after_decide_before_disarm():
    decide = step_index(lambda s: s.get("id") == "decide")
    mode = step_index(lambda s: s.get("id") == "mode")
    mint = step_index(lambda s: s.get("id") == "app-token")
    disarm = step_index(lambda s: "--disable-auto" in s.get("run", ""))
    assert mode < mint
    assert decide < mint < disarm
    assert if_matches(steps()[mint]["if"], MINT_IF)
    assert if_matches(steps()[mode]["if"], MODE_IF)


MODE_IF = "${{ !cancelled() && steps.trigger.outcome == 'success' }}"
MINT_IF = (
    "${{ !cancelled() && steps.trigger.outcome == 'success' "
    "&& steps.mode.outputs.app == 'true' }}"
)


def if_matches(condition: object, expected: str) -> bool:
    """Exact equality after whitespace normalisation."""
    return " ".join(str(condition).split()) == " ".join(expected.split())


def test_if_matcher_rejects_mutated_conditions():
    assert if_matches(f"  {MINT_IF}\n", MINT_IF)
    assert not if_matches(MINT_IF.replace(" }}", " || true }}"), MINT_IF)
    assert not if_matches(
        "${{ !cancelled() && steps.mode.outputs.app == 'true' }}", MINT_IF
    )
    assert not if_matches("${{ !cancelled() }}", MODE_IF)
    assert not if_matches(MODE_IF.replace(" }}", " || true }}"), MODE_IF)


DISARM_IF = "${{ !cancelled() && steps.decide.outputs.eligible != 'true' }}"


def test_disarm_condition_matcher_rejects_mutated_conditions():
    assert if_matches(f"  {DISARM_IF}\n", DISARM_IF)
    old = "steps.decide.outputs.eligible != 'true'"
    assert not if_matches(old, DISARM_IF)
    assert not if_matches("${{ !cancelled() }}", DISARM_IF)
    assert not if_matches(
        "${{ !cancelled() || steps.decide.outputs.eligible != 'true' }}", DISARM_IF
    )
    assert not if_matches(DISARM_IF.replace(" }}", " && false }}"), DISARM_IF)
    assert not if_matches(DISARM_IF.replace(" }}", " || true }}"), DISARM_IF)
    assert not if_matches(DISARM_IF.replace("!cancelled()", "always()"), DISARM_IF)
    assert not if_matches(
        "${{ always() && steps.decide.outputs.eligible != 'true' }}", DISARM_IF
    )


ARMED_QUERY = (
    'armed=$(gh pr view "$PR_URL" --json autoMergeRequest '
    "--jq '.autoMergeRequest != null')"
)
ARMED_OPENER = 'if [ "$armed" = "true" ]; then'
DISARM_CALL = "gh pr merge --disable-auto"


def assert_disarm_gated_on_boolean_armed(run: str) -> None:
    """`armed` must be a jq boolean and the disarm must run only when it is true."""
    lines = normalised_lines(run)
    assert ARMED_QUERY in lines, "armed is not the `!= null` boolean jq expression"
    assert ARMED_OPENER in lines, 'no `[ "$armed" = "true" ]` branch'
    assert lines.index(ARMED_QUERY) < lines.index(ARMED_OPENER), "armed set too late"
    body = branch_body(lines, ARMED_OPENER)
    assert any(DISARM_CALL in line for line in body), "disarm is outside armed branch"
    assert run.count(DISARM_CALL) == 1, "disarm call appears outside the armed branch"


def test_armed_assertion_rejects_inverted_or_non_boolean_checks():
    good = (
        f"{ARMED_QUERY}\n"
        f"{ARMED_OPENER}\n"
        f'  if ! {DISARM_CALL} "$PR_URL"; then\n'
        "    exit 1\n"
        "  fi\n"
        "fi\n"
    )
    assert_disarm_gated_on_boolean_armed(good)
    for bad in (
        good.replace('= "true"', '= "false"'),
        good.replace(".autoMergeRequest != null", ".autoMergeRequest"),
        good.replace(".autoMergeRequest != null", ".autoMergeRequest == null"),
        good.replace(
            f'  if ! {DISARM_CALL} "$PR_URL"; then\n    exit 1\n  fi\n',
            f'  echo x\nfi\n{DISARM_CALL} "$PR_URL"\nif true; then\n  :\n',
        ),
    ):
        with pytest.raises(AssertionError):
            assert_disarm_gated_on_boolean_armed(bad)


def test_disarm_step_runs_for_ineligible_after_mint_before_approve_and_merge():
    decide = step_index(lambda s: s.get("id") == "decide")
    disarm = step_index(lambda s: "--disable-auto" in s.get("run", ""))
    mint = step_index(lambda s: s.get("id") == "app-token")
    approve = step_index(lambda s: "/reviews" in s.get("run", ""))
    merge = step_index(lambda s: "gh pr merge --auto" in s.get("run", ""))
    assert decide < mint < disarm < approve < merge
    step = steps()[disarm]
    assert if_matches(step["if"], DISARM_IF), step["if"]
    assert (
        step["env"]["GH_TOKEN"]
        == "${{ steps.app-token.outputs.token || github.token }}"
    )
    assert_disarm_gated_on_boolean_armed(step["run"])
    assert "::notice title=Auto-merge disarmed" in step["run"]
    assert "::error title=Could not disarm auto-merge" in step["run"]
    assert "exit 1" in step["run"]


def test_mode_step_reads_require_app_through_env_and_fails_closed():
    mode = next(s for s in steps() if s.get("id") == "mode")
    assert mode["env"]["REQUIRE_APP"] == "${{ inputs.require-app-token }}"
    assert "inputs.require-app-token" not in mode["run"]
    assert not has_interpolation(mode["run"])
    lines = normalised_lines(mode["run"])
    body = branch_body(lines, 'if [ "$REQUIRE_APP" = "true" ]; then')
    assert any("::error title=App token required::" in line for line in body)
    assert top_level_lines(body)[-1:] == ["exit 1"], body
    assert "app=false" not in " ".join(body)


# --- behavioural: execute the real "Select token mode" script -----------------

BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(BASH is None, reason="bash is not available")
REQUIRE_BRANCH_OPENER = '          if [ "$REQUIRE_APP" = "true" ]; then\n'


def mode_script() -> str:
    run = next(s for s in steps() if s.get("id") == "mode")["run"]
    assert not has_interpolation(run), "mode run: must not contain ${{ }} expressions"
    return run


def run_mode(
    script: str, tmp_path: Path, client_id: str, key: str, require: str
) -> tuple[int, str, list[str]]:
    """Run `script` like GitHub's `bash --noprofile --norc -eo pipefail {0}`."""
    assert BASH is not None
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {
        "APP_CLIENT_ID": client_id,
        "APP_PRIVATE_KEY": key,
        "REQUIRE_APP": require,
        "GITHUB_OUTPUT": str(out),
        "PATH": os.environ["PATH"],
    }
    proc = subprocess.run(  # noqa: S603
        [BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return proc.returncode, proc.stdout, out.read_text(encoding="utf-8").splitlines()


@requires_bash
@pytest.mark.parametrize("require", ["true", "false"])
def test_mode_script_both_secrets_selects_app(tmp_path: Path, require: str):
    code, _, outputs = run_mode(mode_script(), tmp_path, "id", "key", require)
    assert code == 0
    assert outputs == ["app=true"]


@requires_bash
def test_mode_script_no_secrets_not_required_selects_token(tmp_path: Path):
    code, _, outputs = run_mode(mode_script(), tmp_path, "", "", "false")
    assert code == 0
    assert outputs == ["app=false"]


@requires_bash
def test_mode_script_no_secrets_required_fails_closed(tmp_path: Path):
    code, stdout, outputs = run_mode(mode_script(), tmp_path, "", "", "true")
    assert code != 0
    assert "title=App token required" in stdout
    assert not any(line.startswith("app=") for line in outputs)


@requires_bash
@pytest.mark.parametrize("require", ["true", "false"])
@pytest.mark.parametrize(
    ("client_id", "key", "missing"),
    [("", "key", "APP_CLIENT_ID"), ("id", "", "APP_PRIVATE_KEY")],
)
def test_mode_script_partial_secrets_fail(
    tmp_path: Path, client_id: str, key: str, missing: str, require: str
):
    code, stdout, outputs = run_mode(mode_script(), tmp_path, client_id, key, require)
    assert code != 0
    assert "title=App credentials incomplete" in stdout
    assert f"{missing} is not set" in stdout
    assert not any(line.startswith("app=") for line in outputs)


@requires_bash
def test_mode_harness_catches_early_exit_zero_in_require_branch(tmp_path: Path):
    script = mode_script()
    assert script.count(REQUIRE_BRANCH_OPENER.strip()) == 1
    indent = " " * 4
    mutated = script.replace(
        REQUIRE_BRANCH_OPENER.strip() + "\n",
        REQUIRE_BRANCH_OPENER.strip() + f"\n{indent}exit 0\n",
    )
    assert mutated != script
    code, _, _ = run_mode(mutated, tmp_path, "", "", "true")
    assert code == 0, "harness failed to observe the injected `exit 0`"


APP_TEMPLATE = (
    REPO_ROOT
    / "templates"
    / "github"
    / "workflows"
    / "dependabot-auto-merge-app-template.yml"
)
TOKEN_TEMPLATE = (
    REPO_ROOT
    / "templates"
    / "github"
    / "workflows"
    / "dependabot-auto-merge-template.yml"
)


def template_with(path: Path) -> dict:
    assert path.is_file(), f"{path} is missing"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(iter(doc["jobs"].values())).get("with") or {}


def test_app_template_requires_app_token_and_token_template_does_not():
    assert template_with(APP_TEMPLATE).get("require-app-token") is True
    assert "require-app-token" not in template_with(TOKEN_TEMPLATE)


def test_metadata_uses_github_token_not_app_token():
    meta = next(s for s in steps() if s.get("id") == "metadata")
    assert meta["with"]["github-token"] == "${{ github.token }}"


APP_TOKEN_EXPR = "${{ steps.app-token.outputs.token || github.token }}"


APP_IDENTITY_STEPS = (
    "Disarm auto-merge for ineligible update",
    "Require base-branch status checks",
    "Approve pull request",
    "Enable auto-merge",
)


def assert_app_identity_steps_pin_token(step_list: list[dict]) -> None:
    """Each targeted step exists exactly once and carries the App token expression."""
    names = [s.get("name") for s in step_list]
    for name in APP_IDENTITY_STEPS:
        assert names.count(name) == 1, f"expected exactly one {name!r} step"
        step = step_list[names.index(name)]
        assert step["env"]["GH_TOKEN"] == APP_TOKEN_EXPR, name


def test_app_identity_steps_use_app_token_with_github_token_fallback():
    assert_app_identity_steps_pin_token(steps())


def test_app_identity_token_asserter_rejects_duplicates_and_missing():
    good = [
        {"name": n, "env": {"GH_TOKEN": APP_TOKEN_EXPR}} for n in APP_IDENTITY_STEPS
    ]
    assert_app_identity_steps_pin_token(good)
    duplicated = [
        {"name": APP_IDENTITY_STEPS[0], "env": {"GH_TOKEN": "${{ github.token }}"}},
        *good,
    ]
    with pytest.raises(AssertionError, match="exactly one"):
        assert_app_identity_steps_pin_token(duplicated)
    with pytest.raises(AssertionError, match="exactly one"):
        assert_app_identity_steps_pin_token(good[1:])
    wrong = [dict(s) for s in good]
    wrong[3] = {"name": APP_IDENTITY_STEPS[3], "env": {"GH_TOKEN": "x"}}
    with pytest.raises(AssertionError):
        assert_app_identity_steps_pin_token(wrong)


# --- no bare github.token outside metadata (#462) ----------------------------

BARE_TOKEN_RE = re.compile(r"\$\{\{\s*github\.token\s*\}\}")
METADATA_STEP = "Fetch Dependabot metadata"
METADATA_USES = "dependabot/fetch-metadata@"


def is_metadata_step(step: dict) -> bool:
    return step.get("id") == "metadata" and str(step.get("uses", "")).startswith(
        METADATA_USES
    )


def bare_github_token_steps(step_list: list[dict]) -> list[str]:
    """Names of steps (other than metadata) whose env/with is a bare github.token."""
    offenders = []
    for step in step_list:
        if is_metadata_step(step):
            continue
        values = [*(step.get("env") or {}).values(), *(step.get("with") or {}).values()]
        if any(BARE_TOKEN_RE.fullmatch(str(v).strip()) for v in values):
            offenders.append(str(step.get("name")))
    return offenders


def test_only_metadata_uses_bare_github_token_462():
    step_list = steps()
    assert bare_github_token_steps(step_list) == []
    assert len([s for s in step_list if is_metadata_step(s)]) == 1
    token_steps = [
        s
        for s in step_list
        if APP_TOKEN_EXPR
        in [*(s.get("env") or {}).values(), *(s.get("with") or {}).values()]
    ]
    assert len(token_steps) == len(APP_IDENTITY_STEPS)


def test_bare_github_token_detector_fires_on_synthetic_step():
    bare = {"name": "X", "env": {"GH_TOKEN": "${{ github.token }}"}}
    spaced = {"name": "Y", "with": {"github-token": "${{ github.token}}"}}
    meta = {
        "name": METADATA_STEP,
        "id": "metadata",
        "uses": f"{METADATA_USES}abc  # v3",
        "with": {"github-token": "${{ github.token }}"},
    }
    ok = {"name": "Z", "env": {"GH_TOKEN": APP_TOKEN_EXPR}}
    assert bare_github_token_steps([bare]) == ["X"]
    assert bare_github_token_steps([spaced]) == ["Y"]
    assert bare_github_token_steps([meta, ok]) == []
    impostor = {
        "name": METADATA_STEP,
        "id": "other",
        "uses": f"{METADATA_USES}abc",
        "with": {"github-token": "${{ github.token }}"},
    }
    no_uses = {
        "name": METADATA_STEP,
        "id": "metadata",
        "env": {"GH_TOKEN": "${{ github.token }}"},
    }
    assert bare_github_token_steps([meta, impostor]) == [METADATA_STEP]
    assert bare_github_token_steps([meta, no_uses]) == [METADATA_STEP]


def test_required_checks_step_precedes_approve_and_merge():
    check = step_index(lambda s: "required_status_checks" in s.get("run", ""))
    approve = step_index(lambda s: "/reviews" in s.get("run", ""))
    merge = step_index(lambda s: "gh pr merge --auto" in s.get("run", ""))
    assert check < approve < merge
    step = steps()[check]
    run = step["run"]
    assert "eligible == 'true'" in step["if"]
    assert 'gh api "repos/$REPO/branches/$BASE_REF"' in run
    assert 'gh api "repos/$REPO/rules/branches/$BASE_REF"' in run
    assert "--jq" in run
    assert "::error title=No required checks" in run
    assert "::error title=Cannot verify required checks" in run
    assert "exit 1" in run
    assert_refusal_logic(run, "repos/$REPO")


def normalised_lines(run: str) -> list[str]:
    return [" ".join(line.split()) for line in run.splitlines() if line.strip()]


def opens_if(line: str) -> bool:
    """A multi-line `if ...; then` opener (a one-line `if ...; fi` is not)."""
    return line.startswith("if ") and not line.endswith(" fi")


def branch_body(lines: list[str], opener: str) -> list[str]:
    """Lines of the `if` branch that starts with `opener`, up to its matching `fi`."""
    starts = [i for i, line in enumerate(lines) if line.startswith(opener)]
    assert len(starts) == 1, f"expected exactly one line starting {opener!r}"
    assert "||" not in lines[starts[0]], (
        f"guard opener is neutralised: {lines[starts[0]]!r}"
    )
    body: list[str] = []
    depth = 1
    for line in lines[starts[0] + 1 :]:
        if line == "fi":
            depth -= 1
            if depth == 0:
                return body
        elif opens_if(line):
            depth += 1
        body.append(line)
    raise AssertionError(f"branch {opener!r} is not closed by fi")


def top_level_lines(body: list[str]) -> list[str]:
    """Lines of a branch body that sit at nesting depth 0 (nested ifs dropped)."""
    top: list[str] = []
    depth = 0
    for line in body:
        if line == "fi":
            depth -= 1
        elif opens_if(line):
            depth += 1
        elif depth == 0:
            top.append(line)
    return top


def assert_refusal_logic(run: str, api_prefix: str) -> None:
    """Both API-failure branches and the zero-checks branch must `exit 1`."""
    lines = normalised_lines(run)
    for opener in (
        f'if ! protection=$(gh api "{api_prefix}/branches/$BASE_REF"',
        f'if ! rules=$(gh api "{api_prefix}/rules/branches/$BASE_REF"',
        'if [ "${protection:-0}" -eq 0 ] && [ "${rules:-0}" -eq 0 ]; then',
    ):
        body = branch_body(lines, opener)
        assert body, (opener, "empty branch")
        assert body[-1] == "exit 1", (opener, body)
        assert top_level_lines(body)[-1:] == ["exit 1"], (
            opener,
            "final exit 1 is not at nesting depth 0",
            body,
        )
        assert "exit 0" not in body, (opener, body)


REFUSAL_OPENERS = (
    'if ! protection=$(gh api "repos/$REPO/branches/$BASE_REF" --jq ".x"); then',
    'if ! rules=$(gh api "repos/$REPO/rules/branches/$BASE_REF" --jq ".y"); then',
    'if [ "${protection:-0}" -eq 0 ] && [ "${rules:-0}" -eq 0 ]; then',
)


def refusal_fixture(final: str = "exit 1", prefix: str = "") -> str:
    """A well-formed run script; `prefix` lines go before `final` in branch 3."""
    return (
        f"{REFUSAL_OPENERS[0]}\n  echo x\n  exit 1\nfi\n"
        f"{REFUSAL_OPENERS[1]}\n  echo y\n  exit 1\nfi\n"
        f"{REFUSAL_OPENERS[2]}\n{prefix}  {final}\nfi\n"
    )


def test_refusal_asserter_detects_a_neutralised_guard():
    good = refusal_fixture()
    assert_refusal_logic(good, "repos/$REPO")
    opener = REFUSAL_OPENERS[2]
    assert branch_body(normalised_lines(good), opener)[-1] == "exit 1"

    neutralised = refusal_fixture(final="exit 0")
    assert branch_body(normalised_lines(neutralised), opener)[-1] != "exit 1"
    with pytest.raises(AssertionError):
        assert_refusal_logic(neutralised, "repos/$REPO")
    with pytest.raises(AssertionError):
        assert_refusal_logic(refusal_fixture(final="echo done"), "repos/$REPO")
    with pytest.raises(AssertionError):
        assert_refusal_logic(refusal_fixture(final="exit 1\n  exit 0"), "repos/$REPO")


def test_branch_body_tracks_nested_if_depth():
    nested = (
        "if [ a ]; then\n"
        "  if [ b ]; then\n"
        "    echo inner\n"
        "  fi\n"
        "  exit 1\n"
        "fi\n"
        "echo after\n"
    )
    body = branch_body(normalised_lines(nested), "if [ a ]; then")
    assert body[-1] == "exit 1"
    assert "echo after" not in body
    assert top_level_lines(body) == ["exit 1"]
    assert top_level_lines(["if [ x ]; then", "exit 1", "fi"]) == []


def test_refusal_asserter_rejects_exit_1_only_inside_nested_if():
    multiline = refusal_fixture(
        final="echo done", prefix="  if [ x ]; then\n    exit 1\n  fi\n"
    )
    with pytest.raises(AssertionError):
        assert_refusal_logic(multiline, "repos/$REPO")
    oneline = refusal_fixture(final="if [ x ]; then exit 1; fi")
    with pytest.raises(AssertionError):
        assert_refusal_logic(oneline, "repos/$REPO")
    unconditional_last = refusal_fixture(final="exit 1", prefix="  if [ x ]; then\n")
    with pytest.raises(AssertionError):
        assert_refusal_logic(unconditional_last, "repos/$REPO")


def test_refusal_asserter_rejects_or_true_inside_substitution():
    bad = (
        'if ! protection=$(gh api "repos/$REPO/branches/$BASE_REF" --jq ".x" || true); then\n'
        '  echo "::error title=Cannot verify required checks::x"\n'
        "  exit 1\n"
        "fi\n"
    )
    with pytest.raises(AssertionError, match="neutralised"):
        assert_refusal_logic(bad, "repos/$REPO")


def test_major_requires_opt_in():
    decide = next(s for s in steps() if s.get("id") == "decide")
    assert decide["env"]["INCLUDE_MAJOR"] == "${{ inputs.include-major }}"
    run = decide["run"]
    assert "version-update:semver-patch" in run
    assert "version-update:semver-minor" in run
    assert '"$INCLUDE_MAJOR" = "true"' in run
    assert "::notice" in run
    assert "GITHUB_STEP_SUMMARY" in run


# --- push runs after a github.token merge (#455) ------------------------------

WARN_STEP = "Warn: no push runs after merge"
ENABLE_STEP = "Enable auto-merge"
APP_CLAUSE = "steps.mode.outputs.app != 'true'"
WARNING_PREFIX = "::warning title=No push runs after merge::"


def assert_warn_step_precedes_enable(step_list: list[dict]) -> None:
    """The warn step sits directly before Enable and fires exactly when it does,
    minus App mode. The warning is one static echo."""
    names = [s.get("name") for s in step_list]
    assert names.count(ENABLE_STEP) == 1, f"expected one {ENABLE_STEP!r} step"
    assert names.count(WARN_STEP) == 1, f"expected one {WARN_STEP!r} step"
    enable = names.index(ENABLE_STEP)
    assert names.index(WARN_STEP) == enable - 1, (
        "warn step is not directly before Enable"
    )
    warn = step_list[enable - 1]
    condition = " ".join(str(warn.get("if", "")).split())
    base = " ".join(str(step_list[enable]["if"]).split())
    guarded = f"({base})" if "||" in base else base
    assert condition == f"{guarded} && {APP_CLAUSE}", (
        f"warn if: {condition!r} is not exactly the Enable condition and {APP_CLAUSE!r}"
    )
    run = warn.get("run", "")
    assert run.count(WARNING_PREFIX) == 1, "expected exactly one push-runs warning"
    assert "${{" not in run, "warning must be static"
    assert not warn.get("env"), "warn step must take no env"


def test_warn_step_precedes_enable_and_matches_its_condition():
    assert_warn_step_precedes_enable(steps())


def _fixture_steps(
    *,
    warn: bool = True,
    between: bool = False,
    clause: bool = True,
    base: bool = True,
    text: bool = True,
) -> list[dict]:
    enable_if = "steps.decide.outputs.eligible == 'true'"
    condition = enable_if if base else "always()"
    if clause:
        condition += f" && {APP_CLAUSE}"
    warn_step = {
        "name": WARN_STEP,
        "if": condition,
        "run": f'echo "{WARNING_PREFIX}x"' if text else 'echo "x"',
    }
    out: list[dict] = [{"name": "Select token mode"}]
    if warn:
        out.append(warn_step)
    if between:
        out.append({"name": "Other"})
    out.append({"name": ENABLE_STEP, "if": enable_if})
    return out


def test_warn_step_asserter_requires_parentheses_around_or_conditions():
    base = "a || b"
    for condition, ok in (
        (f"{base} && {APP_CLAUSE}", False),
        (f"({base}) && {APP_CLAUSE}", True),
    ):
        fixture = _fixture_steps()
        fixture[1]["if"] = condition
        fixture[2]["if"] = base
        if ok:
            assert_warn_step_precedes_enable(fixture)
        else:
            with pytest.raises(AssertionError, match="not exactly"):
                assert_warn_step_precedes_enable(fixture)


def test_warn_step_asserter_rejects_broken_variants():
    assert_warn_step_precedes_enable(_fixture_steps())
    for broken in (
        {"warn": False},
        {"between": True},
        {"clause": False},
        {"base": False},
        {"text": False},
    ):
        with pytest.raises(AssertionError):
            assert_warn_step_precedes_enable(_fixture_steps(**broken))
    for extra in (" && github.event_name == 'push'", " || always()"):
        widened = _fixture_steps()
        widened[1]["if"] += extra
        with pytest.raises(AssertionError, match="not exactly"):
            assert_warn_step_precedes_enable(widened)
    doubled = _fixture_steps()
    doubled[1]["run"] += f'\necho "{WARNING_PREFIX}y"'
    with pytest.raises(AssertionError, match="exactly one"):
        assert_warn_step_precedes_enable(doubled)
    templated = _fixture_steps()
    templated[1]["run"] += " ${{ github.actor }}"
    with pytest.raises(AssertionError, match="static"):
        assert_warn_step_precedes_enable(templated)


def test_security_template_declares_workflow_dispatch():
    path = REPO_ROOT / "templates" / "github" / "workflows" / "security-template.yml"
    assert path.is_file(), f"{path} is missing"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = doc.get(True) or doc["on"]
    assert {"push", "pull_request", "schedule", "workflow_dispatch"} <= set(on)
    job = next(iter(doc["jobs"].values()))
    assert job["permissions"] == {
        "contents": "read",
        "actions": "read",
        "id-token": "write",  # pragma: allowlist secret
        "security-events": "write",
    }
    assert re.search(
        r"uses: Claire-s-Monster/ci-framework/\.github/workflows/"
        r"reusable-security\.yml@v\d+\.\d+\.\d+\s+#\s*x-release-please-version",
        path.read_text(encoding="utf-8"),
    )


def test_fetch_metadata_is_sha_pinned():
    meta = next(s for s in steps() if s.get("id") == "metadata")
    assert re.fullmatch(r"dependabot/fetch-metadata@[0-9a-f]{40}", meta["uses"])
    assert "github-token" in meta["with"]
