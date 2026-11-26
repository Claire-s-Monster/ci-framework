"""Guard: every job that consumes `secrets.CI_BOT_TOKEN` verifies it first.

Issue #355. `${{ secrets.CI_BOT_TOKEN || github.token }}` falls back only when
the secret is EMPTY. An expired or revoked PAT is still non-empty, so it wins
the `||` and the API rejects it with HTTP 401 (Bad credentials). At the SARIF
sites (`continue-on-error: true`) that failure is silent.

The fix is a preflight step, `Verify CI_BOT_TOKEN is valid`, as the FIRST step
of every job that references the secret. The six SARIF sites in the reusable
workflows call the `verify-ci-bot-token` composite action pinned to a release
tag (`./` references in a reusable workflow resolve against the CALLER's
checkout, #262); three standalone workflows use the local `./` form after a
sparse `.github/actions` checkout, and the two `workflow_call` ones keep an
inline `run:` copy (follow-up).

This guard enforces, for every job in every workflow and workflow template:

  * the job's first step is the preflight (by exact name);
  * an inline preflight passes the token through `env:` and never interpolates
    `${{ ... }}` inside `run:` (script injection); an action call passes it as
    `with.token` and carries no `run:`;
  * an inline preflight probes `/rate_limit` and hard-fails (`exit 1`) on 401;
  * the preflight has neither `continue-on-error` nor `if`, so it can neither
    be swallowed nor skipped.

Like `test_sarif_upload_auth.py`, this module walks `*.yml.template` files too
(a template that consumes the token ships the gap to every consumer) and keeps
its helpers pure so the classifier self-tests exercise the exact code the real
test uses. Walk-the-tree guards can pass vacuously, hence the floor and the
self-tests below.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

PREFLIGHT_STEP_NAME = "Verify CI_BOT_TOKEN is valid"
TOKEN_REFERENCE = re.compile(r"secrets\.CI_BOT_TOKEN\b")
EXPECTED_ENV_VALUE = "${{ secrets.CI_BOT_TOKEN }}"
PREFLIGHT_STEP_ID = "token-preflight"
# The reusable workflows call the composite action at a release tag (a `./`
# reference would resolve against the CALLER's checkout, #262).
ACTION_USES_PREFIX = "Claire-s-Monster/ci-framework/.github/actions/verify-ci-bot-token"
ACTION_USES_PATTERN = re.compile(re.escape(ACTION_USES_PREFIX) + r"@v\d+\.\d+\.\d+")
RUN_NEEDLES = (
    "/rate_limit",
    "401",
    "exit 1",
    "command -v curl",
    "--max-time",
)
# Extra requirements for a preflight whose job uploads SARIF (#482): it also
# probes code-scanning access and publishes the verdict as a step output.
SARIF_RUN_NEEDLES = ("code-scanning/analyses", "use_pat=", "GITHUB_OUTPUT")
# #482: SARIF uploads use the PAT only when the preflight confirmed
# code-scanning access.
USE_PAT_EXPRESSION = "steps.token-preflight.outputs.use_pat"
# Jobs that cannot host the preflight step (scorecard) read it from a job.
NEEDS_USE_PAT = re.compile(r"needs\.([\w-]+)\.outputs\.use_pat == 'true'")
SARIF_ACTION_PREFIXES = (
    "github/codeql-action/upload-sarif@",
    "github/codeql-action/analyze@",
)
SARIF_WORKFLOWS = ("reusable-ci.yml", "reusable-security.yml")
# 2 SAST semgrep + 2 SAST codeql + 2 scorecard uploads (#482).
MINIMUM_EXPECTED_SARIF_SITES = 6

# Jobs that consume the token but must NOT carry the preflight. The Scorecard
# job runs `ossf/scorecard-action` with `publish_results: true`, and the
# scorecard webapp verifies the workflow file itself: the job may only have
# allowlisted `uses:` steps (no `run:`). A preflight there would make the
# verification reject the job. The SAST jobs of the same workflow consume the
# same token and perform the check. See test_scorecard_publish_restrictions.py.
PREFLIGHT_EXEMPT_JOBS: frozenset[tuple[str, str]] = frozenset(
    {
        ("reusable-ci.yml", "scorecard"),
        ("reusable-security.yml", "scorecard"),
    }
)

# The 11 jobs that consume secrets.CI_BOT_TOKEN today (c-cpp-lint no longer
# does once its dead SARIF upload is removed, #354; the pixi lock refresh job
# no longer does once it runs on github.token, #387):
#   reusable-ci.yml          sast-semgrep, sast-codeql, scorecard (exempt)
#   reusable-security.yml    sast-semgrep, sast-codeql, scorecard (exempt)
#   release-please.yml       release-please
#   cleanup-dev-files.yml    cleanup-dev-files
#   self-healing.yml         self-healing
#   auto-merge-release.yml   auto-merge-release
#   sync-main-to-development.yml  sync-to-development
#
# This floor EQUALS the live count of consuming jobs that carry a preflight
# (11 - 2 exempt = 9) by design (same convention as MINIMUM_EXPECTED_SITES in
# test_sarif_upload_auth.py): removing a consuming job is a deliberate act that
# should update this constant in the same commit, and the floor fails loudly if
# the walk or the matcher silently finds ~zero.
MINIMUM_EXPECTED_CONSUMING_JOBS = 9


def workflow_files(directory: Path = WORKFLOWS_DIR) -> list[Path]:
    """Every `*.yml`, `*.yaml` and `*.yml.template` directly under `directory`."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and (path.suffix in (".yml", ".yaml") or path.name.endswith(".yml.template"))
    )


