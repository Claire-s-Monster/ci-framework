# Feature Request: GitHub Repository Settings Management

## Summary
Add GitHub repository settings management capabilities to mcp-git to enable automated configuration of repository settings, workflow permissions, and branch protection rules directly from ClaudeCode.

## Use Case & Motivation

During development of the ci-framework cleanup workflow, we encountered the need to configure GitHub repository settings programmatically:

1. **Workflow Permissions**: Needed to enable "Allow GitHub Actions to create and approve pull requests"
2. **Actions Configuration**: Required setting organization-only action permissions
3. **Branch Protection**: Needed to configure protected branch rules
4. **Security Policies**: Organization-wide consistency requirements

Currently, these configurations require manual navigation through GitHub's web interface, breaking the automation flow and creating inconsistency across repositories.

## Proposed Features

### 1. Repository Settings Management
```typescript
// Core repository settings
mcp__git__repo_settings({
  repo: "owner/repo",
  settings: {
    has_issues: true,
    has_projects: true,
    has_wiki: false,
    allow_squash_merge: true,
    allow_merge_commit: false,
    allow_rebase_merge: true,
    delete_branch_on_merge: true,
    allow_auto_merge: true
  }
})
```

### 2. GitHub Actions Configuration
```typescript
// Actions permissions and settings
mcp__git__actions_settings({
  repo: "owner/repo",
  actions: {
    enabled: true,
    allowed_actions: "selected", // all, disabled, selected
    allowed_actions_config: {
      github_owned_allowed: true,
      verified_allowed: true,
      patterns_allowed: ["MementoRC/*"]
    }
  }
})

// Workflow permissions
mcp__git__workflow_permissions({
  repo: "owner/repo",
  default_workflow_permissions: "write", // read, write
  can_approve_pull_request_reviews: true
})
```

### 3. Branch Protection Rules
```typescript
// Branch protection configuration
mcp__git__branch_protection({
  repo: "owner/repo",
  branch: "main", // or development
  protection: {
    required_status_checks: {
      strict: true,
      contexts: ["ci/build", "ci/test"]
    },
    enforce_admins: false,
    required_pull_request_reviews: {
      required_approving_review_count: 1,
      dismiss_stale_reviews: true,
      require_code_owner_reviews: false
    },
    restrictions: null, // or specify users/teams
    allow_force_pushes: false,
    allow_deletions: false
  }
})
```

### 4. Security & Compliance
```typescript
// Security settings
mcp__git__security_settings({
  repo: "owner/repo",
  security: {
    vulnerability_alerts: true,
    automated_security_fixes: true,
    dependency_graph: true,
    secret_scanning: true,
    secret_scanning_push_protection: true
  }
})
```

## Technical Implementation Options

### Option A: Extend Current mcp-git Architecture
- Add new tool categories under existing `mcp__git__*` namespace
- Leverage existing GitHub authentication mechanisms
- Integrate with current Git operations workflow

### Option B: Dedicated GitHub Admin Module
- Create `mcp__github__*` namespace for GitHub-specific operations
- Separate from core Git operations (clone, commit, push, etc.)
- Focused on repository management and configuration

### Option C: GitHub REST API Integration
- Direct GitHub REST API wrapper
- Full coverage of GitHub repository management endpoints
- Generic approach supporting future GitHub API additions

## API Design Considerations

### Authentication
- Reuse existing GitHub token mechanisms from mcp-git
- Support for fine-grained personal access tokens
- Organization-level permissions handling

### Error Handling
- Clear error messages for insufficient permissions
- Validation of settings before API calls
- Rollback capabilities for failed configurations

### Consistency
- Follow existing mcp-git naming conventions
- Maintain similar parameter structures
- Consistent error handling patterns

## Integration with ci-framework

### Automated Repository Setup
```yaml
# .github/workflows/setup-repository.yml
name: Repository Setup
on:
  repository_dispatch:
    types: [setup-repo]

jobs:
  configure:
    runs-on: ubuntu-latest
    steps:
      - name: Configure Repository Settings
        # Uses mcp-git tools via ClaudeCode automation
        run: |
          # Enable organization-only actions
          # Configure branch protection
          # Set workflow permissions
          # Apply security settings
```

### Template Repository Configuration
- Standard settings templates for different repository types
- Automated application of organization policies
- Compliance validation and reporting

### Developer Workflow Integration
- ClaudeCode can configure repositories during development
- Consistent settings across all projects
- Infrastructure-as-code approach to repository management

## Benefits

1. **Automation**: Eliminate manual repository configuration
2. **Consistency**: Ensure all repositories follow organization standards
3. **Security**: Programmatic enforcement of security policies
4. **Efficiency**: Reduce setup time for new repositories
5. **Compliance**: Audit and validate repository configurations
6. **Integration**: Seamless workflow with existing mcp-git tools

## Success Criteria

- [ ] Configure GitHub Actions permissions programmatically
- [ ] Set up branch protection rules via ClaudeCode
- [ ] Apply organization-wide security policies
- [ ] Validate repository settings compliance
- [ ] Integrate with ci-framework automation workflows

## Related Context

This feature request emerged from developing the ci-framework automated cleanup workflow:
- **Repository**: https://github.com/MementoRC/ci-framework
- **Workflow**: `.github/workflows/cleanup-dev-files.yml`
- **Use Case**: Automated cleanup of development artifacts with proper permissions

The cleanup workflow successfully removes development files and creates branches, but required manual configuration of GitHub settings to enable automated PR creation.

## References

- [GitHub REST API - Repository Settings](https://docs.github.com/en/rest/repos/repos)
- [GitHub REST API - Actions Permissions](https://docs.github.com/en/rest/actions/permissions)
- [GitHub REST API - Branch Protection](https://docs.github.com/en/rest/branches/branch-protection)
- [GitHub REST API - Repository Security](https://docs.github.com/en/rest/repos/repos#update-a-repository)

---

**Labels**: enhancement, github-api, repository-management, automation
**Priority**: Medium
**Complexity**: High