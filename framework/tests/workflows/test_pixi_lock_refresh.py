"""Scheduled pixi.lock refresh opens a signed bot PR (#387).

scripts/pixi_lock_diff.py turns the JSON written by `pixi update --json` into a
markdown PR body. It is loaded here by path and driven with documented
`pixi update --json` payloads, including a trimmed real sample recorded from
this repository. reusable-pixi-lock-refresh.yml inlines it, and
scripts/check_conda_first.py, as `python3 - <<'PY'` heredocs, so tests pin both
heredocs to the standalone files. Structural tests cover the zero-secret
design, permissions, the signed-commit and CI-dispatch steps, the no-change
path, the injection rule and the consumer templates.

Observed `pixi update --json` schema: {"version": 1, "environment": {<env>:
{<platform>: [{"name", "before": <pkg>|null, "after": <pkg>|null, "type":
"conda"|"pypi"}]}}}. A conda package object carries its location in "conda"
(a channel URL whose filename is name-version-build); the version is never a
separate field. No pypi change occurs in this repository's lock, so the pypi
shape in the synthetic tests is an assumption: a "pypi" URL, or an explicit
"version" field.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPT = Path("scripts/pixi_lock_diff.py")
CONDA_FIRST_SCRIPT = Path("scripts/check_conda_first.py")
REUSABLE = Path(".github/workflows/reusable-pixi-lock-refresh.yml")
TEMPLATE = Path("templates/github/workflows/pixi-lock-refresh-template.yml")
RELEASE_PLEASE_CONFIG = Path(".release-please-config.json")
FIXTURE = Path("framework/tests/workflows/fixtures/pixi_update_sample.json")
DIFF_STEP = "Build PR body"
CONDA_FIRST_STEP = "Conda-first lock check"
COMMIT_STEP = "Create signed commit on refresh branch"
DISPATCH_STEP = "Trigger CI on refresh branch"
CI_TEMPLATES = (
    Path("templates/github/workflows/standard-ci-template.yml"),
    Path("templates/github/workflows/comprehensive-ci-template.yml"),
)
HEREDOC_OPEN = "python3 - <<'PY'\n"
HEREDOC_CLOSE = "\nPY\n"
# The diff step redirects the rendered body straight into the PR body file.
DIFF_HEREDOC_OPEN = "python3 - <<'PY' > \"$RUNNER_TEMP/pr-body.md\"\n"
GATE = "steps.changes.outputs.changed == 'true'"
MODE_STEP = "Select token mode"
MINT_STEP = "Mint GitHub App token"
APP_TOKEN_EXPR = "${{ steps.app-token.outputs.token || github.token }}"
APP_SECRET_REFS = {
    "APP_CLIENT_ID",
    "APP_PRIVATE_KEY",
    "LOCK_REFRESH_APP_CLIENT_ID",
    "LOCK_REFRESH_APP_PRIVATE_KEY",
}

_spec = importlib.util.spec_from_file_location("pixi_lock_diff", SCRIPT)
assert _spec is not None and _spec.loader is not None
diff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diff)

NO_CHANGES = "No package changes."


def conda(name: str, version: str, build: str = "h0_0", ext: str = ".conda") -> dict:
    return {
        "conda": f"https://conda.anaconda.org/conda-forge/linux-64/{name}-{version}-{build}{ext}",
        "sha256": "0" * 64,
    }


def pypi(name: str, version: str) -> dict:
    return {
        "pypi": f"https://files.pythonhosted.org/packages/{name}-{version}-py3-none-any.whl"
    }


def change(
    name: str, before: Any, after: Any, kind: str = "conda", **extra: Any
) -> dict:
    return {"name": name, "before": before, "after": after, "type": kind, **extra}


def payload(**envs: dict[str, list[dict]]) -> dict:
    return {"version": 1, "environment": envs}


def render(data: dict) -> str:
    return diff.render(data)


def rows(text: str) -> list[list[str]]:
    """Cells of every table body row."""
    out = []
    for line in text.splitlines():
        if line.startswith("|") and not line.startswith(("| Package", "|---", "| ---")):
            out.append([cell.strip() for cell in line.strip("|").split("|")])
    return out


# --- pixi_lock_diff: change kinds --------------------------------------------


def test_added_package_shows_dash_to_new():
    text = render(
        payload(default={"linux-64": [change("rich", None, conda("rich", "13.0"))]})
    )
    assert rows(text) == [["`rich`", "linux-64", "— → 13.0", "conda"]]


def test_removed_package_shows_old_to_dash():
    text = render(
        payload(default={"linux-64": [change("rich", conda("rich", "13.0"), None)]})
    )
    assert rows(text) == [["`rich`", "linux-64", "13.0 → —", "conda"]]


def test_upgraded_package_shows_old_to_new():
    data = payload(
        default={
            "linux-64": [change("rich", conda("rich", "13.0"), conda("rich", "14.1"))]
        }
    )
    assert rows(render(data)) == [["`rich`", "linux-64", "13.0 → 14.1", "conda"]]


def test_downgrade_is_reported_and_counted_separately():
    data = payload(
        default={
            "linux-64": [change("rich", conda("rich", "14.1"), conda("rich", "13.0"))]
        }
    )
    text = render(data)
    assert rows(text) == [["`rich`", "linux-64", "14.1 → 13.0", "conda"]]
    assert "1 downgraded" in text
    assert "0 upgraded" in text


def test_summary_counts_every_kind():
    data = payload(
        default={
            "linux-64": [
                change("a", None, conda("a", "1")),
                change("b", conda("b", "1"), None),
                change("c", conda("c", "1"), conda("c", "2")),
                change("d", conda("d", "2"), conda("d", "1")),
            ]
        }
    )
    assert "1 added, 1 removed, 1 upgraded, 1 downgraded, 0 rebuilt" in render(data)


def test_version_comparison_is_numeric_not_lexical():
    data = payload(
        default={"linux-64": [change("x", conda("x", "1.9"), conda("x", "1.10"))]}
    )
    text = render(data)
    assert "1 upgraded" in text
    assert "0 downgraded" in text


def test_build_only_change_shows_the_builds():
    data = payload(
        default={
            "linux-64": [
                change(
                    "_openmp_mutex",
                    conda("_openmp_mutex", "4.5", "2_gnu", ".tar.bz2"),
                    conda("_openmp_mutex", "4.5", "20_gnu"),
                )
            ]
        }
    )
    text = render(data)
    assert rows(text) == [
        ["`_openmp_mutex`", "linux-64", "4.5 (2_gnu) → 4.5 (20_gnu)", "conda"]
    ]
    assert "1 rebuilt" in text


def test_unchanged_entry_is_dropped():
    pkg = conda("rich", "13.0")
    data = payload(default={"linux-64": [change("rich", pkg, dict(pkg))]})
    assert render(data).strip() == NO_CHANGES


# --- pixi_lock_diff: grouping, ordering, sources -----------------------------


def test_identical_changes_across_platforms_collapse_into_one_row():
    entry = change("rich", conda("rich", "13.0"), conda("rich", "14.1"))
    data = payload(
        default={"osx-arm64": [entry], "linux-64": [entry], "win-64": [entry]}
    )
    assert rows(render(data)) == [
        ["`rich`", "linux-64, osx-arm64, win-64", "13.0 → 14.1", "conda"]
    ]


def test_differing_changes_across_platforms_stay_separate():
    data = payload(
        default={
            "linux-64": [change("rich", conda("rich", "13.0"), conda("rich", "14.1"))],
            "win-64": [change("rich", conda("rich", "13.0"), conda("rich", "14.2"))],
        }
    )
    assert [r[1:3] for r in rows(render(data))] == [
        ["linux-64", "13.0 → 14.1"],
        ["win-64", "13.0 → 14.2"],
    ]


def test_each_environment_gets_its_own_table_in_sorted_order():
    data = payload(
        quality={"linux-64": [change("b", None, conda("b", "1"))]},
        default={"linux-64": [change("a", None, conda("a", "1"))]},
    )
    text = render(data)
    assert text.index("### default") < text.index("### quality")
    assert text.count("| Package |") == 2


def test_rows_are_sorted_by_package_name():
    data = payload(
        default={
            "linux-64": [
                change("zlib", None, conda("zlib", "1")),
                change("attrs", None, conda("attrs", "1")),
                change("mypy", None, conda("mypy", "1")),
            ]
        }
    )
    assert [r[0] for r in rows(render(data))] == ["`attrs`", "`mypy`", "`zlib`"]


def test_pypi_and_conda_sources_are_labelled():
    data = payload(
        default={
            "linux-64": [
                change("rich", conda("rich", "13.0"), conda("rich", "14.1")),
                change(
                    "hb-thing", pypi("hb_thing", "1.0"), pypi("hb_thing", "1.1"), "pypi"
                ),
            ]
        }
    )
    assert rows(render(data)) == [
        ["`hb-thing`", "linux-64", "1.0 → 1.1", "pypi"],
        ["`rich`", "linux-64", "13.0 → 14.1", "conda"],
    ]


def test_pypi_explicit_version_field_wins_over_url():
    before = {"pypi": "https://example.org/odd-name.zip", "version": "2.0"}
    after = {"pypi": "https://example.org/odd-name.zip", "version": "2.1"}
    data = payload(default={"linux-64": [change("odd", before, after, "pypi")]})
    assert rows(render(data))[0][2] == "2.0 → 2.1"


def test_pypi_sdist_version_is_parsed():
    before = {"pypi": "https://files.pythonhosted.org/x/my-pkg-1.2.3.tar.gz"}
    after = {"pypi": "https://files.pythonhosted.org/x/my-pkg-1.2.4.tar.gz"}
    data = payload(default={"linux-64": [change("my-pkg", before, after, "pypi")]})
    assert rows(render(data))[0][2] == "1.2.3 → 1.2.4"


def test_conda_name_containing_dashes_parses_version_from_the_right():
    data = payload(
        default={
            "linux-64": [
                change(
                    "python-dateutil",
                    conda("python-dateutil", "2.8.2", "pyhd8ed1ab_0"),
                    conda("python-dateutil", "2.9.0", "pyhd8ed1ab_1"),
                )
            ]
        }
    )
    assert rows(render(data))[0][2] == "2.8.2 → 2.9.0"


# --- pixi_lock_diff: empty input and the real fixture ------------------------


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"version": 1},
        {"version": 1, "environment": {}},
        {"version": 1, "environment": {"default": {}}},
        {"version": 1, "environment": {"default": {"linux-64": []}}},
    ],
)
def test_empty_payloads_print_a_single_line(data):
    assert render(data).strip() == NO_CHANGES


def test_real_fixture_is_non_trivial():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert set(data["environment"]) == {"quality", "default"}


def test_real_fixture_renders_the_expected_body():
    text = render(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert "### default" in text
    assert "### quality" in text
    assert "| `mypy` | linux-64 | 1.17.0 → 2.4.1 | conda |" in text
    assert "| `ncurses` | linux-64 | 6.5 → 6.6 | conda |" in text
    assert "| `_libgcc_mutex` | linux-64 | 0.1 → — | conda |" in text
    assert "| `_python_abi3_support` | linux-64 | — → 1.0 | conda |" in text
    assert "| `_openmp_mutex` | linux-64 | 4.5 (2_gnu) → 4.5 (20_gnu) | conda |" in text


def test_main_reads_update_json_from_the_environment(tmp_path, monkeypatch, capsys):
    path = tmp_path / "update.json"
    path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("UPDATE_JSON", str(path))
    assert diff.main() == 0
    assert "| `mypy` |" in capsys.readouterr().out


@pytest.mark.parametrize("content", ["", "   \n"])
def test_main_treats_an_empty_file_as_no_changes(
    tmp_path, monkeypatch, capsys, content
):
    path = tmp_path / "update.json"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setenv("UPDATE_JSON", str(path))
    assert diff.main() == 0
    assert capsys.readouterr().out.strip() == NO_CHANGES


def test_main_fails_clearly_on_invalid_json(tmp_path, monkeypatch, capsys):
    path = tmp_path / "update.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("UPDATE_JSON", str(path))
    assert diff.main() == 1
    assert "::error" in capsys.readouterr().out


# --- Heredoc sync -------------------------------------------------------------


def _workflow() -> dict:
    return yaml.safe_load(REUSABLE.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _workflow()["jobs"]["refresh"]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def _inline_script(name: str, opener: str = HEREDOC_OPEN) -> str:
    run = _step(name)["run"]
    assert run.startswith(opener), "run must start with a quoted-heredoc python3 -"
    assert run.endswith(HEREDOC_CLOSE), "run must end with the PY terminator"
    return run[len(opener) : -len(HEREDOC_CLOSE)] + "\n"


def test_diff_heredoc_matches_standalone_script():
    body = _inline_script(DIFF_STEP, DIFF_HEREDOC_OPEN)
    assert "def render" in body
    assert body == SCRIPT.read_text(encoding="utf-8")


def test_conda_first_heredoc_matches_standalone_script():
    body = _inline_script(CONDA_FIRST_STEP)
    assert "def parse_pypi_packages" in body
    assert body == CONDA_FIRST_SCRIPT.read_text(encoding="utf-8")


def test_script_header_and_stdlib_only():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "from __future__ import annotations" in text
    assert '"""' in text.split("from __future__", 1)[0]
    imported = set(re.findall(r"^(?:import|from) (\w+)", text, re.MULTILINE))
    assert imported <= {
        "__future__",
        "json",
        "os",
        "re",
        "sys",
        "collections",
        "typing",
    }


