"""Tests for the opt-in conda-first lock check (#386).

Policy: a dependency may come from PyPI only when conda-forge has no package
for it. The script under test is scripts/check_conda_first.py, loaded here by
path. reusable-ci.yml inlines it as a `python3 - <<'PY'` heredoc (a new
composite action would not exist at the release-please-pinned ref until a
release bumps the marker), so a test pins the heredoc to the standalone file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT = Path("scripts/check_conda_first.py")
REUSABLE_CI = Path(".github/workflows/reusable-ci.yml")
STEP_NAME = "Conda-first lock check"
HEREDOC_OPEN = "python3 - <<'PY'\n"
HEREDOC_CLOSE = "\nPY\n"

_spec = importlib.util.spec_from_file_location("check_conda_first", SCRIPT)
assert _spec is not None and _spec.loader is not None
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

# The `environments:` block repeats `- pypi: <url>` references; only the
# top-level `packages:` list may be counted.
_ENVIRONMENTS = """\
version: 6
environments:
  default:
    channels:
    - url: https://conda.anaconda.org/conda-forge/
    packages:
      linux-64:
      - conda: https://conda.anaconda.org/conda-forge/linux-64/python-3.12.0-h1_0.conda
      - pypi: https://files.pythonhosted.org/packages/x/ruff-0.4.0-py3-none-any.whl
"""

CLEAN_LOCK = (
    _ENVIRONMENTS
    + """\
packages:
- conda: https://conda.anaconda.org/conda-forge/linux-64/python-3.12.0-h1_0.conda
  sha256: abc
  name: python
  version: 3.12.0
- conda: https://conda.anaconda.org/conda-forge/noarch/pytest-8.0.0-pyhd8ed1ab_0.conda
  sha256: def
"""
)

VIOLATING_LOCK = (
    _ENVIRONMENTS
    + """\
packages:
- conda: https://conda.anaconda.org/conda-forge/linux-64/python-3.12.0-h1_0.conda
  sha256: abc
- pypi: https://files.pythonhosted.org/packages/x/ruff-0.4.0-py3-none-any.whl
  name: ruff
  version: 0.4.0
  requires_dist:
  - name-like-string
"""
)

HB_LOCK = (
    _ENVIRONMENTS
    + """\
packages:
- pypi: git+https://github.com/Claire-s-Monster/hb-strategy-sandbox.git@abc123
  name: hb-strategy-sandbox
  version: 0.1.0
- pypi: https://files.pythonhosted.org/packages/y/HB_Other-1.0.tar.gz
  name: HB_Other
  version: 1.0.0
"""
)


def _run(tmp_path, capsys, lock: str | None, mode: str, allow: str = "hb-*"):
    lock_file = tmp_path / "pixi.lock"
    if lock is not None:
        lock_file.write_text(lock)
    code = check.run(mode, allow, str(lock_file))
    return code, capsys.readouterr().out


def test_parser_detects_pypi_entries_in_fixture():
    """Self-test: the parser must see the pypi entries, or 'clean' is vacuous."""
    assert check.parse_pypi_packages(VIOLATING_LOCK) == ["ruff"]
    assert check.parse_pypi_packages(HB_LOCK) == ["hb-strategy-sandbox", "HB_Other"]
    assert check.parse_pypi_packages(CLEAN_LOCK) == []


def test_parser_ignores_environments_block():
    assert check.parse_pypi_packages(_ENVIRONMENTS) == []


def test_parser_falls_back_to_url_when_name_missing():
    lock = (
        "packages:\n- pypi: https://h/p/ruff-0.4.0-py3-none-any.whl\n  version: 0.4.0\n"
    )
    assert check.parse_pypi_packages(lock) == ["ruff"]


def test_violating_lock_fails_in_enforce(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, VIOLATING_LOCK, "enforce")
    assert code == 1
    assert "::error" in out and "'ruff'" in out


def test_violating_lock_warns_in_warn(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, VIOLATING_LOCK, "warn")
    assert code == 0
    assert "::warning" in out and "'ruff'" in out
    assert "::error" not in out


def test_duplicate_platform_wheels_count_once(tmp_path, capsys):
    """pixi.lock has one pypi entry per platform wheel; the same name counts once."""
    lock = (
        _ENVIRONMENTS
        + """\
