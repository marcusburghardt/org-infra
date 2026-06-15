# Data Model: Centralize CRAP Load Analysis Workflow

**Date**: 2026-03-18

This feature does not introduce a traditional data model. The relevant data structures are defined by the Gaze tool and consumed as intermediate artifacts within the workflow.

## Workflow Inputs (configuration interface)

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| go-version-file | string | no | `./go.mod` | Path to go.mod for Go version detection |
| gaze-version | string | no | `latest` | Gaze version tag for `go install` |
| baseline-file | string | no | `.gaze/baseline.json` | Path to committed baseline thresholds |
| packages | string | no | `./...` | Go packages to analyze |
| coverprofile | string | no | `coverage.out` | Path to coverage profile |
| new-function-threshold | number | no | `30` | CRAP score ceiling for new functions (used when no `.gaze.yaml` exists) |
| regression-epsilon | number | no | `0.5` | Minimum score delta to flag a regression (used when no `.gaze.yaml` exists) |

## Workflow Outputs

| Output | Type | Description |
|--------|------|-------------|
| status | string | `pass` or `fail` |
| crapload-count | number | Functions at or above CRAP threshold |
| gaze-crapload-count | number | Functions at or above GazeCRAP threshold |
| regressions-count | number | Functions that regressed vs baseline |
| improvements-count | number | Functions that improved vs baseline |

## Intermediate Artifacts

- **gaze-report.json**: Full Gaze analysis output including quality metrics (uploaded as artifact)
- **crapload-current.json**: `gaze crap` JSON output with scores and comparison data (uploaded as artifact)
