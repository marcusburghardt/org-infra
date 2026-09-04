## Why

The compliance workflow (`ci_compliance.yml`) scans branch protection rules for
a hardcoded list of repositories defined in `.complytime/complytime.yaml`. When
a new repository is added to the organization via `peribolos.yaml` (in
`complytime/.github`), it is not automatically included in the compliance scan
targets. This creates a silent coverage gap where new repositories have no
branch protection verification until someone manually updates `complytime.yaml`.

Similarly, when a repository is removed from `peribolos.yaml`, its stale entry
in `complytime.yaml` causes scan failures or wasted CI time.

## What Changes

- Add a new Python script (`scripts/sync-compliance-targets.py`) that compares
  the repository list in `peribolos.yaml` (from `complytime/.github`) against
  the scan targets in `.complytime/complytime.yaml` and generates an updated
  file when drift is detected.
- Add a new org-infra-only workflow (`sync_compliance_targets.yml`) that runs
  the script on a daily schedule, and creates a PR when the target list is out
  of sync with peribolos.
- Add pytest unit tests for the sync script.

## Non-goals

- No changes to the reusable compliance workflow (`reusable_compliance.yml`).
  It continues to scan whatever targets are defined in `complytime.yaml`.
- No cross-org genericity. This workflow is specific to `complytime/org-infra`
  and the `complytime/.github` peribolos source of truth.
- No dynamic exclusion discovery (e.g., auto-skipping archived repos).
  Exclusions are an explicit CLI argument maintained in the workflow file.

## Capabilities

### New Capabilities

- `compliance-target-sync`: Automated drift detection and PR creation to keep
  `.complytime/complytime.yaml` targets aligned with `peribolos.yaml`.

### Modified Capabilities

_(none -- no existing spec-level behavior changes)_

## Impact

- **New files:** `scripts/sync-compliance-targets.py`,
  `.github/workflows/sync_compliance_targets.yml`,
  `tests/test_sync_compliance_targets.py`
- **Existing files:** None modified.
- **Dependencies:** PyYAML (already a project dependency for the sync script),
  `gh` CLI (pre-installed on GitHub-hosted runners, used for PR creation).
- **CI:** New daily scheduled workflow; uses `GITHUB_TOKEN` (public `.github`
  repo clone + PR creation on org-infra).
