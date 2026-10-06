"""Guards against secrets reaching a shell command line (#258).

A `${{ secrets.X }}` expression inside a `run:` body is substituted into the
script text the runner executes, so the secret value ends up in the rendered
script. Passing it through a step-level `env:` block instead keeps it off the
command line.

#255 fixed one instance of this and silently missed two more - one of them in a
file the issue did not know existed. That is what duplicated secret handling
invites, and it is why this guard is repo-wide rather than a list of the files
known to be affected today.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")
ACTION_DIRS = (Path(".github/actions"), Path("actions"))
GPG_ACTION = Path(".github/actions/gpg-signing-setup/action.yml")

# A BARE secret interpolation - the value itself. Deliberately does NOT match
# comparisons such as `${{ secrets.X != '' }}`, which evaluate to a boolean
# rather than the secret and are safe to print.
BARE_SECRET_RE = re.compile(r"\$\{\{\s*secrets\.[A-Za-z_][A-Za-z0-9_]*\s*\}\}")


def _yaml_files() -> list[Path]:
    """Every workflow and composite action definition in the repo."""
    files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    for directory in ACTION_DIRS:
        files += sorted(directory.glob("*/action.yml"))
        files += sorted(directory.glob("*/action.yaml"))
    return files


def _iter_run_bodies(doc):
    """Yield (owner, step_name, run_body) for every step carrying a run: block."""
    if not isinstance(doc, dict):
        return
    for job_name, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield job_name, step.get("name", "<unnamed>"), step["run"]
    runs = doc.get("runs")
    if isinstance(runs, dict):
        for step in runs.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield "runs", step.get("name", "<unnamed>"), step["run"]


@pytest.mark.parametrize("path", _yaml_files(), ids=str)
def test_no_bare_secret_in_run_body(path):
    """No workflow or action may interpolate a secret value into a run: body."""
    offenders = [
        f"{owner} / {step}: {match}"
        for owner, step, body in _iter_run_bodies(yaml.safe_load(path.read_text()))
        for match in BARE_SECRET_RE.findall(body)
    ]
    assert not offenders, (
        f"{path} interpolates a secret directly into a run: body, which renders "
        "the secret into the executed script text. Pass it through a step-level "
        "env: block and reference it as a quoted shell variable (#258). "
        "Offenders: " + "; ".join(offenders)
    )


def test_secret_guard_is_not_vacuous():
    """The parametrization must cover real files, or the guard proves nothing."""
    files = _yaml_files()
    assert len(files) > 5, f"expected many workflow/action files, found {files}"
    assert any(f.name == "action.yml" for f in files), (
        "no composite action files were scanned; the guard would miss them"
    )


# --- #345: no credential in user- or system-scope git config ----------------
#
# `git config --global` writes ~/.gitconfig and `--system` writes
# /etc/gitconfig. On a GitHub-hosted runner both die with the VM, but these
# workflows are reusable, and on a consumer's self-hosted runner both files
# outlive the job - a token written there is handed to every later job on that
# runner, from any repository. cleanup-dev-files.yml did exactly this with a
# `url.<token>.insteadOf` rewrite until #345.
#
# The check is per logical line (backslash continuations joined), so it does
# NOT follow indirection: `cfg=(git config --global); "${cfg[@]}" ...` is
# invisible to it. gpg-signing-setup builds its scope that way, but only ever
# writes identity and signing keys through it, never a credential.

WIDE_SCOPE_GIT_CONFIG_RE = re.compile(r"\bgit\s+config\b[^\n]*?\s--(?:global|system)\b")

# Keys whose VALUE (or, for insteadOf, whose NAME) is a credential by nature.
CREDENTIAL_KEY_RE = re.compile(
    r"insteadof|pushinsteadof|extraheader|credential\.", re.IGNORECASE
)

# Any secret or token expression, bare or inside a larger expression such as
# `${{ secrets.CI_BOT_TOKEN || github.token }}`.
TOKEN_EXPRESSION_RE = re.compile(r"\$\{\{[^}]*\b(?:secrets\.|github\.token\b)")

SHELL_VAR_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")


def _logical_lines(body: str) -> list[str]:
    """The run body with backslash-continued lines joined into one."""
    return body.replace("\\\n", " ").splitlines()


def _secret_env_names(env: object) -> set[str]:
    """Names of step env vars whose value carries a secret or token."""
    if not isinstance(env, dict):
        return set()
    return {
        name
        for name, value in env.items()
        if isinstance(value, str) and TOKEN_EXPRESSION_RE.search(value)
    }


def wide_scope_credential_writes(body: str, env: object = None) -> list[str]:
    """Lines in a run body that put a credential into --global/--system config.

    A wide-scope `git config` line is a violation when it writes a
    credential-shaped key, interpolates a secret/token expression, or expands
    a shell variable that the step's `env:` fills from one.
    """
    tainted = _secret_env_names(env)
    offenders = []
    for line in _logical_lines(body):
        if line.lstrip().startswith("#") or not WIDE_SCOPE_GIT_CONFIG_RE.search(line):
            continue
        if (
            CREDENTIAL_KEY_RE.search(line)
            or TOKEN_EXPRESSION_RE.search(line)
            or tainted.intersection(SHELL_VAR_RE.findall(line))
        ):
            offenders.append(line.strip())
    return offenders


def _credential_scope_files() -> list[Path]:
    """`_yaml_files()` plus shipped templates, which consumers copy verbatim."""
    files = _yaml_files() + sorted(WORKFLOWS_DIR.glob("*.yml.template"))
    templates = Path("templates")
    if templates.is_dir():
        for pattern in ("*.yml", "*.yaml", "*.yml.template"):
            files += sorted(templates.rglob(pattern))
    return files


def _iter_run_steps(doc):
    """Yield (owner, step) for every step dict carrying a run: block."""
    if not isinstance(doc, dict):
        return
    for job_name, job in (doc.get("jobs") or {}).items():
        if isinstance(job, dict):
            for step in job.get("steps") or []:
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    yield job_name, step
    runs = doc.get("runs")
    if isinstance(runs, dict):
        for step in runs.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield "runs", step


# Jinja markers: `{{` not part of a GitHub `${{`, or a `{%` block.
JINJA_RE = re.compile(r"(?<!\$)\{\{|\{%")


def _credential_offenders(path: Path) -> list[str]:
    """Wide-scope credential writes in one file.

    Some files under templates/ are Jinja sources that are not valid YAML
    until rendered. Skipping them would hide exactly the kind of site this
    guard exists for, so they are scanned as plain text instead - which
    still sees credential keys and secret expressions, but not env: taint.
    """
    text = path.read_text()
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        if not JINJA_RE.search(text):
            raise
        return [f"<text> {line}" for line in wide_scope_credential_writes(text)]
    return [
        f"{owner} / {step.get('name', '<unnamed>')}: {line}"
        for owner, step in _iter_run_steps(doc)
        for line in wide_scope_credential_writes(step["run"], step.get("env"))
    ]


@pytest.mark.parametrize("path", _credential_scope_files(), ids=str)
def test_no_credential_in_wide_scope_git_config(path):
    """No step may write a credential into --global or --system git config."""
    offenders = _credential_offenders(path)
    assert not offenders, (
        f"{path} writes a credential into --global/--system git config, which "
        "outlives the job on a self-hosted runner and leaks the token to later "
        "jobs from any repository. Rely on actions/checkout's persisted "
        "credentials, or use repo-local config (#345). Offenders: "
        + "; ".join(offenders)
    )


class TestWideScopeCredentialClassifier:
    """Keeps the #345 guard from passing vacuously: it must flag what it claims to."""

    def test_flags_the_original_insteadof_rewrite(self):
        body = (
            'git_token_url="https://x-access-token:$CI_BOT_TOKEN@github.com/"\n'  # pragma: allowlist secret
            'git config --global url."${git_token_url}".insteadOf "https://github.com/"\n'
        )
        assert wide_scope_credential_writes(
            body, {"CI_BOT_TOKEN": "${{ secrets.CI_BOT_TOKEN }}"}
        )

    def test_flags_env_tainted_value_and_system_scope(self):
        body = 'git config --system http.proxyAuth "$TOKEN"\n'
        assert wide_scope_credential_writes(body, {"TOKEN": "${{ github.token }}"})

    def test_flags_continued_line(self):
        body = 'git config --global \\\n  http.https://github.com/.extraheader "AUTH"\n'
        assert wide_scope_credential_writes(body)

    def test_ignores_local_scope_and_non_credentials(self):
        body = (
            'git config url."https://x-access-token:$T@github.com/".insteadOf x\n'
            "git config --global core.autocrlf false\n"
            "global) git_config=(git config --global) ;;\n"
            "# git config --global url.x.insteadOf y\n"
        )
        assert wide_scope_credential_writes(body, {"T": "${{ secrets.X }}"}) == []

    def test_unparseable_jinja_file_is_scanned_as_text(self, tmp_path):
        path = tmp_path / "wf.yml"
        path.write_text(
            "steps:\n  {{ extra_steps }}\n"
            "  - run: git config --global url.x.insteadOf https://github.com/\n"
        )
        assert _credential_offenders(path)

    def test_unparseable_non_jinja_file_still_errors(self, tmp_path):
        path = tmp_path / "wf.yml"
        path.write_text("jobs: [unclosed\n")
        with pytest.raises(yaml.YAMLError):
            _credential_offenders(path)

    def test_walker_reaches_step_env_in_workflow_shape(self, tmp_path):
        """The pre-#345 cleanup-dev-files.yml shape, through the real file walk.

        The other classifier tests call the line predicate directly; this one
        proves the walker hands it the step's `run:` AND its step-level `env:`.
        """
        path = tmp_path / "wf.yml"
        path.write_text(
            "jobs:\n"
            "  cleanup-dev-files:\n"
            "    steps:\n"
            "      - name: Commit cleanup if files were removed\n"
            "        env:\n"
            "          CI_BOT_TOKEN: ${{ secrets.CI_BOT_TOKEN }}\n"
            "        run: |\n"
            '          git config --global url."${git_token_url}".insteadOf "https://github.com/"\n'
            '          git config --global http.proxyAuth "$CI_BOT_TOKEN"\n'
        )
        offenders = _credential_offenders(path)
        assert len(offenders) == 2, offenders
        assert all(
            o.startswith("cleanup-dev-files / Commit cleanup") for o in offenders
        )

    def test_corpus_includes_templates_and_actions(self):
        files = _credential_scope_files()
        assert any(f.name.endswith(".yml.template") for f in files), files
        assert any(f.name == "action.yml" for f in files), files
        assert Path(".github/workflows/cleanup-dev-files.yml") in files


