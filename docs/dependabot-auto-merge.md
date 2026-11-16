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
- The job runs only when the PR author is `dependabot[bot]`, the actor is
  `dependabot[bot]` and the PR head is in the same repository. A human re-running
  a Dependabot PR, or a fork PR, is skipped.
- The workflow never checks out code, so no PR content is ever executed.
- No `${{ }}` expression appears in a `run:` script; values pass through `env:`.

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
