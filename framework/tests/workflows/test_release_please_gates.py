"""Jobs gated on release-please's `release_created` must compare it to 'true'.

Job outputs are strings, so a bare `if: needs.x.outputs.release_created` is
truthy for 'false' too. Every job `if` that references release_created must use
the explicit `== 'true'` form.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/release-please.yml")
GATE = "release_created"
EXPLICIT = "release_created == 'true'"


def _gated_jobs(workflow: dict) -> dict[str, str]:
    jobs = workflow.get("jobs", {})
    return {
        name: str(job["if"])
        for name, job in jobs.items()
        if GATE in str(job.get("if", ""))
    }


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_release_created_gates_are_explicit() -> None:
    gated = _gated_jobs(_load())
    assert gated, "no job gated on release_created found; guard would be vacuous"
    bare = {name: cond for name, cond in gated.items() if EXPLICIT not in cond}
    assert not bare, f"jobs gate on release_created without == 'true': {bare}"


def test_classifier_detects_bare_gate() -> None:
    bare = {"jobs": {"a": {"if": "needs.r.outputs.release_created"}}}
    good = {"jobs": {"a": {"if": "needs.r.outputs.release_created == 'true'"}}}
    assert EXPLICIT not in _gated_jobs(bare)["a"]
    assert EXPLICIT in _gated_jobs(good)["a"]
