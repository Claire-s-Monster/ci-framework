"""Guard: the ci.yml unit-test coverage step must not mask a coverage failure.

A `pytest --cov ... || pixi run ... pytest` fallback reruns the suite without
coverage when the gated run fails, turning a coverage-gate failure green.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CI_WORKFLOW = Path(".github/workflows/ci.yml")
STEP_NAME = "Run Unit Tests with Coverage"


def coverage_step_violations(step: dict) -> list[str]:
    """Return the reasons a coverage step masks failure (empty when clean)."""
    run = str(step.get("run", ""))
    problems: list[str] = []
    if "--cov" not in run:
        problems.append("run lacks --cov")
    if "||" in run:
        problems.append("run contains a '||' fallback")
    if "continue-on-error" in step:
        problems.append("step sets continue-on-error")
    return problems


def find_coverage_steps(doc: dict) -> list[dict]:
    return [
        step
        for job in (doc.get("jobs") or {}).values()
        for step in job.get("steps", []) or []
        if step.get("name") == STEP_NAME
    ]


class TestUnitTestsCoverageStepNotMasked:
    def test_step_exists(self) -> None:
        steps = find_coverage_steps(yaml.safe_load(CI_WORKFLOW.read_text()))
        assert len(steps) == 1, f"expected one {STEP_NAME!r} step, found {len(steps)}"

    def test_step_has_no_masking_fallback(self) -> None:
        steps = find_coverage_steps(yaml.safe_load(CI_WORKFLOW.read_text()))
        for step in steps:
            assert coverage_step_violations(step) == []

    def test_classifier_flags_fallback(self) -> None:
        """Self-test: the check must flag the historical masking form."""
        masked = {
            "name": STEP_NAME,
            "run": (
                "pixi run -e ci pytest framework/tests/ --cov=framework || \\\n"
                "pixi run -e quality pytest framework/tests/ -v\n"
            ),
        }
        assert "run contains a '||' fallback" in coverage_step_violations(masked)

    def test_classifier_flags_missing_cov_and_continue_on_error(self) -> None:
        bad = {"run": "pixi run pytest", "continue-on-error": True}
        assert len(coverage_step_violations(bad)) == 2

    def test_classifier_passes_clean_step(self) -> None:
        clean = {"run": "pixi run -e ci pytest framework/tests/ --cov=framework\n"}
        assert coverage_step_violations(clean) == []
