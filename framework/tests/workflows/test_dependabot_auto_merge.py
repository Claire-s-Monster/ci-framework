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


def test_job_gate_has_all_three_clauses():
    condition = " ".join(str(job()["if"]).split())
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in condition
    assert "github.actor == 'dependabot[bot]'" in condition
    assert (
        "github.event.pull_request.head.repo.full_name == github.repository"
        in condition
    )


def test_concurrency_is_keyed_on_pr_number():
    concurrency = load()["concurrency"]
    assert "github.workflow" not in concurrency["group"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is True


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


def test_no_run_block_interpolates_expressions():
    offenders = [
        s.get("name") for s in steps() if "run" in s and has_interpolation(s["run"])
    ]
    assert not offenders, offenders


def test_merge_step_uses_auto():
    merge = [s for s in steps() if "gh pr merge" in s.get("run", "")]
    assert len(merge) == 1
    assert "--auto" in merge[0]["run"]
    assert '--"$MERGE_METHOD"' in merge[0]["run"]
    assert merge[0]["env"]["MERGE_METHOD"] == "${{ inputs.merge-method }}"
    assert "Allow auto-merge" in merge[0]["run"]


def test_approve_step_is_gated_on_input_and_eligibility():
    approve = [s for s in steps() if "gh pr review --approve" in s.get("run", "")]
    assert len(approve) == 1
    assert "inputs.approve" in approve[0]["if"]
    assert "eligible == 'true'" in approve[0]["if"]


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
    assert "steps.app-token.outputs.token" in meta["with"]["github-token"]
