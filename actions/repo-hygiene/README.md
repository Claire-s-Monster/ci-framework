# Repository Hygiene Check Action

Automated checks for common repository hygiene issues to prevent accidental commits of development artifacts.

## Features

- ✅ Detects `__pycache__` directories tracked in git
- ✅ Detects `.pyc` files tracked in git
- ✅ Ensures `.gitignore` file exists
- ⚠️ Warns about `.env` files tracked in git
- ⚠️ Warns about `.log` files tracked in git
- ⚠️ Warns about OS-specific files (`.DS_Store`, `Thumbs.db`)

## Usage

### Basic Usage

```yaml
- name: Repository Hygiene Check
  uses: Claire-s-Monster/ci-framework/actions/repo-hygiene@v2.2.0
```

### With Custom Configuration

```yaml
- name: Repository Hygiene Check
  uses: Claire-s-Monster/ci-framework/actions/repo-hygiene@v2.2.0
  with:
    fail-on-pycache: true
    fail-on-pyc: true
    fail-on-missing-gitignore: true
    warn-on-env-files: true
    warn-on-log-files: true
    warn-on-os-files: true
    project-dir: '.'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `fail-on-pycache` | Fail if __pycache__ directories are tracked in git | No | `true` |
| `fail-on-pyc` | Fail if .pyc files are tracked in git | No | `true` |
| `fail-on-missing-gitignore` | Fail if .gitignore file is missing | No | `true` |
| `warn-on-env-files` | Warn if .env files are tracked in git | No | `true` |
| `warn-on-log-files` | Warn if .log files are tracked in git | No | `true` |
| `warn-on-os-files` | Warn if OS-specific files are tracked | No | `true` |
| `project-dir` | Project directory to check | No | `.` |

## Outputs

| Output | Description |
|--------|-------------|
| `success` | Whether hygiene checks passed |
| `violations` | Number of critical violations found |
| `warnings` | Number of warnings found |
| `details` | Details of hygiene check results |

## Examples

### In a CI Workflow

```yaml
jobs:
  hygiene:
    name: Repository Hygiene
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check Repository Hygiene
        uses: Claire-s-Monster/ci-framework/actions/repo-hygiene@v2.2.0
```

### With Conditional Execution

```yaml
- name: Check Repository Hygiene
  uses: Claire-s-Monster/ci-framework/actions/repo-hygiene@v2.2.0
  continue-on-error: false  # Fail the job if hygiene checks fail
```

## What Gets Checked

### Critical Violations (Fail)

1. **`__pycache__` directories** - Python bytecode cache directories should never be committed
2. **`.pyc` files** - Compiled Python files should never be committed
3. **Missing `.gitignore`** - Every repository should have a .gitignore file

### Warnings (Non-Blocking)

1. **`.env` files** - Environment variable files may contain secrets
2. **`.log` files** - Log files are typically local artifacts
3. **`.DS_Store`** - macOS folder metadata files
4. **`Thumbs.db`** - Windows thumbnail cache files

## Why Hygiene Checks Matter

Repository hygiene checks prevent:
- ❌ Binary files bloating repository size
- ❌ Local development artifacts in production
- ❌ Potential secret leakage via .env files
- ❌ Cross-platform compatibility issues
- ❌ Merge conflicts from generated files

## Best Practices

1. **Add to your `.gitignore`**:
   ```gitignore
   __pycache__/
   *.pyc
   *.pyo
   .env
   .env.*
   *.log
   .DS_Store
   Thumbs.db
   ```

2. **Run locally before committing**:
   ```bash
   git status | grep -E "(__pycache__|\.pyc$)"
   ```

3. **Use pre-commit hooks** to prevent commits of these files

## Integration with CI Framework

This action is automatically integrated into the CI Framework's reusable workflows. You can also use it standalone in your custom workflows.

## Troubleshooting

### How to fix violations

If you have violations detected:

```bash
# Remove __pycache__ directories
find . -type d -name "__pycache__" -exec git rm -rf {} +

# Remove .pyc files
find . -type f -name "*.pyc" -exec git rm -f {} +

# Add .gitignore if missing
cat > .gitignore << EOF
__pycache__/
*.pyc
*.pyo
.env
.env.*
*.log
.DS_Store
Thumbs.db
EOF

# Commit the changes
git add .gitignore
git commit -m "chore: remove development artifacts and add .gitignore"
```

### Why am I getting warnings?

Warnings don't fail the build but indicate files that typically shouldn't be in git. Review each warning and decide whether to:
- Add the file to `.gitignore` and remove from git
- Keep the file if it's intentionally tracked (e.g., a test fixture)

## License

MIT License - See the main CI Framework repository for details.