# --- Reusable workflow structure ---------------------------------------------


def _call() -> dict:
    doc = _workflow()
    return (doc.get(True) or doc["on"])["workflow_call"]


def test_trigger_is_workflow_call_only():
    doc = _workflow()
    assert set(doc.get(True) or doc["on"]) == {"workflow_call"}


def test_workflow_call_declares_only_the_optional_app_secrets():
    secrets = _call()["secrets"]
    assert set(secrets) == {"APP_CLIENT_ID", "APP_PRIVATE_KEY"}
    for name, spec in secrets.items():
        assert spec["required"] is False, name
        assert spec["description"], name


def test_no_ci_bot_reference_in_workflow_or_template():
    for path in (REUSABLE, TEMPLATE):
        text = path.read_text(encoding="utf-8")
        assert "CI_BOT" not in text, path
        assert "gpg" not in text.lower(), path
        used = set(re.findall(r"secrets\.(\w+)", text))
        assert used <= APP_SECRET_REFS, (path, used)


def test_inputs_and_defaults():
    inputs = _call()["inputs"]
    defaults = {k: v.get("default") for k, v in inputs.items()}
    assert defaults == {
        "target-branch": "development",
        "branch-name": "chore/pixi-lock-refresh",
        "environments": "",
        "auto-merge": False,
        "pixi-version": defaults["pixi-version"],
        "package-path": ".",
        "conda-first-check": "enforce",
        "conda-first-allow": "hb-*",
        "ci-workflow": "ci.yml",
    }
    assert inputs["auto-merge"]["type"] == "boolean"
    reusable_ci = yaml.safe_load(
        Path(".github/workflows/reusable-ci.yml").read_text(encoding="utf-8")
    )
    ci_inputs = (reusable_ci.get(True) or reusable_ci["on"])["workflow_call"]["inputs"]
    assert defaults["pixi-version"] == ci_inputs["pixi-version"]["default"]


