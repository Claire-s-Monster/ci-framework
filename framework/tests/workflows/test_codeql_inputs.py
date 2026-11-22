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


def test_job_condition_keeps_codeql_opt_in_and_language_gate(doc):
    cond = doc["jobs"]["sast-codeql"]["if"]
    assert "inputs.codeql " in cond
    assert "needs.detect-changes.outputs.has_codeql" in cond