def iter_strings(node: object):
    """Yield every string found anywhere in a nested dict/list structure."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from iter_strings(key)
            yield from iter_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_strings(item)


def job_steps(job: object) -> list[dict]:
    """The job's steps as a list of dicts (empty for `uses:` callers)."""
    if not isinstance(job, dict):
        return []
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def job_has_preflight(job: object) -> bool:
    """True if any step of the job is named like the preflight step."""
    return any(step.get("name") == PREFLIGHT_STEP_NAME for step in job_steps(job))


def job_references_token(job: object) -> bool:
    """True if the job consumes `secrets.CI_BOT_TOKEN` outside its preflight.

    Covers step `with`/`env`/`run`/`if`, job-level `env`/`if`, and a
    `uses:`-caller's `secrets:` mapping, by scanning every string in the job.
    The preflight step itself is EXCLUDED (by exact name): it always carries
    `env.CI_BOT_TOKEN: ${{ secrets.CI_BOT_TOKEN }}`, so counting it would make
    every job with a preflight a "consumer" and a stale preflight in a job
    that no longer uses the token could never be flagged.
    """
    if isinstance(job, dict) and isinstance(job.get("steps"), list):
        job = {
            **job,
            "steps": [
                step
                for step in job["steps"]
                if not (
                    isinstance(step, dict) and step.get("name") == PREFLIGHT_STEP_NAME
                )
            ],
        }
    return any(TOKEN_REFERENCE.search(text) for text in iter_strings(job))


def _inline_preflight_problems(step: dict, sarif: bool) -> list[str]:
    """Problems with an inline (`run:`) preflight step."""
    problems: list[str] = []
    env = step.get("env")
    env_value = env.get("CI_BOT_TOKEN") if isinstance(env, dict) else None
    if env_value != EXPECTED_ENV_VALUE:
        problems.append(f"env.CI_BOT_TOKEN must be {EXPECTED_ENV_VALUE!r}")
    run = step.get("run")
    run = run if isinstance(run, str) else ""
    for needle in RUN_NEEDLES:
        if needle not in run:
            problems.append(f"run must contain {needle!r}")
    if sarif:
        for needle in SARIF_RUN_NEEDLES:
            if needle not in run:
                problems.append(f"run must contain {needle!r}")
        if step.get("id") != PREFLIGHT_STEP_ID:
            problems.append(f"step must have id: {PREFLIGHT_STEP_ID}")
    if "${{" in run:
        problems.append("run must not interpolate ${{ }} (script injection)")
    return problems


def preflight_problems(step: dict, sarif: bool = False) -> list[str]:
    """Everything wrong with a preflight step (empty list means it is sound).

    `sarif` marks a job that uploads SARIF with the token; its preflight must
    also probe code-scanning access and expose `use_pat` under the fixed id.
    """
    problems: list[str] = []
    if "uses" in step:
        # The composite action form: the script lives in (and is tested via)
        # the action, so only the call wiring is checked here.
        with_ = step.get("with")
        token = with_.get("token") if isinstance(with_, dict) else None
        if token != EXPECTED_ENV_VALUE:
            problems.append(f"with.token must be {EXPECTED_ENV_VALUE!r}")
        if "run" in step:
            problems.append("an action call must not also carry a run:")
        if sarif and step.get("id") != PREFLIGHT_STEP_ID:
            problems.append(f"step must have id: {PREFLIGHT_STEP_ID}")
    else:
        problems += _inline_preflight_problems(step, sarif)
    if "continue-on-error" in step:
        problems.append("must not set continue-on-error")
    if "if" in step:
        problems.append("must not have an `if:`")
    return problems