def test_conda_first_allow_default_matches_reusable_ci():
    reusable_ci = yaml.safe_load(
        Path(".github/workflows/reusable-ci.yml").read_text(encoding="utf-8")
    )
    ci_inputs = (reusable_ci.get(True) or reusable_ci["on"])["workflow_call"]["inputs"]
    assert (
        _call()["inputs"]["conda-first-allow"]["default"]
        == ci_inputs["conda-first-allow"]["default"]
    )


def test_permissions_are_inherited_from_the_caller():
    doc = _workflow()
    assert "permissions" not in doc
    assert "permissions" not in doc["jobs"]["refresh"]


def test_concurrency_is_per_repo_and_branch_and_never_cancels():
    concurrency = _workflow()["concurrency"]
    assert "github.repository" in concurrency["group"]
    assert "inputs.branch-name" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_checkout_is_target_branch_without_persisted_credentials():
    checkout = next(
        s for s in _steps() if str(s.get("uses", "")).startswith("actions/checkout")
    )
    assert "token" not in checkout["with"]
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ inputs.target-branch }}"


def test_setup_pixi_pins_version_input():
    step = next(s for s in _steps() if "setup-pixi" in str(s.get("uses", "")))
    assert step["uses"] == "prefix-dev/setup-pixi@v0.11.2"
    assert step["with"]["pixi-version"] == "${{ inputs.pixi-version }}"


