# Label Sync

`reusable-label-sync.yml` creates the repository labels that Dependabot and the
pixi lock refresh request. Dependabot drops labels that do not exist, so nothing
is labelled until something creates them. Each label is created with
`gh label create --force`, so a rerun updates the colour and description of an
existing label.

## Usage

Copy `templates/github/workflows/label-sync-template.yml`. It runs on
`workflow_dispatch` and on pushes to the default branch that touch
`.github/dependabot.yml` or the caller file. The job needs only `issues: write`;
the top level grants nothing.

```yaml
permissions: {}

jobs:
  labels:
    permissions:
      issues: write
    uses: Claire-s-Monster/ci-framework/.github/workflows/reusable-label-sync.yml@<tag>
```

Until the first release containing this workflow, pin `@development`.

## Input

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `labels` | string | standard set | Newline-separated `name\|color\|description` lines; color is 6-digit hex without `#`. |

The default set is `dependencies`, `python`, `github-actions`, `docker`,
`nodejs` and `pixi`. Blank lines are skipped; a malformed line (missing name, bad
color, extra `|`) fails the job. The input reaches the script through an
environment variable, never through `${{ }}` interpolation in `run:`.

See also [Pixi Lock Refresh](pixi-lock-refresh.md), whose PRs carry the
`dependencies` and `pixi` labels.
