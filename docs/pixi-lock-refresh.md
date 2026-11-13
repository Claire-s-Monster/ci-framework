# Pixi Lock Refresh

`reusable-pixi-lock-refresh.yml` refreshes `pixi.lock` on a schedule and opens
(or updates) one signed bot pull request with the result (#387).

## Dependabot and pixi

Dependabot's `pip` ecosystem ignores `[tool.pixi.*]` tables and `pixi.lock`, so
on a pixi project it does nothing. Delete the `pip` block from
`templates/github/dependabot.yml` in your copy, use this workflow for lock
updates, and keep Dependabot for `github-actions`.

## Why

A lock file that is only touched by hand drifts: security fixes in conda-forge
never reach CI, and the eventual catch-up is one large, hard-to-review jump.
This workflow runs `pixi update` weekly and puts the delta in front of your CI
as a normal PR. Its body lists every change, one table per environment, with
identical changes across platforms collapsed into one row:

| Package | Platform(s) | Old → New | Source |
|---------|-------------|-----------|--------|
| `mypy` | linux-64 | 1.17.0 → 2.4.1 | conda |

Added packages show `— → x`, removed ones `x → —`. When `pixi update` changes
nothing, the job ends with a notice and no PR is opened.

## Token modes

The workflow has two caller shapes. It declares no `permissions` of its own: the
job inherits the caller's `GITHUB_TOKEN` grant, so each shape sets that grant in
the caller.

| | Default (zero secrets) | Optional GitHub App |
|---|---|---|
| Secrets | none | `APP_CLIENT_ID`, `APP_PRIVATE_KEY` |
| Caller permissions | `contents`, `pull-requests`, `actions`: write | `contents: read` |
| Commit, PR, auto-merge token | `github.token` | short-lived App token |
| CI on the PR | `workflow_dispatch` of `ci-workflow` | triggered natively by the App's push and PR |
| Auto-merge triggers push workflows | no | yes |
| "Allow GitHub Actions to create and approve pull requests" | required | not needed |
| Scorecard Token-Permissions alerts | 2 per repository | none |

The mode is chosen by the secrets: both set selects the App path, both unset
selects `github.token`. Setting exactly one fails the job with an
`App credentials incomplete` error naming the missing secret. The secret values
are never printed.

### GitHub App setup

1. Create a GitHub App with repository permissions **Contents: Read and write**
   and **Pull requests: Read and write** (Metadata: read is implied).
2. Install it on the repository.
3. Store the App's client ID and a generated private key as repository (or
   organization) secrets, for example `LOCK_REFRESH_APP_CLIENT_ID` and
   `LOCK_REFRESH_APP_PRIVATE_KEY`.
4. In the caller, set `permissions: contents: read` and pass the secrets (the
   template has the commented-out shape):

   ```yaml
   jobs:
     refresh:
       permissions:
         contents: read
       uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-pixi-lock-refresh.yml@<tag>
       secrets:
         APP_CLIENT_ID: ${{ secrets.LOCK_REFRESH_APP_CLIENT_ID }}
         APP_PRIVATE_KEY: ${{ secrets.LOCK_REFRESH_APP_PRIVATE_KEY }}
   ```

The token is minted by `actions/create-github-app-token` for the current
repository only, with `contents: write` and `pull-requests: write`. The commit is
still created through `createCommitOnBranch`, so it is GitHub-signed and the
verified-commit check applies to both paths. There is no CI dispatch on the App
path, so `actions: write` and `workflow_dispatch` in your CI are not needed.

On the App path the token is minted at the start of every run, including runs
where the lock is already current. A wrong client ID or private key, a missing
installation, or missing App permissions therefore fails the run immediately,
and a manual `workflow_dispatch` of the caller is a complete setup check. The
token is revoked at job end by the action's post step.

## Default mode: no secrets

The default needs no secrets and no PAT or GPG key. It uses only the built-in
`github.token`, with caller permissions `contents: write`, `pull-requests: write`
and `actions: write` (the last one is for the CI dispatch).

**One-time prerequisites per repository:**

1. Your CI workflow (default `ci.yml`) declares `workflow_dispatch:` under `on:`.
   Both CI templates in `templates/github/workflows/` already do.
2. Enable Settings > Actions > General > "Allow GitHub Actions to create and
   approve pull requests". It can be scripted:

   ```bash
   gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
     -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true
   ```

**Signed commit.** The commit is created through the GraphQL
`createCommitOnBranch` mutation, so GitHub signs it and shows it as Verified.
The job checks `commit.verification.verified` and refuses to publish an
unsigned commit. The commit is built on a temporary ref
(`<branch-name>-tmp-<run id>-<attempt>`, deleted afterwards) and `branch-name`
is then moved to it in one force update. Building on `branch-name` directly
would first need a reset to a commit already in `target-branch`, which GitHub
can treat as merging or emptying an open PR.

**CI on the PR.** Events caused by `github.token` do not start workflows, with
one documented exception: `workflow_dispatch`. After the PR step, the job runs
`gh workflow run <ci-workflow> --ref <branch-name>`. The dispatched check runs
attach to the head commit of `branch-name`, which is the PR head, so required
checks are satisfied. Set `ci-workflow: ''` to disable the dispatch.

**Caveats.**

- The CI run is a `workflow_dispatch` run, not a `pull_request` run.
  `reusable-ci.yml`'s `self-heal` placeholder job also runs on dispatch; it is
  a harmless echo.
- `dorny/paths-filter` in `reusable-ci.yml` diffs against the repository default
  branch on non-PR events. `pixi.lock` is in the `src` filter, so tests do run.
- An auto-merge performed with `github.token` does not trigger push workflows
  on the target branch. On the App path it does.
