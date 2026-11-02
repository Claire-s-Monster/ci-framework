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

## Required secrets

All three are `required: true` on the workflow. Pass them from the caller.

| Secret | Purpose |
|--------|---------|
| `CI_BOT_TOKEN` | PAT that pushes the branch and opens the PR. Needs `contents: write` and `pull-requests: write` on the repository. |
| `CI_BOT_GPG_KEY` | ASCII-armored, passphrase-less GPG private key used to sign the commit. |
| `CI_BOT_GPG_KEY_ID` | Key ID of that key. |

**A `GITHUB_TOKEN` push would not trigger CI.** GitHub deliberately does not
start workflow runs for events caused by the default token, so a PR opened that
way would sit there with no checks and could never satisfy branch protection.
There is therefore no `github.token` fallback: the first step verifies
`CI_BOT_TOKEN` against `/rate_limit`, and an empty token or an HTTP 401 fails
the job with an explicit error. A job that cannot sign (empty GPG key) also
fails before pushing.

**Rotation.** PATs expire. When the token or key is rotated, update the three
repository (or organisation) secrets together. An expired token fails the
preflight with `CI_BOT_TOKEN is invalid or expired (HTTP 401)`, so the failure
is visible in the weekly run rather than silently skipping refreshes.

## Behavior

1. Preflight the token, then check out `target-branch` with it.
2. Run `pixi update --json` (with `-e` for each name in `environments`).
3. If `pixi.lock` is unchanged, stop cleanly. Every later step is gated on the change.
4. Run the conda-first check on the refreshed lock (below).
5. Commit `pixi.lock` as `chore(deps): refresh pixi.lock`, signed, and
   `git push --force-with-lease` it to `branch-name`.
6. Edit the open PR from `branch-name` into `target-branch` if there is one,
   otherwise create it.

`branch-name` is **bot-owned**: it is force-pushed on every run, so do not put
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
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-pixi-lock-refresh.yml@<tag>
    secrets:
      CI_BOT_TOKEN: ${{ secrets.CI_BOT_TOKEN }}
      CI_BOT_GPG_KEY: ${{ secrets.CI_BOT_GPG_KEY }}
      CI_BOT_GPG_KEY_ID: ${{ secrets.CI_BOT_GPG_KEY_ID }}
```

**Until the first release containing this workflow, callers must pin
`@development`**: a tag cut before it does not have the file, and the template's
`@v4.0.0` marker is only bumped by release-please at release time.

Optional inputs: `target-branch` (default `development`), `branch-name`
(`chore/pixi-lock-refresh`), `environments` (empty = all), `auto-merge`,
`pixi-version` (default matches `reusable-ci.yml`), `package-path` (`.`),
`conda-first-check` (`enforce`), `conda-first-allow` (`hb-*`).
