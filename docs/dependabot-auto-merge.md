# Dependabot Auto-Merge

`reusable-dependabot-auto-merge.yml` approves Dependabot pull requests and
enables auto-merge on them. GitHub then merges each PR once its required checks
pass. Major updates are left for manual review unless you opt in.

## Caller

Copy `templates/github/workflows/dependabot-auto-merge-template.yml` to
`.github/workflows/dependabot-auto-merge.yml`:

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
- The calling job grants `contents: write` and `pull-requests: write`.

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
- The App token, when configured, is minted only after the PR is judged eligible.
- The workflow never checks out code, so no PR content is ever executed.
- No `${{ }}` expression appears in a `run:` script; values pass through `env:`.

## Behaviour notes

- An empty or unknown update-type (for example a digest-only bump) is NOT
  auto-merged. SHA-to-SHA action bumps may be classified as major, and then need
  `include-major: true` or a manual merge. This is narrower than ci-framework's
  previous in-repo file, which merged anything that was not major.
- The workflow refuses to run the approve and merge steps when the base branch has
  no required status checks (see Troubleshooting).

**The template's `@vX.Y.Z` ref only contains this workflow from the release that
introduced it (v4.4.0 or later).** Before that release the template's ref will
not resolve.

## GitHub App token (optional)

With the default `github.token`, an auto-merge does not start workflows on the
base branch. To use an App token instead, install a GitHub App with Contents and
Pull requests write, and store `APP_CLIENT_ID` and `APP_PRIVATE_KEY` as
**Dependabot secrets** (Settings > Secrets and variables > Dependabot). Runs
triggered by Dependabot cannot read Actions secrets. Then pass them in the caller:

```yaml
    secrets:
      APP_CLIENT_ID: ${{ secrets.APP_CLIENT_ID }}
      APP_PRIVATE_KEY: ${{ secrets.APP_PRIVATE_KEY }}
```

Set both or neither; one alone fails the run.

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