def test_workflow_has_no_local_action_or_release_marker():
    text = REUSABLE.read_text(encoding="utf-8")
    assert "uses: ./" not in text
    assert "x-release-please-version" not in text


def test_no_change_path_gates_every_later_step():
    steps = _steps()
    names = [s.get("name") for s in steps]
    start = names.index("Detect lock changes") + 1
    changes = steps[start - 1]
    assert changes["id"] == "changes"
    assert "git diff --quiet" in changes["run"]
    assert "::notice" in changes["run"]
    assert "changed=false" in changes["run"]
    assert "changed=true" in changes["run"]
    later = steps[start:]
    assert later, "no steps after change detection"
    for step in later:
        assert GATE in str(step.get("if", "")), f"{step.get('name')} is not gated"
    gated = {s["name"] for s in later}
    assert {CONDA_FIRST_STEP, DIFF_STEP, "Open or update pull request"} <= gated


def test_conda_first_runs_before_the_diff_and_any_pr_step():
    names = [s.get("name") for s in _steps()]
    assert names.index(CONDA_FIRST_STEP) < names.index(DIFF_STEP)
    assert names.index(CONDA_FIRST_STEP) < names.index(COMMIT_STEP)
    step = _step(CONDA_FIRST_STEP)
    assert step["env"]["CONDA_FIRST_MODE"] == "${{ inputs.conda-first-check }}"
    assert step["env"]["CONDA_FIRST_ALLOW"] == "${{ inputs.conda-first-allow }}"
    assert step["working-directory"] == "${{ inputs.package-path }}"


