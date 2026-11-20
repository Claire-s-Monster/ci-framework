# Dependabot Auto-Merge

`reusable-dependabot-auto-merge.yml` approves Dependabot pull requests and
enables auto-merge on them. GitHub then merges each PR once its required checks
pass. Major updates are left for manual review unless you opt in.

## Caller

Copy a template to `.github/workflows/dependabot-auto-merge.yml`. There are two
modes.

**`github.token` mode**: `templates/github/workflows/dependabot-auto-merge-template.yml`.
The job needs write permissions:

```yaml
name: Dependabot Auto-Merge
on: pull_request
permissions:
  contents: read
jobs:
  auto-merge:
    permissions:
      contents: write
      pull-requests: write
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-dependabot-auto-merge.yml@vX.Y.Z
```

**App mode**: `templates/github/workflows/dependabot-auto-merge-app-template.yml`.
The job is read-only because the App token does every write; the secrets must be
Dependabot secrets (see GitHub App token below):

```yaml
name: Dependabot Auto-Merge
on: pull_request
permissions:
  contents: read
jobs:
  auto-merge:
    permissions:
      contents: read
      pull-requests: read
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-dependabot-auto-merge.yml@vX.Y.Z
    secrets:
      APP_CLIENT_ID: ${{ secrets.APP_CLIENT_ID }}
      APP_PRIVATE_KEY: ${{ secrets.APP_PRIVATE_KEY }}
```

Read-only scopes need a ci-framework release carrying #462 (the next release
after v4.4.1).

## Inputs

| Input | Type | Default | Meaning |
|---|---|---|---|
| `merge-method` | string | `squash` | `merge`, `squash` or `rebase`. Anything else fails the run. |
| `approve` | boolean | `true` | Approve the PR before enabling auto-merge. |
| `include-major` | boolean | `false` | Also handle semver-major updates. |

Secrets `APP_CLIENT_ID` and `APP_PRIVATE_KEY` are optional (see below).

## Prerequisites

- Settings > General > Pull Requests > "Allow auto-merge".
- Required status checks on the base branch. Without them auto-merge merges at once.
- Settings > Actions > General > "Allow GitHub Actions to create and approve
  pull requests", when approving with `github.token`. Otherwise set `approve: false`.
- Without App secrets the calling job grants `contents: write` and
  `pull-requests: write`. With App secrets it may grant `contents: read` and
  `pull-requests: read` (needs the release after v4.4.1).

## Migrating from a hand-copied workflow

- Replace the old file in the same PR. Overwriting
  `.github/workflows/dependabot-auto-merge.yml` with the caller is simplest. Never
  run both: two workflows would race to approve and merge the same PR. A
  hand-copied `pull_request_target` version is the riskier pattern this replaces.
- If the old file used App secrets stored as Actions secrets, re-create them as
  Dependabot secrets (see GitHub App token below).
- The caller keeps top-level `contents: read`. On the job it grants
  `contents: write` and `pull-requests: write` (`github.token` mode), or
  `contents: read` and `pull-requests: read` (App mode).
- Behaviour differs from typical hand-copied versions (see Behaviour notes and
  Security model): majors are manual by default, an unknown update-type is not
  merged, human re-runs do nothing, and approve and merge are pinned to the
  triggering head SHA.
- Dependabot PRs that are already open do not re-run after the migration merges.
  Comment `@dependabot rebase` on one to trigger the new workflow.
- If a branch protection rule or ruleset lists the old workflow's job as a
  required check, update it. The new job's check name differs.

## Security model

- The caller must use `pull_request`. Under `pull_request_target` a run has write
  access and secrets, so the workflow's first step fails any other event.
- The job runs only when the PR author is `dependabot[bot]`, `github.actor` is
  `dependabot[bot]`, `github.triggering_actor` is `dependabot[bot]` and the PR
  head is in the same repository. On a re-run `github.actor` keeps the original
  actor; only `github.triggering_actor` becomes the user who re-ran. Re-runs by
  humans and fork PRs are therefore skipped.
- Approve and merge are pinned to the event's head SHA (`commit_id` on the review,
  `--match-head-commit` on the merge), so a push after the decision is not merged.
- The App token, when configured, is minted once after the eligibility decision,
  for every PR, scoped to this repository with Contents and Pull requests write.
  Metadata and the decision use only the read-scoped `github.token`.