def is_action_checkout(step: object) -> bool:
    """True for a credential-less sparse checkout of `.github/actions` only."""
    if not isinstance(step, dict):
        return False
    uses = step.get("uses")
    with_ = step.get("with")
    return (
        isinstance(uses, str)
        and uses.startswith("actions/checkout@")
        and isinstance(with_, dict)
        and with_.get("sparse-checkout") == ".github/actions"
        and with_.get("persist-credentials") is False
        and "token" not in with_
    )


def job_problems(job: object) -> list[str]:
    """Problems with a job; empty if it neither consumes the token nor has a preflight.

    A preflight in a job that no longer consumes the token is STALE and flagged.
    """
    if not job_references_token(job):
        if job_has_preflight(job):
            return ["stale preflight: job has the step but no CI_BOT_TOKEN consumer"]
        return []
    steps = job_steps(job)
    if not steps:
        return ["consumes CI_BOT_TOKEN but has no steps to host the preflight"]
    first = steps[0]
    if is_action_checkout(first) and len(steps) > 1:
        # The `./` form needs the action on disk: a sparse checkout of
        # `.github/actions` may precede the preflight (and nothing else).
        first = steps[1]
    if first.get("name") != PREFLIGHT_STEP_NAME:
        return [f"first step must be named {PREFLIGHT_STEP_NAME!r}"]
    return preflight_problems(first, sarif=bool(sarif_token_sites("", "", job)))


def exempt_aware_problems(file_name: str, job_id: str, job: object) -> list[str]:
    """Problems with a job, honouring PREFLIGHT_EXEMPT_JOBS.

    An exempt job must NOT carry the preflight (re-adding it breaks Scorecard
    `publish_results` verification); every other job goes through `job_problems`.
    """
    if (file_name, job_id) in PREFLIGHT_EXEMPT_JOBS:
        if job_has_preflight(job):
            return ["exempt job must not carry the preflight (breaks publish_results)"]
        return []
    return job_problems(job)


def sarif_token_sites(
    file_name: str, job_id: str, job: object
) -> list[tuple[str, str]]:
    """(label, token expression) of each SARIF upload step that sets a token.

    Covers `upload-sarif` steps and `analyze` steps with `token:` (those upload
    natively), including the exempt scorecard jobs: they cannot host a preflight
    step but read the verdict from a separate preflight job via `needs`.
    """
    sites: list[tuple[str, str]] = []
    for index, step in enumerate(job_steps(job)):
        uses = step.get("uses")
        with_ = step.get("with")
        if not isinstance(uses, str) or not uses.startswith(SARIF_ACTION_PREFIXES):
            continue
        if not isinstance(with_, dict) or "token" not in with_:
            continue
        label = f"{file_name}:{job_id}:step[{index}]"
        sites.append((label, str(with_["token"])))
    return sites


def _needs_list(job: object) -> list[str]:
    needs = job.get("needs") if isinstance(job, dict) else None
    if isinstance(needs, str):
        return [needs]
    return [n for n in needs if isinstance(n, str)] if isinstance(needs, list) else []


