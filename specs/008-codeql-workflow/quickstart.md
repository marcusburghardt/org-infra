# CodeQL Analysis Quickstart

This guide covers enabling CodeQL semantic static analysis for repository
maintainers adopting the reusable workflow.

## Prerequisites

- Repository contains Go, Python, JavaScript, or another CodeQL-supported
  language
- For Go repositories: `go.mod` (or `go.work`) exists in the repository root

No secrets or tokens are required -- CodeQL uses the built-in `GITHUB_TOKEN`
for Code Scanning uploads.

## Setup Steps

### Step 1: Add Consumer Workflow

Create `.github/workflows/ci_codeql.yml` in your repository.

**Standard single-module Go repository (zero configuration):**

```yaml
name: CodeQL Analysis

on:
  push:
    branches: [main]
    paths:
      - "**.go"
      - "go.mod"
      - "go.sum"
  pull_request:
    branches: [main]
    paths:
      - "**.go"
      - "go.mod"
      - "go.sum"

permissions:
  contents: read

jobs:
  codeql:
    name: CodeQL Analysis
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: complytime/org-infra/.github/workflows/reusable_codeql.yml@main
    with:
      language: go
```

**Multi-module Go repository (custom build command):**

For repositories with `go.work` or non-standard build layouts (e.g.,
`complytime-collector-components`):

```yaml
name: CodeQL Analysis

on:
  push:
    branches: [main]
    paths:
      - "**.go"
      - "go.mod"
      - "go.sum"
      - "go.work"
  pull_request:
    branches: [main]
    paths:
      - "**.go"
      - "go.mod"
      - "go.sum"
      - "go.work"

permissions:
  contents: read

jobs:
  codeql:
    name: CodeQL Analysis
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: complytime/org-infra/.github/workflows/reusable_codeql.yml@main
    with:
      language: go
      go-version-file: "proofwatch/go.mod"
      build-command: "cd proofwatch && go build ./..."
    env:
      GOWORK: "off"
```

**Multi-language repository (matrix strategy):**

For repositories with both Go and Python (or other CodeQL-supported
languages):

```yaml
name: CodeQL Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  codeql:
    name: CodeQL (${{ matrix.language }})
    permissions:
      contents: read
      security-events: write
      actions: read
    strategy:
      fail-fast: false
      matrix:
        include:
          - language: go
            go-version-file: "go.mod"
          - language: python
            go-version-file: ""
    uses: complytime/org-infra/.github/workflows/reusable_codeql.yml@main
    with:
      language: ${{ matrix.language }}
      go-version-file: ${{ matrix.go-version-file }}
```

### Step 2: Disable Default Code Scanning Setup

If your repository has GitHub's default code scanning setup enabled, disable
it to avoid duplicate analysis:

1. Navigate to **Settings** > **Code security** > **Code scanning**
2. Under "Default setup", click **Disable**
3. Confirm the change

The new consumer workflow replaces the default setup with controlled Go
version management.

## Configuration Options

### Required Inputs

| Input | Type | Description |
|-------|------|-------------|
| `language` | string | CodeQL language to analyze (`go`, `python`, `javascript`, etc.) |

### Optional Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `go-version-file` | string | `go.mod` | Path to `go.mod` or `go.work` (Go only) |
| `build-command` | string | `""` | Custom build command; empty uses autobuild |
| `query-suite` | string | `default` | Query suite: `default`, `security-extended`, `security-and-quality` |
| `fail-on-alert` | boolean | `false` | Fail workflow when CodeQL finds alerts |

### Required Permissions

Consumer workflows must grant these job-level permissions:

| Permission | Level | Purpose |
|-----------|-------|---------|
| `contents` | `read` | Checkout source code |
| `security-events` | `write` | Upload SARIF to Code Scanning |
| `actions` | `read` | Required for SARIF upload API |

## Verification

After setup:

1. **Push a commit** to main or open a PR to trigger the workflow
2. **Check the Actions tab** to verify the workflow executes successfully
3. **View results** in the repository's **Security** > **Code scanning** tab
4. **Verify Go version**: The "Setup Go" step log should show the version
   matching your `go.mod`

## Troubleshooting

### Autobuild Fails

If CodeQL's autobuild cannot build your Go code:
- Check the "Autobuild" step log for the specific error
- Provide a custom `build-command` that matches your existing build process
  (e.g., `make build` or `go build ./cmd/...`)

### Go Version Mismatch

If the Go version doesn't match your `go.mod`:
- Verify `go-version-file` points to the correct file
- For multi-module repos, try pointing to `go.work` instead of `go.mod`

### Too Many Findings

If CodeQL reports excessive findings during initial adoption:
- The `default` query suite (the default) provides highest precision
- Findings are advisory by default -- they don't block PRs
- Triage findings in the Security tab; dismiss false positives

## Per-Repository Configuration Summary

| Repository | Configuration | Notes |
|-----------|---------------|-------|
| complyctl | Defaults | Single module, autobuild works |
| complytime-providers | Defaults | Single module, 3 binaries auto-detected |
| complypack | Defaults | Single module, standard cmd/ layout |
| complytime-collector-components | Custom | `go-version-file: proofwatch/go.mod`, custom build, `GOWORK=off` |
| complyapi | TBD | Assess when populated |

## Infrastructure Notes

The reusable workflow resides in org-infra at
`.github/workflows/reusable_codeql.yml`. It is NOT synced to downstream
repos -- each repo opts in by creating their own consumer workflow. Changes
to the reusable workflow propagate automatically since consumer workflows
reference `@main`.