- The workflow never checks out code, so no PR content is ever executed.
- No `${{ }}` expression appears in a `run:` script; values pass through `env:`.

## Behaviour notes

- An empty or unknown update-type (for example a digest-only bump) is NOT
  auto-merged. SHA-to-SHA action bumps may be classified as major, and then need
  `include-major: true` or a manual merge. This is narrower than ci-framework's
  previous in-repo file, which merged anything that was not major.
- The workflow refuses to run the approve and merge steps when the base branch has
  no required status checks (see Troubleshooting).
- When Dependabot rewrites a PR into an ineligible update (for example a grouped
  update that gains a semver-major or unknown update), the workflow disables any
  auto-merge armed by an earlier run. This also disarms auto-merge that a human
  enabled on a Dependabot PR once Dependabot pushes an ineligible head.
  Re-enable it manually if intended. If disabling fails the run fails.

**The template's `@vX.Y.Z` ref only contains this workflow from the release that
introduced it (v4.4.0 or later).** Before that release the template's ref will
not resolve.

## GitHub App token (optional)

With the default `github.token`, an auto-merge does not start workflows on the
base branch. To use an App token instead, install a GitHub App with Contents and
Pull requests write, and store `APP_CLIENT_ID` and `APP_PRIVATE_KEY` as
**Dependabot secrets** (Settings > Secrets and variables > Dependabot). Runs
triggered by Dependabot cannot read Actions secrets. To avoid one copy per
repository, store them once as organization-level Dependabot secrets
(Organization settings > Secrets and variables > Dependabot) limited to the
selected repositories; this copy is separate from the Actions secrets that
pixi lock-refresh reads. Then use
`templates/github/workflows/dependabot-auto-merge-app-template.yml`, which passes
them and grants read-only job permissions:

```yaml
    permissions:
      contents: read
      pull-requests: read
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-dependabot-auto-merge.yml@vX.Y.Z
    secrets:
      APP_CLIENT_ID: ${{ secrets.APP_CLIENT_ID }}
      APP_PRIVATE_KEY: ${{ secrets.APP_PRIVATE_KEY }}
```

Set both or neither; one alone fails the run.

In App mode the token is minted once, after the eligibility decision, for every
PR, and every write step (disarm, require-checks, approve, enable) uses it. The
caller therefore needs no job-level write permissions. This requires a
ci-framework release carrying #462 (the next release after v4.4.1); earlier
releases mint the token only for eligible PRs, so the disarm step needs
`contents: write` and `pull-requests: write` on the job.

OpenSSF Scorecard's Token-Permissions check scores the caller's job-level
writes. App mode removes them.

## Push runs on the merge commit

In `github.token` mode the merge is authored by `github-actions[bot]`, and GitHub
does not run push workflows (CI, Security) for it, so the new base-branch tip has
no push runs. When auto-merge is actually being enabled in this mode, the
"Warn: no push runs after merge" step logs a `No push runs after merge` warning.
The App token mode fixes this: the merge is App-authored and push runs fire.
Without an App, re-validate the tip by hand with `workflow_dispatch`. CI can be
re-run if your `ci.yml` declares it (`standard-ci-template.yml` and
`comprehensive-ci-template.yml` do), and Security via
`templates/github/workflows/security-template.yml`.

### Migrating a local auto-merge workflow

If a repository still runs a LOCAL workflow that calls `gh pr merge --auto` with
`secrets.GITHUB_TOKEN`, it has this gap and none of the guards here. Replace it
with a caller of the reusable workflow (see "Caller") and configure the App
secrets as above.

## Troubleshooting

- **Approval failed**: enable "Allow GitHub Actions to create and approve pull
  requests", set `approve: false`, or check the App has Pull requests write.
- **Auto-merge failed**: enable "Allow auto-merge" in the repository settings and
  add required status checks on the base branch.
- **No required checks**: the base branch has no required status checks, neither
  in branch protection nor in a ruleset. `gh pr merge --auto` would merge at once
  without CI, so the run fails. Add required status checks to the base branch.
- **Cannot verify required checks**: reading branch protection or rulesets failed
  (for example the token lacks permission). The run fails closed. Check that the
  token can read the branch and repository rules.