def test_update_runs_with_json_into_runner_temp():
    step = _step("Refresh pixi.lock")
    assert "pixi update --json" in step["run"]
    assert '"$RUNNER_TEMP/update.json"' in step["run"]
    assert step["env"]["ENVIRONMENTS"] == "${{ inputs.environments }}"
    assert step["working-directory"] == "${{ inputs.package-path }}"


def test_commit_step_creates_a_verified_commit_via_graphql():
    step = _step(COMMIT_STEP)
    assert step["id"] == "commit"
    assert step["if"] == GATE
    assert step["env"]["GH_TOKEN"] == APP_TOKEN_EXPR
    run = step["run"]
    assert "set -euo pipefail" in run
    assert "createCommitOnBranch" in run
    assert "chore(deps): refresh pixi.lock" in run
    assert ".commit.verification.verified" in run
    assert "refusing to publish an unsigned commit" in run
    assert "git push" not in run
    assert "git commit" not in run
    assert 'gh api -X PATCH "repos/$GH_REPO/git/refs/heads/$BRANCH_NAME"' in run
    assert run.index("verification.verified") < run.index("-X PATCH")
    assert '>> "$GITHUB_OUTPUT"' in run


def test_dispatch_step_uses_ci_workflow_input_and_is_skipped_when_empty():
    names = [s.get("name") for s in _steps()]
    assert names.index("Open or update pull request") < names.index(DISPATCH_STEP)
    step = _step(DISPATCH_STEP)
    assert GATE in step["if"]
    assert "inputs.ci-workflow != ''" in step["if"]
    assert step["env"]["CI_WORKFLOW"] == "${{ inputs.ci-workflow }}"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert 'gh workflow run "$CI_WORKFLOW" --ref "$BRANCH_NAME"' in step["run"]
    assert "workflow_dispatch" in step["run"]
    assert "steps.mode.outputs.app != 'true'" in step["if"]


