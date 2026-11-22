"""reusable-ci.yml exposes CodeQL tuning inputs (#468)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REUSABLE_CI = Path(".github/workflows/reusable-ci.yml")


@pytest.fixture(scope="module")
def doc() -> dict:
    return yaml.safe_load(REUSABLE_CI.read_text())


@pytest.fixture(scope="module")
def inputs(doc: dict) -> dict:
    # YAML 1.1 parses the bare `on:` key as boolean True.
    trigger = doc.get(True) or doc["on"]
    return trigger["workflow_call"]["inputs"]


@pytest.mark.parametrize(
    ("name", "type_", "default"),
    [
        ("codeql-config-file", "string", ""),
        ("codeql-packs", "string", ""),
    ],
)
def test_codeql_input_shape(inputs, name, type_, default):
    spec = inputs[name]
    assert spec["type"] == type_
    assert spec["default"] == default
    assert spec["required"] is False
    assert spec["description"].strip()


def test_init_receives_config_and_packs(doc):
    steps = doc["jobs"]["sast-codeql"]["steps"]
    init = [s for s in steps if "codeql-action/init" in s.get("uses", "")]
    assert len(init) == 1
    with_ = init[0]["with"]
    assert with_["config-file"] == "${{ inputs.codeql-config-file }}"
    assert with_["packs"] == "${{ inputs.codeql-packs }}"


def _and_operands(cond: object) -> set[str]:
    """Split a workflow `if:` into its AND operands, rejecting any `||`.

    Asserting the exact operand set (rather than substring presence) means an
    `||` or a dropped operand no longer passes.
    """
    text = " ".join(str(cond).split())
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    assert "||" not in text
    return {part.strip() for part in text.split("&&")}


def test_job_condition_keeps_codeql_opt_in_and_language_gate(doc):
    # Both gates must be required.
    assert _and_operands(doc["jobs"]["sast-codeql"]["if"]) == {
        "inputs.codeql",
        "needs.detect-changes.outputs.has_codeql == 'true'",
    }


def test_packs_description_documents_per_language_scope(inputs):
    desc = " ".join(inputs["codeql-packs"]["description"].split())
    assert "EVERY language" in desc
    assert "codeql-config-file" in desc


def test_reusable_ci_codeql_defaults_true(inputs):
    spec = inputs["codeql"]
    assert spec["type"] == "boolean"
    assert spec["default"] is True


# --- reusable-security.yml: CodeQL is opt-in (v5) ---

REUSABLE_SECURITY = Path(".github/workflows/reusable-security.yml")


@pytest.fixture(scope="module")
def sec_doc() -> dict:
    return yaml.safe_load(REUSABLE_SECURITY.read_text())


@pytest.fixture(scope="module")
def sec_inputs(sec_doc: dict) -> dict:
    trigger = sec_doc.get(True) or sec_doc["on"]
    return trigger["workflow_call"]["inputs"]


def test_security_codeql_input_defaults_false(sec_inputs):
    spec = sec_inputs["codeql"]
    assert spec["type"] == "boolean"
    assert spec["default"] is False
    assert spec["required"] is False
    assert "reusable-ci" in spec["description"]


@pytest.mark.parametrize("name", ["codeql-config-file", "codeql-packs"])
def test_security_codeql_tuning_input_shape(sec_inputs, name):
    spec = sec_inputs[name]
    assert spec["type"] == "string"
    assert spec["default"] == ""
    assert spec["required"] is False


def test_security_job_condition_requires_input_and_language(sec_doc):
    assert _and_operands(sec_doc["jobs"]["sast-codeql"]["if"]) == {
        "inputs.codeql",
        "needs.detect-languages.outputs.has_codeql == 'true'",
    }


def test_security_init_receives_config_and_packs(sec_doc):
    steps = sec_doc["jobs"]["sast-codeql"]["steps"]
    init = [s for s in steps if "codeql-action/init" in s.get("uses", "")]
    assert len(init) == 1
    with_ = init[0]["with"]
    assert with_["config-file"] == "${{ inputs.codeql-config-file }}"
    assert with_["packs"] == "${{ inputs.codeql-packs }}"


def test_security_announces_codeql_move_when_skipped(sec_doc):
    steps = sec_doc["jobs"]["security-summary"]["steps"]
    notice = [s for s in steps if s.get("name") == "Announce CodeQL move"]
    assert len(notice) == 1
    assert _and_operands(notice[0]["if"]) == {
        "!inputs.codeql",
        "needs.detect-languages.outputs.has_codeql == 'true'",
    }
    assert "::warning title=CodeQL moved to reusable-ci::" in notice[0]["run"]
    assert "GITHUB_STEP_SUMMARY" in notice[0]["run"]
    assert sec_doc["jobs"]["security-summary"]["if"] == "always()"