def provider_problems(jobs: dict, consumer_id: str, provider_id: str) -> list[str]:
    """Problems with the preflight JOB `provider_id` feeding `consumer_id` (#482).

    The consumer reads `needs.<provider>.outputs.use_pat`. The provider must be
    in the consumer's `needs`, start with the sound SARIF preflight, expose
    `outputs.use_pat` from it, run under the exact same `if:` as the consumer
    (a skipped provider would silently force the github.token fallback) and
    request no write permission (in particular no id-token).
    """
    provider = jobs.get(provider_id)
    if not isinstance(provider, dict):
        return [f"needs.{provider_id} names a job that does not exist"]
    consumer = jobs[consumer_id]
    problems: list[str] = []
    if provider_id not in _needs_list(consumer):
        problems.append(f"{consumer_id} must list {provider_id} in needs")
    steps = job_steps(provider)
    if not steps or steps[0].get("name") != PREFLIGHT_STEP_NAME:
        problems.append(f"{provider_id}: first step must be {PREFLIGHT_STEP_NAME!r}")
    else:
        problems += [
            f"{provider_id}: {p}" for p in preflight_problems(steps[0], sarif=True)
        ]
    outputs = provider.get("outputs")
    expected = "${{ steps." + PREFLIGHT_STEP_ID + ".outputs.use_pat }}"
    if not isinstance(outputs, dict) or outputs.get("use_pat") != expected:
        problems.append(f"{provider_id}: outputs.use_pat must be {expected!r}")
    if provider.get("if") != consumer.get("if"):
        problems.append(f"{provider_id}: `if:` must equal {consumer_id}'s `if:`")
    permissions = provider.get("permissions")
    if isinstance(permissions, dict) and any(
        value == "write" for value in permissions.values()
    ):
        problems.append(f"{provider_id}: must not request any write permission")
    return problems


def token_selects_pat_only_when_true(token: str, output_ref: str) -> bool:
    """True if `token` is exactly `<ref> == 'true' && secrets.CI_BOT_TOKEN || github.token`.

    Whitespace-normalized and exact, so an expression that merely mentions the
    output (`== 'false' && PAT`, swapped operands, `!=`) cannot pass.
    """
    expr = " ".join(token.strip().removeprefix("${{").removesuffix("}}").split())
    return expr == f"{output_ref} == 'true' && secrets.CI_BOT_TOKEN || github.token"


def sarif_site_problems(file_name: str, jobs: dict) -> list[str]:
    """Problems with every SARIF token site of a workflow's `jobs` mapping.

    A site is sound if its token is the PAT-or-github.token expression gated on
    either this job's own preflight step output, or (jobs that cannot host the
    step) a sound preflight job named through `needs.<J>.outputs.use_pat`.
    """
    problems: list[str] = []
    for job_id, job in jobs.items():
        for label, token in sarif_token_sites(file_name, job_id, job):
            if "secrets.CI_BOT_TOKEN" not in token or "github.token" not in token:
                problems.append(f"{label}: token is {token!r}")
                continue
            match = NEEDS_USE_PAT.search(token)
            if match:
                if not token_selects_pat_only_when_true(
                    token, f"needs.{match.group(1)}.outputs.use_pat"
                ):
                    problems.append(f"{label}: token is {token!r}")
                problems += [
                    f"{label}: {p}"
                    for p in provider_problems(jobs, job_id, match.group(1))
                ]
            elif not token_selects_pat_only_when_true(token, USE_PAT_EXPRESSION):
                problems.append(f"{label}: token is {token!r}")
    return problems


def provider_job_ids(file_name: str, jobs: dict) -> set[str]:
    """Jobs named by a `needs.<J>.outputs.use_pat` SARIF token in this workflow."""
    return {
        match.group(1)
        for job_id, job in jobs.items()
        for _, token in sarif_token_sites(file_name, job_id, job)
        if (match := NEEDS_USE_PAT.search(token))
    }