- The lock is sent base64-encoded in a single GraphQL `createCommitOnBranch`
  request (about 4/3 of the lock's size). The step logs both sizes, so a request
  rejected for size is visible in the job log.

### Scorecard Token-Permissions alerts

OpenSSF Scorecard (`TokenPermissionsID`) cannot see into a reusable workflow. It
scores the caller's job-level permissions and raises two high alerts per
consumer repository, both on the caller file (`pixi-lock-refresh.yml`):

- `jobLevel 'contents' permission set to 'write'`
- `jobLevel 'actions' permission set to 'write'`

They are expected. Each scope backs one operation, all done with `github.token`:

| Scope | Operation |
|-------|-----------|
| `contents: write` | API-signed commit (GraphQL `createCommitOnBranch`) |
| `pull-requests: write` | open or update the PR and enable auto-merge |
| `actions: write` | `gh workflow run` of the CI workflow on the refresh branch, because PRs and pushes made with `github.token` do not start workflows |

Splitting the dispatch into a separate job does not help: Scorecard scores every
job-level write. The template does set a top-level `permissions: {}`, which
Scorecard also checks for.

**Fix:** use the optional GitHub App shape (see "Token modes"). The caller then
grants only `contents: read`, and the alerts do not appear (#406).

**For repositories that stay on the zero-secret default**, dismiss each alert as
"Won't fix" with this comment (280 characters or fewer, GitHub's dismissal
comment limit):

```text
Won't fix: pixi-lock-refresh needs job-level contents:write (API-signed commit), pull-requests:write (PR) and actions:write (dispatch CI; github.token PRs don't trigger workflows). Top-level permissions: {}. The optional GitHub App shape avoids this (ci-framework#406)
```

If a repository's first Scorecard upload happens on a pull request, every
pre-existing finding shows as new on that PR, because the target branch has no
baseline yet. This is a one-time effect, not a regression.

## Behavior

1. Validate `branch-name`. On the App path, mint the App token now, on every
   run, before any other work.
2. Check out `target-branch` (without persisted credentials). Its head commit
   is the parent of the refresh commit.
3. Run `pixi update --json` (with `-e` for each name in `environments`).
4. If `pixi.lock` is unchanged, stop cleanly. Every later step is gated on the change.
5. Run the conda-first check on the refreshed lock (below).
6. Create the signed commit of `pixi.lock` as `chore(deps): refresh pixi.lock`
   via the API and force-move `branch-name` to it.
7. Edit the open PR from `branch-name` into `target-branch` if there is one,
   otherwise create it.
8. Dispatch `ci-workflow` on `branch-name` (default mode only; skipped on the
   App path).

`branch-name` is **bot-owned**: it is force-updated on every run, so do not put
work on it. The workflow refuses a `branch-name` equal to `target-branch`.
Concurrent runs for the same repository and branch queue instead of cancelling.

## Conda-first behavior

The refreshed lock is checked against the conda-first policy (#386): a
dependency may come from PyPI only when conda-forge has no package for it.
`conda-first-check` is one of:

- `enforce` (default): any PyPI package outside `conda-first-allow` fails the
  job **before** a commit, branch or PR exists.
- `warn`: annotates each offender and continues.
- `off`: skips the check.

`conda-first-allow` takes comma- or newline-separated `fnmatch` patterns on
package names. The default is `hb-*`, matching `reusable-ci.yml`, because
hb-* sub-packages are not on conda-forge. The script is the same
`scripts/check_conda_first.py`, inlined as a byte-identical heredoc.

Local-path sources (for example a project's own editable self-install,
`path = ".", editable = true`) are not PyPI packages and are exempt; remote
packages stay checked even when editable.

## Auto-merge

`auto-merge` defaults to `false`. When `true`, the last step runs
`gh pr merge --auto --squash`, so the PR merges once its required checks pass.
That needs "Allow auto-merge" enabled on the repository and required status
checks on the target branch; without checks, auto-merge would merge the lock
untested.

## Consumer example

Copy `templates/github/workflows/pixi-lock-refresh-template.yml`. It runs
Mondays at 06:00 UTC and on `workflow_dispatch`:

```yaml
name: Pixi Lock Refresh
on:
  schedule:
    - cron: '0 6 * * 1'
  workflow_dispatch:

# Top level grants nothing (OpenSSF Token-Permissions); the job scopes writes.
permissions: {}

jobs:
  refresh:
    # Default shape (zero secrets). Scorecard flags the contents/actions writes;
    # see docs/pixi-lock-refresh.md "Scorecard Token-Permissions alerts".
    permissions:
      contents: write        # API-signed commit
      pull-requests: write   # open the PR and enable auto-merge
      actions: write         # dispatch CI on the refresh branch (github.token PRs don't trigger workflows)
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-pixi-lock-refresh.yml@<tag>
```

**Until the first release containing this workflow, callers must pin
`@development`**: a tag cut before it does not have the file, and the template's
`@<tag>  # x-release-please-version` marker is only bumped by release-please at
release time.

Optional inputs: `target-branch` (default `development`), `branch-name`
(`chore/pixi-lock-refresh`), `environments` (space-separated; empty = all), `auto-merge`,
`pixi-version` (default matches `reusable-ci.yml`), `package-path` (`.`),
`conda-first-check` (`enforce`), `conda-first-allow` (`hb-*`), `ci-workflow`
(`ci.yml`; the workflow file dispatched on `branch-name`, empty disables it),
`labels` (`dependencies,pixi`; comma-separated, empty = no labels).

## PR labels

The PR gets the labels in the `labels` input. Before creating or editing the PR,
the job runs `gh label create <label> --force` for each one, so the label exists
even in a repository that never ran [label sync](label-sync.md). If a label
cannot be created, the job emits a `::warning::` and opens the PR without that
label instead of failing. Set `labels: ''` to apply none.
