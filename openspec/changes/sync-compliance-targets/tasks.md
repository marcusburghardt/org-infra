## 1. Core Script

- [ ] 1.1 Create `scripts/sync-compliance-targets.py` with
  `# SPDX-License-Identifier: Apache-2.0` header and functions to: parse
  `peribolos.yaml` (extract repo names from `orgs.<org>.repos`), parse
  `complytime.yaml` (extract target repo names from `targets[*].variables.url`),
  compute drift (return added/removed sets), and generate an updated
  `complytime.yaml` preserving `policies` and `complypacks` sections with
  targets sorted alphabetically by ID. Target IDs: prefix `complytime-` unless
  the repo name already starts with `complytime-`. Script accepts `--peribolos`,
  `--complytime`, `--org`, `--output`, and `--exclude` CLI arguments. The
  `--exclude` argument accepts a comma-separated list of repo names to remove
  from both sides before comparison. Exit codes: 0 = no drift, 1 = error
  (missing file, parse failure, missing org), 2 = drift detected and output
  written. Validate repo names against `^[a-zA-Z0-9._-]+$` and skip invalid
  names with a warning to stderr. Verify with
  `python scripts/sync-compliance-targets.py --help` succeeding and
  `ruff check scripts/sync-compliance-targets.py` reporting zero issues.

## 2. Unit Tests

- [ ] 2.1 Create `tests/test_sync_compliance_targets.py` with pytest tests
  using inline dict fixtures (following the pattern in
  `tests/test_sync_org_repositories.py`). Test classes covering:
  (a) peribolos repo extraction (valid data, empty org, missing org key),
  (b) complytime target parsing (extract repo names from URLs, empty targets),
  (c) drift detection (added repos, removed repos, no drift, mixed),
  (d) target ID generation (plain repos get `complytime-` prefix, repos
  already prefixed with `complytime-` use name as-is),
  (e) `complytime.yaml` generation (correct target entries, preserved
  `policies`/`complypacks`, sorted output),
  (f) error handling (missing peribolos file exits 1, malformed YAML exits 1,
  missing org exits 1, invalid repo names skipped with warning),
  (g) CLI exit codes (0 for no drift, 2 for drift, 1 for errors),
  (h) `--exclude` flag (excluded repos not treated as additions or removals).
  Verify with `make test` passing all new tests.

## 3. Workflow

- [ ] 3.1 Create `.github/workflows/sync_compliance_targets.yml` with a
  header comment block describing the workflow's purpose. Triggers: `schedule`
  (cron `0 22 * * *`) and `workflow_dispatch`. Single job that: checks out
  org-infra with `contents: write` + `pull-requests: write` permissions,
  shallow-clones `complytime/.github` to fetch `peribolos.yaml`, installs
  PyYAML, runs `scripts/sync-compliance-targets.py` with `--output` pointing
  to a temp path and `--exclude ".github,complyscribe"`. On drift (exit 2):
  copies output to `.complytime/complytime.yaml`, commits with `-s` flag,
  pushes to branch `sync/compliance-targets`, checks if a PR already exists
  for that branch via `gh pr list`, and creates one via `gh pr create` only
  if none exists. All action `uses:` SHA-pinned with inline version comments.
  Workflow-level `permissions: contents: none`. Verify with
  `yamllint .github/workflows/sync_compliance_targets.yml` reporting zero
  issues.

## 4. Validation

- [ ] 4.1 Run `make lint` and verify zero lint issues across all new files
  (`scripts/sync-compliance-targets.py`,
  `tests/test_sync_compliance_targets.py`,
  `.github/workflows/sync_compliance_targets.yml`).
- [ ] 4.2 Run `make test` and verify all existing and new tests pass.
- [ ] 4.3 Verify `sync_compliance_targets.yml` does NOT appear in
  `sync-config.yml`.
