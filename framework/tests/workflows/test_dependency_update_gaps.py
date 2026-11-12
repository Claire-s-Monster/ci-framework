"""Guards for the pixi dependency-update gaps.

Covers reusable-label-sync.yml and its template, the `audit-task` input and
exit-127 handling of the Python dependency audit jobs in reusable-ci.yml and
reusable-security.yml, and the `labels` input of reusable-pixi-lock-refresh.yml.

Walk-the-tree style assertions can pass vacuously, so every lookup asserts that
the step or key it inspects was actually found before checking its content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TEMPLATES = REPO_ROOT / "templates" / "github"
LABEL_SYNC = WORKFLOWS / "reusable-label-sync.yml"
LABEL_SYNC_TEMPLATE = TEMPLATES / "workflows" / "label-sync-template.yml"
LOCK_REFRESH = WORKFLOWS / "reusable-pixi-lock-refresh.yml"
LOCK_REFRESH_TEMPLATE = TEMPLATES / "workflows" / "pixi-lock-refresh-template.yml"
REUSABLE_CI = WORKFLOWS / "reusable-ci.yml"
REUSABLE_SECURITY = WORKFLOWS / "reusable-security.yml"

STANDARD_LABELS = {
    "dependencies",
    "python",
    "github-actions",
    "docker",
    "nodejs",
    "pixi",
}
EXPR_RE = re.compile(r"\$\{\{")


def load(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{path.name} did not parse as a mapping"
    return doc


def workflow_inputs(doc: dict) -> dict:
    # PyYAML parses the bare key `on` as boolean True.
    on_block = doc.get("on", doc.get(True))
    assert isinstance(on_block, dict), "no `on:` mapping found"
    inputs = on_block["workflow_call"]["inputs"]
    assert inputs, "workflow_call inputs not found"
    return inputs


def find_step(doc: dict, job: str, name: str) -> tuple[list, int, dict]:
    steps = doc["jobs"][job]["steps"]
    for index, step in enumerate(steps):
        if step.get("name") == name:
            return steps, index, step
    raise AssertionError(f"step {name!r} not found in job {job!r}")


def has_interpolation(run_body: str) -> bool:
    """True when a `run:` body contains a `${{ }}` expression (injection)."""
    return EXPR_RE.search(run_body) is not None


# --- classifier self-tests ---------------------------------------------------


def test_interpolation_detector_self_test():
    assert has_interpolation('echo "${{ inputs.x }}"')
    assert not has_interpolation('echo "$X"')


# --- reusable-label-sync -----------------------------------------------------


def test_label_sync_permissions_are_minimal():
    doc = load(LABEL_SYNC)
    assert doc["permissions"] == {}
    assert doc["jobs"]["sync"]["permissions"] == {"issues": "write"}


def test_label_sync_is_workflow_call_only():
    on_block = load(LABEL_SYNC).get("on", load(LABEL_SYNC).get(True))
    assert set(on_block) == {"workflow_call"}


def test_label_sync_default_labels_cover_the_standard_set():
    default = workflow_inputs(load(LABEL_SYNC))["labels"]["default"]
    names = set()
    for line in default.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        assert len(parts) == 3, f"malformed default label line: {line!r}"
        assert re.fullmatch(r"[0-9A-Fa-f]{6}", parts[1]), line
        names.add(parts[0])
    assert names == STANDARD_LABELS


def test_label_sync_passes_inputs_through_env_only():
    doc = load(LABEL_SYNC)
    step = doc["jobs"]["sync"]["steps"][0]
    assert step["env"]["LABELS"] == "${{ inputs.labels }}"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert step["env"]["GH_REPO"] == "${{ github.repository }}"
    for job in doc["jobs"].values():
        for s in job["steps"]:
            if "run" in s:
                assert not has_interpolation(s["run"]), s.get("name")


def test_label_sync_creates_labels_with_force_and_rejects_malformed_lines():
    run = load(LABEL_SYNC)["jobs"]["sync"]["steps"][0]["run"]
    assert 'gh label create "$name"' in run
    assert "--force" in run
    assert '--color "$color"' in run
    assert '--description "' in run
    assert "exit 1" in run
    assert "continue" in run, "blank lines must be skipped"


def test_label_sync_has_timeout():
    assert load(LABEL_SYNC)["jobs"]["sync"]["timeout-minutes"]


def test_label_sync_template_shape():
    doc = load(LABEL_SYNC_TEMPLATE)
    on_block = doc.get("on", doc.get(True))
    assert set(on_block) == {"workflow_dispatch", "push"}
    assert set(on_block["push"]["paths"]) == {
        ".github/dependabot.yml",
        ".github/workflows/label-sync.yml",
    }
    assert doc["permissions"] == {}
    job = doc["jobs"]["labels"]
    assert job["permissions"] == {"issues": "write"}
    assert job["uses"].startswith(
        "Claire-s-Monster/ci-framework/.github/workflows/reusable-label-sync.yml@v"
    )
    marked = [
        line
        for line in LABEL_SYNC_TEMPLATE.read_text().splitlines()
        if "reusable-label-sync.yml@" in line and "# x-release-please-version" in line
    ]
    assert marked, "the uses: ref lacks the release-please marker"


def test_label_sync_template_is_registered_with_release_please():
    config = json.loads((REPO_ROOT / ".release-please-config.json").read_text())
    paths = {entry["path"] for entry in config["extra-files"]}
    assert "templates/github/workflows/label-sync-template.yml" in paths


def test_label_sync_is_documented():
    assert "label-sync.md" in (REPO_ROOT / "docs" / "README.md").read_text()
    assert (REPO_ROOT / "docs" / "label-sync.md").is_file()


# --- python-dep-audit: audit-task and exit 127 -------------------------------


def test_reusable_ci_audit_task_input_default():
    declared = workflow_inputs(load(REUSABLE_CI))["audit-task"]
    assert declared["default"] == "safety-check"
    assert declared["type"] == "string"


def test_reusable_ci_audit_step_uses_input_and_handles_127():
    doc = load(REUSABLE_CI)
    steps, index, step = find_step(doc, "python-dep-audit", "Run dependency audit")
    assert step["env"]["AUDIT_TASK"] == "${{ inputs.audit-task }}"
    run = step["run"]
    assert not has_interpolation(run)
    assert '"$AUDIT_TASK"' in run
    assert 'pixi run -e "$PIXI_ENV" "$AUDIT_TASK"' in run
    assert "-eq 127" in run
    assert "::warning" in run
    assert "status=missing-tool" in run
    assert "status=findings" in run
    assert step["continue-on-error"] is True
    gate = next(s for s in steps[index + 1 :] if s.get("name") == "Fail on CVEs")
    assert "steps.audit.outcome == 'failure'" in gate["if"]
    assert "steps.audit.outputs.status != 'missing-tool'" in gate["if"]
    assert gate["if"].startswith("inputs.fail-on-cve")


def test_reusable_security_pixi_environment_input_default():
    declared = workflow_inputs(load(REUSABLE_SECURITY))["pixi-environment"]
    assert declared["default"] == "ci"
    assert declared["type"] == "string"


def test_reusable_security_audit_job_has_no_hardcoded_ci_env():
    doc = load(REUSABLE_SECURITY)
    steps, index, step = find_step(doc, "python-dep-audit", "Run dependency audit")
    assert step["env"]["PIXI_ENV"] == "${{ inputs.pixi-environment }}"
    for s in steps:
        run = s.get("run", "")
        assert not has_interpolation(run)
        assert not re.search(r"-e ci\b", run), s.get("name")
    run = step["run"]
    assert "-eq 127" in run
    assert "::warning" in run
    assert "status=missing-tool" in run
    gate = next(s for s in steps[index + 1 :] if s.get("name") == "Fail on CVEs")
    assert "steps.audit.outcome == 'failure'" in gate["if"]
    assert "steps.audit.outputs.status != 'missing-tool'" in gate["if"]
    install = next(s for s in steps if s.get("name") == "Install Dependencies")
    assert install["env"]["PIXI_ENV"] == "${{ inputs.pixi-environment }}"


# --- lock refresh labels -----------------------------------------------------


def test_lock_refresh_labels_input_default():
    declared = workflow_inputs(load(LOCK_REFRESH))["labels"]
    assert declared["default"] == "dependencies,pixi"
    assert declared["type"] == "string"


def test_lock_refresh_pr_step_ensures_and_applies_labels():
    doc = load(LOCK_REFRESH)
    _steps, _index, step = find_step(doc, "refresh", "Open or update pull request")
    assert step["env"]["PR_LABELS"] == "${{ inputs.labels }}"
    run = step["run"]
    assert not has_interpolation(run)
    assert 'gh label create "$label" --force' in run
    assert "::warning" in run
    assert "--label" in run
    assert "--add-label" in run
    assert run.index("gh label create") < run.index("gh pr create")
    assert run.index("gh label create") < run.index("gh pr edit")


def test_lock_refresh_template_has_active_with_block():
    doc = load(LOCK_REFRESH_TEMPLATE)
    with_block = doc["jobs"]["refresh"]["with"]
    assert with_block == {
        "target-branch": "development",
        "environments": "",
        "auto-merge": False,
        "labels": "dependencies,pixi",
    }
    inputs = workflow_inputs(load(LOCK_REFRESH))
    for key, value in with_block.items():
        assert inputs[key]["default"] == value, key
    text = LOCK_REFRESH_TEMPLATE.read_text()
    assert re.search(r"^\s*#\s+APP_CLIENT_ID:", text, re.MULTILINE)
    assert re.search(r"^\s*#\s+APP_PRIVATE_KEY:", text, re.MULTILINE)
    assert "secrets" not in doc["jobs"]["refresh"]


# --- dependabot template and docs --------------------------------------------


def test_dependabot_template_warns_pixi_projects_off_pip():
    text = (TEMPLATES / "dependabot.yml").read_text()
    pip_at = text.index('package-ecosystem: "pip"')
    preamble = text[:pip_at]
    assert "PIXI PROJECTS: DELETE THIS BLOCK" in preamble
    assert "pixi-lock-refresh-template.yml" in preamble
    assert "github-actions" in preamble


def test_docs_have_dependabot_and_pixi_section():
    text = (REPO_ROOT / "docs" / "pixi-lock-refresh.md").read_text()
    assert "## Dependabot and pixi" in text
    assert "label-sync.md" in text
    assert "`labels`" in text