def test_mode_step_reads_secrets_via_env_and_rejects_a_half_configured_app():
    step = _step(MODE_STEP)
    assert step["id"] == "mode"
    assert "if" not in step
    assert step["env"] == {
        "APP_CLIENT_ID": "${{ secrets.APP_CLIENT_ID }}",
        "APP_PRIVATE_KEY": "${{ secrets.APP_PRIVATE_KEY }}",
    }
    run = step["run"]
    assert "secrets." not in run
    assert '[ -n "$APP_CLIENT_ID" ] && [ -n "$APP_PRIVATE_KEY" ]' in run
    assert '[ -z "$APP_CLIENT_ID" ] && [ -z "$APP_PRIVATE_KEY" ]' in run
    assert run.count("app=true") == 1
    assert run.count("app=false") == 1
    assert "::error title=App credentials incomplete::" in run
    assert "exit 1" in run
    assert "missing=APP_CLIENT_ID" in run
    assert "missing=APP_PRIVATE_KEY" in run
    assert "echo $APP" not in run and 'echo "$APP' not in run
    names = [s.get("name") for s in _steps()]
    assert names.index("Validate branch inputs") < names.index(MODE_STEP)
    assert names.index(MODE_STEP) < names.index(MINT_STEP)
    assert names.index(MINT_STEP) < names.index("Checkout target branch")


def test_mint_step_requests_only_contents_and_pull_requests_write():
    step = _step(MINT_STEP)
    assert step["id"] == "app-token"
    assert step["uses"] == "actions/create-github-app-token@v3.3.0"
    assert step["if"] == "steps.mode.outputs.app == 'true'"
    assert step["with"] == {
        "client-id": "${{ secrets.APP_CLIENT_ID }}",
        "private-key": "${{ secrets.APP_PRIVATE_KEY }}",
        "permission-contents": "write",
        "permission-pull-requests": "write",
    }
    names = [s.get("name") for s in _steps()]
    assert names.index(MINT_STEP) < names.index("Checkout target branch")
    assert names.index(MINT_STEP) < names.index("Detect lock changes")
    assert names.index(MINT_STEP) < names.index(COMMIT_STEP)


def test_app_credentials_are_validated_even_when_the_lock_is_unchanged():
    names = [s.get("name") for s in _steps()]
    for name in (MODE_STEP, MINT_STEP):
        assert "steps.changes" not in str(_step(name)), name
        assert names.index(name) < names.index("Detect lock changes"), name


def test_app_path_needs_no_write_in_the_caller():
    doc = _workflow()
    assert "permissions" not in doc
    assert "permissions" not in doc["jobs"]["refresh"]
    for name in (COMMIT_STEP, "Open or update pull request", "Enable auto-merge"):
        assert _step(name)["env"]["GH_TOKEN"] == APP_TOKEN_EXPR, name
    dispatch = _step(DISPATCH_STEP)
    assert "steps.mode.outputs.app != 'true'" in dispatch["if"]
    only_github_token = [
        s["name"]
        for s in _steps()
        if s.get("env", {}).get("GH_TOKEN") == "${{ github.token }}"
    ]
    assert only_github_token == [DISPATCH_STEP]
    text = TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"^\s*#\s*permissions:\n\s*#\s+contents: read$", text, re.M)
    assert re.search(
        r"^\s*#\s*APP_CLIENT_ID: \$\{\{ secrets\.LOCK_REFRESH_APP_CLIENT_ID", text, re.M
    )
    assert re.search(
        r"^\s*#\s*APP_PRIVATE_KEY: \$\{\{ secrets\.LOCK_REFRESH_APP_PRIVATE_KEY",
        text,
        re.M,
    )


