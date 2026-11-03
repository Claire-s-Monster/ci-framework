# Pixi Lock Refresh

`reusable-pixi-lock-refresh.yml` refreshes `pixi.lock` on a schedule and opens
(or updates) one signed bot pull request with the result (#387).

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

## No secrets

The workflow needs no secrets and no PAT or GPG key. It uses only the built-in
`github.token`, with job permissions `contents: write`, `pull-requests: write`
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
  on the target branch.

## Behavior

1. Check out `target-branch` (without persisted credentials). Its head commit
   is the parent of the refresh commit.
2. Run `pixi update --json` (with `-e` for each name in `environments`).
3. If `pixi.lock` is unchanged, stop cleanly. Every later step is gated on the change.
4. Run the conda-first check on the refreshed lock (below).
5. Create the signed commit of `pixi.lock` as `chore(deps): refresh pixi.lock`
   via the API and force-move `branch-name` to it.
6. Edit the open PR from `branch-name` into `target-branch` if there is one,
   otherwise create it.
7. Dispatch `ci-workflow` on `branch-name`.

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

jobs:
  refresh:
    permissions:
      contents: write
      pull-requests: write
      actions: write
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-pixi-lock-refresh.yml@<tag>
```

**Until the first release containing this workflow, callers must pin
`@development`**: a tag cut before it does not have the file, and the template's
`@v4.0.0` marker is only bumped by release-please at release time.

Optional inputs: `target-branch` (default `development`), `branch-name`
(`chore/pixi-lock-refresh`), `environments` (empty = all), `auto-merge`,
`pixi-version` (default matches `reusable-ci.yml`), `package-path` (`.`),
`conda-first-check` (`enforce`), `conda-first-allow` (`hb-*`), `ci-workflow`
(`ci.yml`; the workflow file dispatched on `branch-name`, empty disables it).
