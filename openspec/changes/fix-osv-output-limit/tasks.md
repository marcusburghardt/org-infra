## 1. Workflow Configuration

- [x] 1.1 Modify `.github/workflows/reusable_vuln_scan.yml` to pass `export-results: false` to the pinned OSV reusable workflow and verify complete JSON reports are not exported as job outputs.
- [x] 1.2 Review `sync-config.yml` for the downstream rollout scope of `.github/workflows/reusable_vuln_scan.yml` and verify no sync configuration change is required.

## 2. Permissions and Regression Coverage

- [x] 2.1 Verify `.github/workflows/reusable_vuln_scan.yml` retains its existing least-privilege OSV job permissions, `fail-on-vuln: true`, and `upload-sarif: true` settings.
- [x] 2.2 Create `tests/test_vuln_scan_workflow.py` with positive and negative assertions that the OSV call explicitly disables complete result exports while preserving SARIF and vulnerability enforcement inputs, and verify the focused pytest file passes.

## 3. Validation

- [x] 3.1 Run `make lint` and verify yamllint, Ruff, and workflow SHA-pin checks report no issues.
- [x] 3.2 Run `make test` and verify the complete regression suite passes.
- [x] 3.3 Document the oversized-report reproduction from issue #574 and verify deterministic regression tests cover the local integration contract: disabled result exports, continued use of the pinned artifact-producing integration, SARIF and failure-policy inputs, and permissions.

<!-- spec-review: passed -->

<!-- code-review: passed -->
