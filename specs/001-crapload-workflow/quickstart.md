# Quickstart: CRAP Load Analysis

## For Repository Maintainers (Adopting the Workflow)

### 1. Add the consumer workflow

Create `.github/workflows/ci_crapload.yml` in your repository:

```yaml
# SPDX-License-Identifier: Apache-2.0

name: CRAP Load Check

on:
  pull_request:
    branches:
      - main

permissions:
  contents: read
  pull-requests: write

jobs:
  crapload:
    name: CRAP Load Analysis
    uses: complytime/org-infra/.github/workflows/reusable_crapload_analysis.yml@main
    permissions:
      contents: read
      pull-requests: write
```

### 2. (Optional) Commit a baseline file

To enable regression detection, generate and commit a baseline at `.gaze/baseline.json`. This file contains per-function CRAP scores from a known-good state. Without it, the workflow still runs but skips per-function comparison.

**Generate a baseline:**

```bash
# 1. Install gaze
go install github.com/unbound-force/gaze/cmd/gaze@latest

# 2. Determine packages to analyze
# For single-module repos (go.mod at root):
PACKAGES="./..."

# For multi-module repos (no root go.mod), auto-discover:
PACKAGES=$(find . -name go.mod -type f -not -path '*/vendor/*' \
  | xargs dirname | sed 's|^\./||' | sed 's|^$|.|' | sed 's|$|/...|' | paste -sd ' ')

# 3. Run tests with coverage
go test -coverprofile=coverage.out $PACKAGES

# 4. Generate baseline
mkdir -p .gaze
gaze crap --format=json --coverprofile=coverage.out $PACKAGES > .gaze/baseline.json

# 5. Commit the baseline
git add .gaze/baseline.json
git commit -m "chore: add CRAP baseline for regression detection"
```

**For multi-module projects:**

The workflow automatically discovers all Go modules when the default `./...` pattern doesn't resolve packages (e.g., no code at root, or root go.mod contains only tools). No additional configuration is required.

To analyze only specific modules (e.g., exclude experimental packages), specify packages explicitly:

```bash
# Run tests for specific packages only
go test -coverprofile=coverage.out ./cmd/... ./pkg/...

# Generate baseline with the same packages
gaze crap --format=json --coverprofile=coverage.out ./cmd/... ./pkg/... > .gaze/baseline.json
```

And configure the `packages` input in your workflow:

```yaml
jobs:
  crapload:
    uses: complytime/org-infra/.github/workflows/reusable_crapload_analysis.yml@main
    with:
      packages: './cmd/... ./pkg/...'  # Analyze only these modules
```

### 3. Open a pull request

The workflow runs automatically on PRs targeting `main` that modify Go files. Results appear as a PR comment with a summary table.

## Customizing Inputs

Override defaults by passing `with:` in the consumer workflow:

```yaml
jobs:
  crapload:
    uses: complytime/org-infra/.github/workflows/reusable_crapload_analysis.yml@main
    with:
      new-function-threshold: 20    # Stricter threshold
      packages: './cmd/... ./pkg/...'  # Specific packages only
```

## For org-infra Contributors

The reusable workflow lives at `.github/workflows/reusable_crapload_analysis.yml`. Changes here affect all consuming repositories. Follow the constitution's Amendment Procedure for workflow modifications.

The consumer template at `.github/workflows/ci_crapload.yml` is distributed to Go repositories via the sync mechanism defined in `sync-config.yml`.