def _isolated_env(cwd: Path, home: Path, scope: str) -> dict[str, str]:
    """Environment that cannot read or write the developer's real git config."""
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(cwd.parent),
        "GITHUB_OUTPUT": str(home / "github_output"),
        "GPG_PRIVATE_KEY": "",
        "GPG_KEY_ID": "ABCDEF",
        "GIT_USER_NAME": "Test Bot",
        "GIT_USER_EMAIL": "bot@example.invalid",
        "CONFIG_SCOPE": scope,
    }


def _run_gpg_step(cwd: Path, home: Path, scope: str) -> subprocess.CompletedProcess:
    """Execute the action's run script under bash with HOME pointed at a tmp dir.

    An empty GPG_PRIVATE_KEY makes the script skip the import and exit 0 after
    configuring identity, so no real key or keyring is involved.
    """
    script = yaml.safe_load(GPG_ACTION.read_text())["runs"]["steps"][0]["run"]
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env=_isolated_env(cwd, home, scope),
        capture_output=True,
        text=True,
        check=False,
    )


class TestGpgSigningSetupAction:
    """The composite action #258 consolidates GPG handling into.

    Nothing else lints this file - actionlint only inspects .github/workflows/
    and the yaml-lint task is scoped to that directory too - so its structure is
    asserted here rather than assumed.
    """

    def test_action_file_exists_and_parses(self):
        assert GPG_ACTION.is_file(), f"{GPG_ACTION} is missing"
        assert yaml.safe_load(GPG_ACTION.read_text()), "action.yml parsed as empty"

    def test_config_scope_defaults_to_local(self):
        """'global' leaks bot identity and commit.gpgsign into later jobs on
        persistent runners (#348), so the safe scope must be the default."""
        doc = yaml.safe_load(GPG_ACTION.read_text())
        assert doc["inputs"]["config-scope"]["default"] == "local"

    def test_is_a_composite_action_with_expected_interface(self):
        doc = yaml.safe_load(GPG_ACTION.read_text())
        assert doc["runs"]["using"] == "composite"
        expected_inputs = {
            "gpg-private-key",
            "gpg-key-id",
            "git-user-name",
            "git-user-email",
            "config-scope",
        }
        assert set(doc["inputs"]) == expected_inputs
        assert "signing-enabled" in doc.get("outputs", {})

    def test_secrets_are_passed_through_env_not_the_script_body(self):
        """The whole point of the action: the key never hits the command line."""
        step = yaml.safe_load(GPG_ACTION.read_text())["runs"]["steps"][0]
        assert "GPG_PRIVATE_KEY" in step["env"], (
            "the private key must be exposed to the script through env:"
        )
        assert "${{ inputs.gpg-private-key }}" not in step["run"], (
            "the private key must not be interpolated into the script body"
        )

    @pytest.mark.skipif(
        shutil.which("git") is None or shutil.which("bash") is None,
        reason="git and bash are required to execute the step",
    )
    class TestScopeBehavior:
        """Run the real script; HOME is always a tmp dir, never the user's."""

        def test_local_scope_fails_clearly_outside_a_work_tree(self, tmp_path):
            """Without a repo, 'local' would fail obscurely on the first git
            config write; it must instead say what to do, before writing."""
            home, work = tmp_path / "home", tmp_path / "work"
            home.mkdir()
            work.mkdir()
            result = _run_gpg_step(work, home, "local")
            assert result.returncode != 0
            assert "needs a git work tree" in result.stdout
            assert not (home / ".gitconfig").exists()

        def test_local_scope_writes_repo_config_only(self, tmp_path):
            """The point of #348: 'local' must leave ~/.gitconfig untouched."""
            home, work = tmp_path / "home", tmp_path / "work"
            home.mkdir()
            work.mkdir()
            env = _isolated_env(work, home, "local")
            subprocess.run(
                ["git", "init", "-q"],
                cwd=work,
                env=env,
                check=True,
                capture_output=True,
            )
            result = _run_gpg_step(work, home, "local")
            assert result.returncode == 0, result.stderr
            name = subprocess.run(
                ["git", "config", "--local", "user.name"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            assert name.stdout.strip() == "Test Bot"
            assert not (home / ".gitconfig").exists()
            assert "signing-enabled=false" in (home / "github_output").read_text()

        def test_global_scope_writes_home_gitconfig(self, tmp_path):
            """'global' stays available as an explicit opt-in, outside a repo."""
            home, work = tmp_path / "home", tmp_path / "work"
            home.mkdir()
            work.mkdir()
            result = _run_gpg_step(work, home, "global")
            assert result.returncode == 0, result.stderr
            assert "Test Bot" in (home / ".gitconfig").read_text()
