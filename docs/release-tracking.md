# Release Tracking

`reusable-release-tracking.yml` tracks an issue from "fixed" to "shipped" with
two labels (#394).

| Label | Meaning |
|-------|---------|
| `fixed-in-development` | A pull request closing the issue merged into the development branch. Not yet in a tagged release. |
| `released` | A release tag contains every fix recorded for the issue. |

## Why

GitHub's `Closes #N` only fires when a pull request merges into the default
branch. With a `development` -> `main` flow, issues stay open (or are closed
with no signal) while the fix sits on `development`, and consumers pin released
tags, not branches. This workflow closes the gap.

## Modes

**Fixed mode** (no `tag` input), run on a merged pull request into the
development branch:

- Finds same-repo issues named by a closing keyword (`close(s|d)`,
  `fix(es|ed)`, `resolve(s|d)`) in the PR title, body and commit messages.
- Adds `fixed-in-development`, posts a comment carrying a hidden marker with
  the merge sha, and closes the issue as completed. Re-runs do not post a
  second comment.

**Released mode** (`tag` input set), run after a release is created:

- Looks at closed issues labelled `fixed-in-development`.
- If every marker sha is contained in the tag (GitHub compare status `ahead`
  or `identical`), comments with a link to the release, adds `released` and
  removes `fixed-in-development`. Otherwise the issue is left untouched.

## How this repo wires it

- `.github/workflows/release-tracking.yml` calls fixed mode on
  `pull_request_target` (closed, branch `development`) and offers a
  `workflow_dispatch` with a `tag` input to re-run released mode.
  `pull_request_target` is used only to get a write token on fork and
  Dependabot PRs; there is no checkout and no PR code runs.
- `.github/workflows/release-please.yml` has a `release-tracking` job, gated on
  `release_created == 'true'`, that passes `tag_name` to released mode in-line.
  A release created by a token does not reliably trigger `release: published`
  workflows.

## Consumer example

Available from the first release after v4.0.0. The caller job needs
`issues: write`.

```yaml
# .github/workflows/release-tracking.yml
name: Release Tracking
on:
  pull_request_target:
    types: [closed]
    branches: [development]

jobs:
  fixed:
    if: github.event.pull_request.merged == true
    permissions:
      contents: read
      issues: write
      pull-requests: read
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-release-tracking.yml@<tag>
```

Released mode, called right after your release is created:

```yaml
  release-tracking:
    needs: release
    if: needs.release.outputs.release_created == 'true'
    permissions:
      contents: read
      issues: write
      pull-requests: read
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-release-tracking.yml@<tag>
    with:
      tag: ${{ needs.release.outputs.tag_name }}
```

Optional inputs: `development-branch` (default `development`), `fixed-label`,
`released-label`.

## Requirements

- Promote `development` to `main` with **merge commits**. A squash promotion
  rewrites the fix shas, so the containment check can never succeed.
- The calling job must grant `issues: write` (and `contents: read`,
  `pull-requests: read`).