@pytest.mark.parametrize("path", CI_TEMPLATES, ids=lambda p: p.name)
def test_ci_templates_declare_workflow_dispatch(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "workflow_dispatch" in (doc.get(True) or doc["on"])


def test_branch_name_may_never_equal_the_target_branch():
    run = _step("Validate branch inputs")["run"]
    assert '"$BRANCH_NAME" = "$TARGET_BRANCH"' in run
    assert "exit 1" in run


def test_pr_is_listed_then_edited_or_created():
    run = _step("Open or update pull request")["run"]
    assert (
        'gh pr list --head "$BRANCH_NAME" --base "$TARGET_BRANCH" --state open' in run
    )
    assert "gh pr edit" in run
    assert "gh pr create" in run
    assert run.index("gh pr edit") < run.index("gh pr create")
    assert '--body-file "$RUNNER_TEMP/pr-body.md"' in run
    assert "Allow GitHub Actions to create and approve pull requests" in run
    assert _step("Open or update pull request")["env"]["GH_TOKEN"] == APP_TOKEN_EXPR
    assert "pull_requests" in run or "Pull requests write" in run


def test_auto_merge_defaults_off_and_is_gated_on_the_input():
    assert _call()["inputs"]["auto-merge"]["default"] is False
    step = _step("Enable auto-merge")
    assert step["env"]["GH_TOKEN"] == APP_TOKEN_EXPR
    assert GATE in step["if"]
    assert "inputs.auto-merge" in step["if"]
    assert "gh pr merge" in step["run"]
    assert "--auto" in step["run"]
    assert "--squash" in step["run"]


def test_no_input_is_interpolated_inside_any_run_script():
    offenders = [
        f"{step.get('name')}: {m}"
        for step in _steps()
        for m in re.findall(r"\$\{\{[^}]*\}\}", step.get("run", ""))
    ]
    assert not offenders, offenders
    assert "${{ inputs." not in "\n".join(s.get("run", "") for s in _steps())


def test_python_heredocs_are_quoted():
    for step in _steps():
        run = step.get("run", "")
        if "python3" in run:
            assert run.startswith("python3 - <<'PY'"), step.get("name")


# --- Consumer template -------------------------------------------------------


def test_template_calls_the_reusable_workflow_at_a_marked_ref():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert re.search(
        r"uses: Claire-s-Monster/ci-framework/\.github/workflows/"
        r"reusable-pixi-lock-refresh\.yml@v\d+\.\d+\.\d+\s+#\s*x-release-please-version",
        text,
    )


def test_template_triggers_weekly_and_manually_and_passes_no_secrets():
    doc = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    on = doc.get(True) or doc["on"]
    assert on["schedule"] == [{"cron": "0 6 * * 1"}]
    assert "workflow_dispatch" in on
    job = next(iter(doc["jobs"].values()))
    assert job["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
        "actions": "write",
    }
    assert "secrets" not in job


def test_template_shows_inputs_commented_out():
    text = TEMPLATE.read_text(encoding="utf-8")
    for name in _call()["inputs"]:
        assert re.search(rf"^\s*#\s*{re.escape(name)}:", text, re.MULTILINE), name
    assert "with:" not in re.sub(r"^\s*#.*$", "", text, flags=re.MULTILINE)


def test_only_the_marked_template_is_a_release_please_extra_file():
    config = json.loads(RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"))
    extra = {entry["path"] for entry in config["extra-files"]}
    assert TEMPLATE.as_posix() in extra
    assert REUSABLE.as_posix() not in extra