packages:
- pypi: https://files.pythonhosted.org/packages/x/ruff-0.4.0-cp312-manylinux_x86_64.whl
  name: ruff
  version: 0.4.0
- pypi: https://files.pythonhosted.org/packages/x/ruff-0.4.0-py3-none-macosx_arm64.whl
  name: ruff
  version: 0.4.0
"""
    )
    code, out = _run(tmp_path, capsys, lock, "warn")
    assert code == 0
    assert out.count("::warning") == 1
    assert "conda-first-check: 1 PyPI package(s) outside the allowlist." in out


def test_clean_lock_passes(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, CLEAN_LOCK, "enforce")
    assert code == 0
    assert "::error" not in out and "::warning" not in out


def test_hb_entries_are_exempt_by_name(tmp_path, capsys):
    """Both the git+ hb-* entry and the non-git hb-* (HB_Other) are exempt."""
    code, out = _run(tmp_path, capsys, HB_LOCK, "enforce")
    assert code == 0
    assert "::error" not in out and "::warning" not in out


def test_allow_accepts_newline_separated_patterns(tmp_path, capsys):
    code, _ = _run(tmp_path, capsys, VIOLATING_LOCK, "enforce", allow="hb-*\nRuff")
    assert code == 0


def test_empty_allow_exempts_nothing(tmp_path, capsys):
    code, _ = _run(tmp_path, capsys, HB_LOCK, "enforce", allow="")
    assert code == 1


def test_off_skips(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, VIOLATING_LOCK, "off")
    assert code == 0
    assert "::error" not in out and "::warning" not in out


def test_invalid_mode_is_rejected(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, CLEAN_LOCK, "strict")
    assert code == 1
    assert "::error" in out


def test_missing_lock_is_a_notice_and_passes(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, None, "enforce")
    assert code == 0
    assert "::notice" in out


@pytest.mark.parametrize("name", ["HB_Foo", "hb.foo", "Hb-Foo"])
def test_name_normalization(name):
    assert check.is_allowed(name, check.parse_allow("hb-*"))


def test_workflow_wires_the_check_after_install_dependencies():
    """reusable-ci.yml must expose both inputs and run the action in python-quality."""
    doc = yaml.safe_load(REUSABLE_CI.read_text())
    # YAML 1.1 parses the bare `on:` key as boolean True.
    trigger = doc.get(True) or doc["on"]
    inputs = trigger["workflow_call"]["inputs"]
    assert inputs["conda-first-check"]["default"] == "warn"
    assert inputs["conda-first-allow"]["default"] == "hb-*"
    steps = doc["jobs"]["python-quality"]["steps"]
    names = [s.get("name") for s in steps]
    assert names.index(STEP_NAME) == names.index("Install Dependencies") + 1
    step = steps[names.index(STEP_NAME)]
    assert "uses" not in step
    assert step["working-directory"] == "${{ inputs.package-path }}"
    assert step["env"]["CONDA_FIRST_MODE"] == "${{ inputs.conda-first-check }}"
    assert step["env"]["CONDA_FIRST_ALLOW"] == "${{ inputs.conda-first-allow }}"
    assert "${{" not in step["run"], "inputs must reach the script via env only"


def _inline_script() -> str:
    """Heredoc body of the python-quality step, wrapper stripped."""
    doc = yaml.safe_load(REUSABLE_CI.read_text())
    steps = doc["jobs"]["python-quality"]["steps"]
    run = next(s for s in steps if s.get("name") == STEP_NAME)["run"]
    assert run.startswith(HEREDOC_OPEN), (
        "run must start with a quoted-heredoc python3 -"
    )
    assert run.endswith(HEREDOC_CLOSE), "run must end with the PY terminator"
    return run[len(HEREDOC_OPEN) : -len(HEREDOC_CLOSE)] + "\n"


def test_inline_script_extraction_is_not_vacuous():
    body = _inline_script()
    assert body.strip()
    assert "def parse_pypi_packages" in body


def test_inline_script_matches_standalone_script():
    assert _inline_script() == SCRIPT.read_text()
