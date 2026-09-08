## Why

The reusable OSV scan can exceed GitHub Actions' 1 MB per-job output limit when the upstream workflow exports complete scan reports, causing otherwise successful scans to fail during output evaluation. This change restores reliable scanning for repositories with large dependency reports and closes #574.

## What Changes

- Stop propagating complete OSV `old-results.json` and `new-results.json` reports through reusable-workflow job outputs.
- Preserve the complete JSON reports as downloadable workflow artifacts.
- Preserve SARIF upload and fail-on-vulnerability behavior.
- Add deterministic regression validation that complete OSV result exports remain disabled.

## Capabilities

### New Capabilities

- `osv-vulnerability-scan`: Defines reliable OSV pull-request scanning, diagnostic artifact retention, SARIF publication, and vulnerability enforcement.

### Modified Capabilities

None.

## Non-goals

- Changing the vulnerabilities that OSV Scanner detects or the policy for failing on new vulnerabilities.
- Changing Trivy source scanning behavior.
- Replacing JSON artifacts with job-output transport.

## Impact

- Affects `.github/workflows/reusable_vuln_scan.yml` and its downstream consumers across synchronized repositories.
- Retains the pinned upstream OSV integration rather than reproducing its scan workflow locally.
- Requires validation that artifacts, SARIF upload, permissions, and failure semantics remain compatible.

## Constitution Alignment

- **I. Single Source of Truth**: N/A. The change introduces no shared constant or duplicated configuration value.
- **II. Simplicity & Isolation**: PASS. It uses the upstream workflow's focused export control instead of duplicating scanner logic.
- **III. Incremental Improvement**: PASS. The implementation is limited to the OSV
  output-limit failure and its regression coverage. A validation-only `yq`
  compatibility repair is included because the pre-existing preflight test otherwise
  blocks the mandatory full suite; it does not alter preflight behavior.
- **IV. Readability First**: PASS. The required result-export behavior is explicit at the reusable-workflow call site.
- **V. Do Not Reinvent the Wheel**: PASS. The design retains Google's pinned reusable workflow and its supported input.
- **VI. Composability**: PASS. Complete machine-readable reports remain available as JSON artifacts.
- **VII. Convention Over Configuration**: PASS. Downstream callers inherit the safe organization-wide behavior without new inputs.