def load_jobs(path: Path) -> dict:
    """The `jobs:` mapping of a workflow file (empty if absent or unparsable shape)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    return jobs if isinstance(jobs, dict) else {}


def all_jobs() -> list[tuple[str, str, object]]:
    """(file name, job id, job) for every job in every workflow file."""
    return [
        (path.name, job_id, job)
        for path in workflow_files()
        for job_id, job in load_jobs(path).items()
    ]


# --- Real-tree tests ---------------------------------------------------------


def test_walk_finds_the_expected_number_of_consuming_jobs():
    found = [
        job
        for _, _, job in all_jobs()
        if job_references_token(job) and job_has_preflight(job)
    ]
    assert len(found) >= MINIMUM_EXPECTED_CONSUMING_JOBS, (
        f"walk found {len(found)} consuming jobs with a preflight, expected at "
        f"least {MINIMUM_EXPECTED_CONSUMING_JOBS}; the glob or matcher may be broken"
    )


def test_every_consuming_job_starts_with_a_sound_preflight_and_none_is_stale():
    # Preflight JOBS feeding a `needs` site hold the step without consuming the
    # token themselves; sarif_site_problems validates them instead.
    providers = {
        path.name: provider_job_ids(path.name, load_jobs(path))
        for path in workflow_files()
    }
    failures = [
        f"{file_name}:{job_id}: {problem}"
        for file_name, job_id, job in all_jobs()
        if job_id not in providers[file_name]
        for problem in exempt_aware_problems(file_name, job_id, job)
    ]
    assert not failures, "\n".join(failures)


def test_exempt_jobs_are_exactly_the_consumers_without_a_preflight():
    unprotected = {
        (file_name, job_id)
        for file_name, job_id, job in all_jobs()
        if job_references_token(job) and not job_has_preflight(job)
    }
    assert unprotected == PREFLIGHT_EXEMPT_JOBS, (
        f"consuming jobs without a preflight: {sorted(unprotected)}; "
        f"exemptions: {sorted(PREFLIGHT_EXEMPT_JOBS)} (stale or missing exemption)"
    )


def _sarif_sites() -> list[tuple[str, str]]:
    return [
        site
        for path in workflow_files()
        if path.name in SARIF_WORKFLOWS
        for job_id, job in load_jobs(path).items()
        for site in sarif_token_sites(path.name, job_id, job)
    ]


def test_walk_finds_the_sarif_upload_sites():
    sites = _sarif_sites()
    assert len(sites) >= MINIMUM_EXPECTED_SARIF_SITES, (
        f"walk found {len(sites)} SARIF token sites, expected at least "
        f"{MINIMUM_EXPECTED_SARIF_SITES}; the walk or matcher may be broken"
    )


def test_every_sarif_upload_uses_pat_only_when_preflight_confirms_access():
    failures = [
        problem
        for path in workflow_files()
        if path.name in SARIF_WORKFLOWS
        for problem in sarif_site_problems(path.name, load_jobs(path))
    ]
    assert not failures, "\n".join(failures)


def test_scorecard_jobs_have_no_run_steps_and_only_use_actions():
    # publish_results verification rejects `run:` in the scorecard job (#482).
    for file_name, job_id in sorted(PREFLIGHT_EXEMPT_JOBS):
        steps = job_steps(load_jobs(WORKFLOWS_DIR / file_name)[job_id])
        assert steps, f"{file_name}:{job_id} has no steps"
        for step in steps:
            assert "run" not in step, f"{file_name}:{job_id} has a run: step"
            assert isinstance(step.get("uses"), str), f"{file_name}:{job_id}: {step}"


def reusable_preflight_steps() -> list[tuple[str, dict]]:
    """(file:job label, step) of every preflight step in the reusable workflows."""
    return [
        (f"{path.name}:{job_id}", step)
        for path in workflow_files()
        if path.name in SARIF_WORKFLOWS
        for job_id, job in load_jobs(path).items()
        for step in job_steps(job)
        if step.get("name") == PREFLIGHT_STEP_NAME
    ]


def action_form_problems(label: str, step: dict) -> list[str]:
    """Problems with a reusable-workflow preflight that must call the action."""
    uses = step.get("uses")
    if not isinstance(uses, str) or not ACTION_USES_PATTERN.fullmatch(uses):
        return [
            f"{label}: uses must match {ACTION_USES_PATTERN.pattern!r}, got {uses!r}"
        ]
    return []


def test_all_six_reusable_preflights_use_the_action():
    # 3 jobs (sast-semgrep, sast-codeql, scorecard-token-preflight) in each of
    # reusable-ci.yml and reusable-security.yml. Exactly 6: a miscount means the
    # walk or the matcher is broken, not that the guard passed.
    steps = reusable_preflight_steps()
    assert len(steps) == MINIMUM_EXPECTED_SARIF_SITES, (
        f"walk found {len(steps)} reusable preflights, expected exactly "
        f"{MINIMUM_EXPECTED_SARIF_SITES}"
    )
    failures = [p for label, step in steps for p in action_form_problems(label, step)]
    assert not failures, "\n".join(failures)


def _sparse_checkout(**with_overrides: object) -> dict:
    return {
        "uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "with": {
            "sparse-checkout": ".github/actions",
            "persist-credentials": False,
            **with_overrides,
        },
    }


def test_selftest_action_checkout_may_precede_the_preflight():
    local = {
        "name": PREFLIGHT_STEP_NAME,
        "uses": "./.github/actions/verify-ci-bot-token",
        "with": {"token": EXPECTED_ENV_VALUE, "check-code-scanning": "false"},
    }
    consumer = {"env": {"GH_TOKEN": EXPECTED_ENV_VALUE}, "run": "true"}
    assert is_action_checkout(_sparse_checkout())
    assert job_problems({"steps": [_sparse_checkout(), local, consumer]}) == []
    # Anything else first, or a checkout that is not credential-less/sparse, fails.
    assert job_problems({"steps": [consumer, local]})
    for override in (
        {"persist-credentials": True},
        {"sparse-checkout": "."},
        {"token": EXPECTED_ENV_VALUE},
    ):
        bad = _sparse_checkout(**override)
        assert not is_action_checkout(bad), override
        assert job_problems({"steps": [bad, local, consumer]}), override
    assert not is_action_checkout("not a dict")


def test_selftest_action_form_requires_a_pinned_action_call():
    good = {"uses": f"{ACTION_USES_PREFIX}@v5.2.0"}
    assert action_form_problems("w", good) == []
    for bad in (
        {"run": "true"},
        {"uses": f"{ACTION_USES_PREFIX}@main"},
        {"uses": f"{ACTION_USES_PREFIX}@v5"},
        {"uses": "./.github/actions/verify-ci-bot-token"},
    ):
        assert action_form_problems("w", bad), bad


def test_selftest_action_call_step_is_checked_for_token_id_and_run():
    step = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "uses": f"{ACTION_USES_PREFIX}@v5.2.0",
        "with": {"token": EXPECTED_ENV_VALUE},
    }
    assert preflight_problems(step, sarif=True) == []
    assert preflight_problems({**step, "with": {}}, sarif=True)
    assert preflight_problems({**step, "id": "other"}, sarif=True)
    assert preflight_problems({**step, "run": "true"}, sarif=True)
    assert preflight_problems({**step, "if": "always()"}, sarif=True)


# --- Classifier self-tests (guard against a vacuously passing walk) ----------


def _preflight(**overrides: object) -> dict:
    step: dict = {
        "name": PREFLIGHT_STEP_NAME,
        "id": PREFLIGHT_STEP_ID,
        "env": {"CI_BOT_TOKEN": EXPECTED_ENV_VALUE},
        "run": (
            "command -v curl; curl --max-time 15 https://api.github.com/rate_limit; "
            "curl /code-scanning/analyses; "
            'case "$s" in 401) exit 1;; esac; echo "use_pat=true" >> "$GITHUB_OUTPUT"'
        ),
    }
    step.update(overrides)
    return step


def _consumer_step() -> dict:
    return {
        "uses": "actions/checkout@v7",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }


def test_selftest_sound_job_is_not_flagged():
    assert job_problems({"steps": [_preflight(), _consumer_step()]}) == []


def test_selftest_job_without_preflight_is_flagged():
    problems = job_problems({"steps": [_consumer_step()]})
    assert problems and "first step" in problems[0]


def test_selftest_preflight_not_first_is_flagged():
    job = {"steps": [{"run": "true"}, _preflight(), _consumer_step()]}
    assert job_problems(job)


def test_selftest_uses_caller_job_without_steps_is_flagged():
    job = {
        "uses": "o/r/.github/workflows/w.yml@v1",
        "secrets": {"CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"},
    }
    assert job_problems(job)


def test_selftest_interpolation_inside_run_is_flagged():
    run = 'curl /rate_limit; echo "${{ secrets.CI_BOT_TOKEN }}"; 401 exit 1'
    problems = job_problems({"steps": [_preflight(run=run), _consumer_step()]})
    assert any("script injection" in problem for problem in problems)


def test_selftest_continue_on_error_is_flagged():
    step = _preflight(**{"continue-on-error": True})
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert any("continue-on-error" in problem for problem in problems)


def test_selftest_if_on_preflight_is_flagged():
    problems = job_problems(
        {"steps": [_preflight(**{"if": "always()"}), _consumer_step()]}
    )
    assert any("`if:`" in problem for problem in problems)


def test_selftest_wrong_env_and_missing_markers_are_flagged():
    step = _preflight(env={"CI_BOT_TOKEN": "x"}, run="true")
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert len(problems) == 1 + len(RUN_NEEDLES)  # env + every run marker


def _sarif_upload_step() -> dict:
    return {
        "uses": "github/codeql-action/upload-sarif@abc",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }


def test_selftest_sarif_job_requires_probe_output_and_id():
    step = _preflight(id="other", run=_preflight()["run"].replace("use_pat=", "x="))
    problems = job_problems({"steps": [step, _sarif_upload_step()]})
    assert any("id:" in problem for problem in problems)
    assert any("use_pat=" in problem for problem in problems)


def test_selftest_non_sarif_job_needs_no_probe_or_id():
    step = _preflight(
        id="other", run="command -v curl; curl --max-time 1 /rate_limit; 401 exit 1"
    )
    assert job_problems({"steps": [step, _consumer_step()]}) == []


def test_selftest_sound_sarif_job_is_not_flagged():
    assert job_problems({"steps": [_preflight(), _sarif_upload_step()]}) == []


_SCORECARD_IF = "inputs.scorecard && github.event_name == 'pull_request'"
_NEEDS_TOKEN = (
    "${{ needs.scorecard-token-preflight.outputs.use_pat == 'true' "
    "&& secrets.CI_BOT_TOKEN || github.token }}"
)


def _scorecard_jobs(**provider_overrides: object) -> dict:
    provider: dict = {
        "if": _SCORECARD_IF,
        "permissions": {"contents": "read"},
        "outputs": {"use_pat": "${{ steps.token-preflight.outputs.use_pat }}"},
        "steps": [_preflight()],
    }
    provider.update(provider_overrides)
    return {
        "scorecard-token-preflight": provider,
        "scorecard": {
            "needs": "scorecard-token-preflight",
            "if": _SCORECARD_IF,
            "steps": [
                {
                    "uses": "github/codeql-action/upload-sarif@abc",
                    "with": {"token": _NEEDS_TOKEN},
                }
            ],
        },
    }


def test_selftest_sound_needs_site_is_not_flagged():
    jobs = _scorecard_jobs()
    assert sarif_site_problems("w.yml", jobs) == []
    assert provider_job_ids("w.yml", jobs) == {"scorecard-token-preflight"}


def test_selftest_needs_site_with_mismatched_if_is_flagged():
    jobs = _scorecard_jobs(**{"if": "inputs.scorecard"})
    problems = sarif_site_problems("w.yml", jobs)
    assert any("`if:` must equal" in problem for problem in problems)


def test_selftest_needs_site_without_needs_entry_is_flagged():
    jobs = _scorecard_jobs()
    jobs["scorecard"]["needs"] = ["detect-changes"]
    problems = sarif_site_problems("w.yml", jobs)
    assert any("must list" in problem for problem in problems)


def test_selftest_needs_site_flags_bad_provider_steps_outputs_and_permissions():
    jobs = _scorecard_jobs(
        steps=[{"run": "true"}],
        outputs={},
        permissions={"contents": "write"},
    )
    text = "\n".join(sarif_site_problems("w.yml", jobs))
    assert "first step must be" in text
    assert "outputs.use_pat" in text
    assert "write permission" in text


def test_selftest_needs_site_naming_missing_job_is_flagged():
    jobs = _scorecard_jobs()
    del jobs["scorecard-token-preflight"]
    problems = sarif_site_problems("w.yml", jobs)
    assert any("does not exist" in problem for problem in problems)


_BAD_TOKEN_FORMS = [
    "${{ steps.token-preflight.outputs.use_pat == 'false' && secrets.CI_BOT_TOKEN || github.token }}",
    "${{ steps.token-preflight.outputs.use_pat != 'true' && secrets.CI_BOT_TOKEN || github.token }}",
    "${{ steps.token-preflight.outputs.use_pat == 'true' && github.token || secrets.CI_BOT_TOKEN }}",
    "${{ steps.token-preflight.outputs.use_pat || secrets.CI_BOT_TOKEN || github.token }}",
]


def test_selftest_use_pat_matcher_requires_exact_expression():
    good = (
        "${{ steps.token-preflight.outputs.use_pat == 'true' &&\n"
        "   secrets.CI_BOT_TOKEN || github.token }}"
    )
    assert token_selects_pat_only_when_true(good, USE_PAT_EXPRESSION)
    for bad in _BAD_TOKEN_FORMS:
        assert not token_selects_pat_only_when_true(bad, USE_PAT_EXPRESSION), bad


def test_selftest_inverted_or_swapped_site_tokens_are_flagged():
    for bad in _BAD_TOKEN_FORMS:
        job = {"steps": [_preflight(), _sarif_upload_step()]}
        job["steps"][1]["with"]["token"] = bad
        assert sarif_site_problems("w.yml", {"j": job}), bad
    for bad in (
        _NEEDS_TOKEN.replace("== 'true'", "== 'false'"),
        "${{ needs.scorecard-token-preflight.outputs.use_pat == 'true' "
        "&& github.token || secrets.CI_BOT_TOKEN }}",
    ):
        jobs = _scorecard_jobs()
        jobs["scorecard"]["steps"][0]["with"]["token"] = bad
        assert sarif_site_problems("w.yml", jobs), bad


def test_selftest_bare_token_site_is_flagged_in_exempt_job_too():
    jobs = _scorecard_jobs()
    jobs["scorecard"]["steps"][0]["with"]["token"] = (
        "${{ secrets.CI_BOT_TOKEN || github.token }}"
    )
    assert sarif_site_problems("w.yml", jobs)


def test_selftest_sarif_site_matcher_flags_bare_token():
    upload = {
        "uses": "github/codeql-action/upload-sarif@abc",
        "with": {"token": "${{ secrets.CI_BOT_TOKEN || github.token }}"},
    }
    no_token = {"uses": "github/codeql-action/analyze@abc", "with": {"upload": False}}
    job = {"steps": [_preflight(), no_token, upload]}
    sites = sarif_token_sites("other.yml", "j", job)
    assert len(sites) == 1 and USE_PAT_EXPRESSION not in sites[0][1]
    # Exempt (scorecard) jobs are matched too since #482.
    assert len(sarif_token_sites(*next(iter(PREFLIGHT_EXEMPT_JOBS)), job)) == 1


def test_selftest_curl_without_max_time_is_flagged():
    step = _preflight(
        run="command -v curl; curl https://api.github.com/rate_limit; "
        'curl /code-scanning/analyses; echo use_pat= >> "$GITHUB_OUTPUT"; '
        'case "$s" in 401) exit 1;; esac'
    )
    problems = job_problems({"steps": [step, _consumer_step()]})
    assert any("--max-time" in problem for problem in problems)


def test_selftest_stale_preflight_without_consumer_is_flagged():
    problems = job_problems({"steps": [_preflight(), {"run": "echo hi"}]})
    assert problems and "stale preflight" in problems[0]


def test_selftest_detector_excludes_the_preflight_step_itself():
    assert not job_references_token({"steps": [_preflight()]})
    assert job_references_token({"steps": [_preflight(), _consumer_step()]})


def test_selftest_job_not_referencing_token_is_not_flagged():
    job = {"steps": [{"run": "echo hi", "env": {"GH_TOKEN": "${{ github.token }}"}}]}
    assert job_problems(job) == []


def test_selftest_exempt_job_without_preflight_passes():
    pair = next(iter(PREFLIGHT_EXEMPT_JOBS))
    assert exempt_aware_problems(*pair, {"steps": [_consumer_step()]}) == []


def test_selftest_exempt_job_with_preflight_fails():
    pair = next(iter(PREFLIGHT_EXEMPT_JOBS))
    job = {"steps": [_preflight(), _consumer_step()]}
    problems = exempt_aware_problems(*pair, job)
    assert problems and "exempt job" in problems[0]


def test_selftest_non_exempt_job_without_preflight_fails():
    problems = exempt_aware_problems(
        "other.yml", "some-job", {"steps": [_consumer_step()]}
    )
    assert problems and "first step" in problems[0]


def test_selftest_reference_detector_finds_token_in_every_location():
    expr = "${{ secrets.CI_BOT_TOKEN || github.token }}"
    locations = {
        "with": {"steps": [{"uses": "x", "with": {"token": expr}}]},
        "env": {"steps": [{"run": "true", "env": {"T": expr}}]},
        "run": {"steps": [{"run": f"echo {expr}"}]},
        "step if": {"steps": [{"run": "true", "if": f"{expr} != ''"}]},
        "job if": {"if": f"{expr} != ''", "steps": [{"run": "true"}]},
        "job env": {"env": {"T": expr}, "steps": [{"run": "true"}]},
    }
    for label, job in locations.items():
        assert job_references_token(job), label
    assert not job_references_token({"steps": [{"run": "echo secrets.OTHER"}]})
    assert not job_references_token({"steps": [{"run": "secrets.CI_BOT_TOKEN_X"}]})
