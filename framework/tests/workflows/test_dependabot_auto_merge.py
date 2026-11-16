"""Guards for reusable-dependabot-auto-merge.yml.

The workflow runs with write tokens on Dependabot PRs, so the security-relevant
shape is pinned: pull_request only, an author+actor+same-repo gate, no checkout,
and no `${{ }}` expression inside any `run:` script.

The negative checks (no checkout, no interpolation) pass trivially on an empty
parse, so a non-vacuity test asserts steps and run blocks were actually found.
"""

from __future__ import annotations

import re
from pathlib import Path

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
    assert set(inputs) == {"merge-method", "approve", "include-major"}
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


GIT_FETCH_RE = re.compile(r"\bgit\s+(fetch|checkout|clone)\b")


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


def test_mint_runs_only_when_eligible_and_after_decide():
    decide = step_index(lambda s: s.get("id") == "decide")
    mint = step_index(lambda s: s.get("id") == "app-token")
    assert mint > decide
    condition = steps()[mint]["if"]
    assert "steps.decide.outputs.eligible == 'true'" in condition
    assert "steps.mode.outputs.app == 'true'" in condition


def test_disarm_step_runs_for_ineligible_between_decide_and_mint():
    decide = step_index(lambda s: s.get("id") == "decide")
    disarm = step_index(lambda s: "--disable-auto" in s.get("run", ""))
    mint = step_index(lambda s: s.get("id") == "app-token")
    approve = step_index(lambda s: "/reviews" in s.get("run", ""))
    merge = step_index(lambda s: "gh pr merge --auto" in s.get("run", ""))
    assert decide < disarm < mint
    assert disarm < approve < merge
    step = steps()[disarm]
    assert "steps.decide.outputs.eligible != 'true'" in step["if"]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "autoMergeRequest" in step["run"]
    assert "::notice title=Auto-merge disarmed" in step["run"]
    assert "::error title=Could not disarm auto-merge" in step["run"]
    assert "exit 1" in step["run"]


def test_metadata_uses_github_token_not_app_token():
    meta = next(s for s in steps() if s.get("id") == "metadata")
    assert meta["with"]["github-token"] == "${{ github.token }}"


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


def branch_body(lines: list[str], opener: str) -> list[str]:
    """Lines of the `if` branch that starts with `opener`, up to its `fi`."""
    starts = [i for i, line in enumerate(lines) if line.startswith(opener)]
    assert len(starts) == 1, f"expected exactly one line starting {opener!r}"
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line == "fi":
            return body
        body.append(line)
    raise AssertionError(f"branch {opener!r} is not closed by fi")


def assert_refusal_logic(run: str, api_prefix: str) -> None:
    """Both API-failure branches and the zero-checks branch must `exit 1`."""
    lines = normalised_lines(run)
    for opener in (
        f'if ! protection=$(gh api "{api_prefix}/branches/$BASE_REF"',
        f'if ! rules=$(gh api "{api_prefix}/rules/branches/$BASE_REF"',
        'if [ "${protection:-0}" -eq 0 ] && [ "${rules:-0}" -eq 0 ]; then',
    ):
        body = branch_body(lines, opener)
        assert body[-1] == "exit 1", (opener, body)
        assert "exit 0" not in body, (opener, body)


def test_refusal_asserter_detects_a_neutralised_guard():
    good = (
        'if [ "${protection:-0}" -eq 0 ] && [ "${rules:-0}" -eq 0 ]; then\n'
        '  echo "::error title=No required checks::x"\n'
        "  exit 1\n"
        "fi\n"
    )
    opener = 'if [ "${protection:-0}" -eq 0 ] && [ "${rules:-0}" -eq 0 ]; then'
    assert branch_body(normalised_lines(good), opener)[-1] == "exit 1"
    bad = good.replace("exit 1", "exit 0")
    assert branch_body(normalised_lines(bad), opener)[-1] != "exit 1"


def test_major_requires_opt_in():
    decide = next(s for s in steps() if s.get("id") == "decide")
    assert decide["env"]["INCLUDE_MAJOR"] == "${{ inputs.include-major }}"
    run = decide["run"]
    assert "version-update:semver-patch" in run
    assert "version-update:semver-minor" in run
    assert '"$INCLUDE_MAJOR" = "true"' in run
    assert "::notice" in run
    assert "GITHUB_STEP_SUMMARY" in run


def test_fetch_metadata_is_sha_pinned():
    meta = next(s for s in steps() if s.get("id") == "metadata")
    assert re.fullmatch(r"dependabot/fetch-metadata@[0-9a-f]{40}", meta["uses"])
    assert "github-token" in meta["with"]
