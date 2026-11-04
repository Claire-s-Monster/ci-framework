"""Tests for the opt-in pip policy check (#399).

The script under test is scripts/check_pip_policy.py, loaded here by path.
reusable-ci.yml inlines it as a `python3 - <<'PY'` heredoc (a new composite
action would not exist at the release-please-pinned ref until a release bumps
the marker), so a test pins the heredoc to the standalone file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT = Path("scripts/check_pip_policy.py")
REUSABLE_CI = Path(".github/workflows/reusable-ci.yml")
STEP_NAME = "Pip policy check"
HEREDOC_OPEN = "python3 - <<'PY'\n"
HEREDOC_CLOSE = "\nPY\n"

_spec = importlib.util.spec_from_file_location("check_pip_policy", SCRIPT)
assert _spec is not None and _spec.loader is not None
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

EXTRAS_TOML = '[project]\nname = "x"\n\n[project.optional-dependencies]\ndev = ["pytest"]\ndocs = []\n'
EMPTY_EXTRAS_TOML = '[project]\nname = "x"\n\n[project.optional-dependencies]\n'
NO_EXTRAS_TOML = '[project]\nname = "x"\n'


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _run(tmp_path, capsys, mode: str, pyproject: str | None = NO_EXTRAS_TOML):
    py = tmp_path / "pyproject.toml"
    if pyproject is not None:
        py.write_text(pyproject)
    code = check.run(mode, str(py), str(tmp_path))
    return code, capsys.readouterr().out


# --- extras rule ---------------------------------------------------------------


def test_extras_lists_names():
    assert check.find_extras(EXTRAS_TOML) == ["dev", "docs"]


def test_extras_empty_or_missing_table_is_fine():
    assert check.find_extras(EMPTY_EXTRAS_TOML) == []
    assert check.find_extras(NO_EXTRAS_TOML) == []


def test_extras_enforce_fails_and_names_extra(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, "enforce", EXTRAS_TOML)
    assert code == 1
    assert "::error title=optional-dependencies extra::Extra 'dev'" in out
    assert "issues/399" in out


def test_missing_pyproject_is_a_notice(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, "enforce", None)
    assert code == 0
    assert "::notice" in out


def test_invalid_toml_is_a_violation_not_a_crash(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, "enforce", "[project\nname =")
    assert code == 1
    assert "::error title=pip-policy-check invalid toml" in out
    code, out = _run(tmp_path, capsys, "warn", "[project\nname =")
    assert code == 0
    assert "::warning title=pip-policy-check invalid toml" in out


# --- pip regex -----------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "pip install x",
        "pip3 install x",
        "uv pip install x",
        "pixi run pip install -e .",
        "python -m pip install x",
        "run: pip install x",
        "python -m pip install requests -e .",
        "python -m pip install -r req.txt -e .",
    ],
)
def test_pip_positives(line):
    assert check.pip_violations_in_text(line) == [(1, line)]


@pytest.mark.parametrize(
    "line",
    [
        "python -m pip install -e .",
        "python3 -m pip install --editable .",
        "python -m pip install --no-build-isolation -e .",
        "python3 -m pip install -q --no-deps --editable .",
        "python -m pip install --editable=.",
        "# pip install x",
        "    # pip install x",
        "pip install x  # pip-policy: allow",
        "pipx install foo",
        "pip-compile requirements.in",
    ],
)
def test_pip_negatives(line):
    assert check.pip_violations_in_text(line) == []


def test_line_numbers_are_one_based():
    assert check.pip_violations_in_text("a\nb\npip install x\n") == [
        (3, "pip install x")
    ]


# --- backslash continuations ---------------------------------------------------


def test_continued_editable_install_is_exempt():
    text = "python -m pip install \\\n  --no-build-isolation \\\n  -e ."
    assert check.pip_violations_in_text(text) == []


def test_continued_violation_reports_first_physical_line():
    text = "pip install \\\n  requests\npip install y"
    assert [n for n, _ in check.pip_violations_in_text(text)] == [1, 3]


# --- file selection ------------------------------------------------------------


def test_file_selection(tmp_path):
    scanned = [
        ".github/workflows/ci.yml",
        ".github/actions/foo/action.yaml",
        "actions/bar/action.yml",
        "scripts/x.sh",
        "scripts/y.bash",
        "Makefile",
        "Dockerfile",
        "docker/Dockerfile.dev",
        "pixi.toml",
        "pyproject.toml",
    ]
    skipped = [
        "README.md",
        "docs/a.rst",
        "notes.txt",
        "foo.py",
        "other.yml",
        ".pixi/envs/default/x.sh",
        "node_modules/pkg/y.sh",
        ".venv/bin/z.sh",
        "venv/bin/z.sh",
        "lib/site-packages/pkg/w.sh",
        "__pycache__/v.sh",
        ".git/hooks/pre-commit.sh",
    ]
    for rel in scanned + skipped:
        _write(tmp_path, rel, "x\n")
    found = {
        p.relative_to(tmp_path).as_posix() for p in check.iter_scanned_files(tmp_path)
    }
    assert found == set(scanned)


# --- run() modes ---------------------------------------------------------------


def _dirty(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", "steps:\n  - run: pip install x\n")


def test_enforce_fails_on_bare_pip(tmp_path, capsys):
    _dirty(tmp_path)
    code, out = _run(tmp_path, capsys, "enforce")
    assert code == 1
    assert (
        "::error file=.github/workflows/ci.yml,line=2,title=bare pip install::" in out
    )


def test_warn_never_fails(tmp_path, capsys):
    _dirty(tmp_path)
    code, out = _run(tmp_path, capsys, "warn", EXTRAS_TOML)
    assert code == 0
    assert "::warning" in out and "::error" not in out
    assert "pip-policy-check: 3 violation(s)." in out


def test_off_skips(tmp_path, capsys):
    _dirty(tmp_path)
    code, out = _run(tmp_path, capsys, "off", EXTRAS_TOML)
    assert code == 0
    assert "::error" not in out and "::warning" not in out


def test_invalid_mode_is_rejected(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, "strict")
    assert code == 1
    assert "::error" in out


def test_clean_tree_passes_enforce(tmp_path, capsys):
    _write(tmp_path, "scripts/ok.sh", "python -m pip install -e .\n")
    code, out = _run(tmp_path, capsys, "enforce")
    assert code == 0
    assert "pip-policy-check: 0 violation(s)." in out


def test_escape_property():
    assert check._escape_property("a,b:c%d\n") == "a%2Cb%3Ac%25d%0A"


def test_file_property_is_escaped_in_output(tmp_path, capsys):
    _write(tmp_path, "a,b/run.sh", "pip install x\n")
    code, out = _run(tmp_path, capsys, "enforce")
    assert code == 1
    assert "file=a%2Cb/run.sh,line=1," in out


# --- python without tomllib ----------------------------------------------------


def test_missing_tomllib_is_reported_not_a_crash(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(check, "tomllib", None)
    code, out = _run(tmp_path, capsys, "enforce")
    assert code == 1
    assert "::error title=pip-policy-check python" in out
    code, out = _run(tmp_path, capsys, "warn")
    assert code == 0
    assert "::warning title=pip-policy-check python" in out
    code, out = _run(tmp_path, capsys, "off")
    assert code == 0
    assert "::error" not in out and "::warning" not in out


def test_ci_framework_itself_passes_enforce(capsys):
    """Dogfood: this repo must satisfy its own policy (marked lines are exempt)."""
    code = check.run("enforce", "pyproject.toml", ".")
    out = capsys.readouterr().out
    assert code == 0, out


# --- workflow wiring -----------------------------------------------------------


def test_workflow_wires_the_check_after_conda_first():
    doc = yaml.safe_load(REUSABLE_CI.read_text())
    # YAML 1.1 parses the bare `on:` key as boolean True.
    trigger = doc.get(True) or doc["on"]
    inputs = trigger["workflow_call"]["inputs"]
    assert inputs["pip-policy-check"]["default"] == "off"
    assert inputs["pip-policy-check"]["type"] == "string"
    steps = doc["jobs"]["python-quality"]["steps"]
    names = [s.get("name") for s in steps]
    assert names.index(STEP_NAME) == names.index("Conda-first lock check") + 1
    assert names.index("Run Linters and Formatters") == names.index(STEP_NAME) + 1
    step = steps[names.index(STEP_NAME)]
    assert "uses" not in step
    assert step["working-directory"] == "${{ inputs.package-path }}"
    assert step["env"]["PIP_POLICY_MODE"] == "${{ inputs.pip-policy-check }}"
    assert step["env"]["REPO_ROOT"] == "${{ github.workspace }}"
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
    assert "def pip_violations_in_text" in body


def test_inline_script_matches_standalone_script():
    assert _inline_script() == SCRIPT.read_text()
