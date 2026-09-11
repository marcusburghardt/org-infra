## 1. Scaffold Reusable Workflow

- [x] 1.1 Create `.github/workflows/reusable_codeql.yml` with header comment
  block describing the workflow purpose, modes (autobuild vs manual build),
  supported languages, and permission requirements. Verify the header follows
  the "Title with underline" style used by `reusable_vuln_scan.yml`.

- [x] 1.2 Define `workflow_call` trigger with five inputs. The `language` input
  SHALL be `required: true` with no default. The remaining four inputs
  (`go-version-file`, `build-command`, `query-suite`, `fail-on-alert`) SHALL
  have `default` values as specified in the codeql-analysis spec's Input
  Contract table. Each input SHALL have a `description` field. Verify all
  inputs are present with `yq '.on.workflow_call.inputs | keys'`.

- [x] 1.3 Set workflow-level permissions to deny all (`permissions: {}`).
  Define a single job `analyze` with job-level permissions limited to
  `contents: read`, `security-events: write`, and `actions: read`. Verify
  with `yq '.permissions' && yq '.jobs.analyze.permissions'`.

- [x] 1.4 Add a `concurrency` block at workflow level scoped to the language,
  workflow, and ref, with `cancel-in-progress: true`. Verify the concurrency
  group format is consistent with `reusable_vuln_scan.yml`.

- [x] 1.5 Set `timeout-minutes: 45` on the `analyze` job. Verify with
  `yq '.jobs.analyze.timeout-minutes'`.

## 2. Implement Analysis Steps

- [x] 2.1 Add checkout step using `actions/checkout` SHA-pinned to the version
  used by other workflows in the repo (currently `v7.0.1`). Set
  `persist-credentials: false`. Verify the SHA matches the pin in
  `reusable_vuln_scan.yml`.

- [x] 2.2 Add `actions/setup-go` step conditioned on
  `inputs.language == 'go'`. Use the same SHA pin as existing workflows
  (currently `v7.0.0`). Set `go-version-file` from the input and
  `cache: false`. This step MUST appear before `codeql-action/init`. Verify
  the conditional and step ordering.

- [x] 2.3 Add `github/codeql-action/init` step. Pin to the latest stable SHA
  of `codeql-action` v4. Set `languages` from `inputs.language` and `queries`
  from `inputs.query-suite`. Verify the action ref is a full 40-character SHA
  with inline version comment.

- [x] 2.4 Add build step with conditional logic: if `inputs.build-command` is
  non-empty, run it as a `run:` step using an environment variable (not inline
  `${{ inputs.build-command }}`) and set `build-mode: manual` on the init step;
  if empty and `inputs.language` requires building (Go), use
  `github/codeql-action/autobuild` (same SHA pin); if empty and language
  does not require building, skip the build step entirely. All `run:` steps
  SHALL use `shell: bash` with `set -euo pipefail`. Verify all three code
  paths are represented in the YAML.

- [x] 2.5 Add `github/codeql-action/analyze` step with `category` set to
  `/language:${{ inputs.language }}` for SARIF deduplication. Same SHA pin
  as init. Verify the category format matches GitHub's recommendation.

- [x] 2.6 Add optional fail-on-alert step: if `inputs.fail-on-alert` is `true`,
  parse the SARIF output for results with `level` of `error` or `warning` and
  fail the job when any are present. Verify this step is conditioned on the
  input and does not run by default.

## 3. Contract Test

- [x] 3.1 Create `.github/workflows/ci_test_codeql.yml` with triggers on
  `pull_request` and `push` to `main`, scoped to `paths:` matching
  `.github/workflows/reusable_codeql.yml`,
  `.github/workflows/ci_test_codeql.yml`, and `tests/test_codeql_workflow.py`.
  Verify paths filter is present.

- [x] 3.2 Create `tests/test_codeql_workflow.py` following the
  `test_vuln_scan_workflow.py` pattern. The pytest test file SHALL parse
  `reusable_codeql.yml` with PyYAML and assert on:
  (a) `language` input is `required: true` with no default (traces to:
  Single-language invocation requirement),
  (b) optional inputs have correct defaults (traces to: Configurable query
  suite, Advisory alerts, Configurable build mode requirements),
  (c) workflow-level permissions are `{}` and job-level are `contents: read`,
  `security-events: write`, `actions: read` (traces to: Least-privilege
  permissions requirement),
  (d) all `uses:` refs match `[a-f0-9]{40}` pattern (traces to: SHA-pinned
  action references requirement),
  (e) `setup-go` step appears before `codeql/init` in step list (traces to:
  Go version derived from repository requirement, Design D8),
  (f) `setup-go` and build steps have `if:` conditions checking
  `inputs.language` (traces to: Go version and Configurable build mode
  requirements),
  (g) `timeout-minutes` is set on the job (traces to: Job timeout
  requirement),
  (h) `concurrency` block exists (traces to: Concurrency control requirement),
  (i) the workflow does not expose `workflow_call` outputs (traces to: Output
  Contract).
  Verify the test passes with `python -m pytest tests/test_codeql_workflow.py`.

- [x] 3.3 Wire `ci_test_codeql.yml` to invoke `pytest` on
  `tests/test_codeql_workflow.py`. Verify the workflow references the test
  file correctly.

## 4. SpecKit Documentation

- [x] 4.1 Create `specs/008-codeql-workflow/spec.md` with feature specification
  covering purpose, user scenarios, workflow file reference, and key metadata.
  Follow the structure of `specs/002-sonarqube-workflow/spec.md`. Verify the
  file exists and contains all required sections.

- [x] 4.2 Create `specs/008-codeql-workflow/quickstart.md` with step-by-step
  adoption guide including copy-paste consumer workflow examples for:
  (a) standard single-module Go repo (defaults, with `paths:` filter for
  `**.go`, `go.mod`, `go.sum`),
  (b) multi-module Go repo with custom build command,
  (c) multi-language repo with matrix strategy.
  Include required permissions and trigger configuration. Follow the structure
  of `specs/002-sonarqube-workflow/quickstart.md`. Verify the file exists and
  contains all three examples.

## 5. Validation

- [x] 5.1 Run `yamllint` on both new workflow files and verify zero lint errors:
  `yamllint .github/workflows/reusable_codeql.yml .github/workflows/ci_test_codeql.yml`.

- [x] 5.2 Verify all action `uses:` references in `reusable_codeql.yml` are
  SHA-pinned (40 hex characters, no mutable tags): scan for `uses:` lines and
  confirm each matches the pattern `<owner>/<repo>@[a-f0-9]{40}`.

- [x] 5.3 Verify the workflow is NOT listed in `sync-config.yml` (it should not
  be synced): `grep -c 'reusable_codeql' sync-config.yml` returns 0.

- [x] 5.4 Run the full project lint suite (`make lint`) and verify zero errors
  across all linters.

- [x] 5.5 Run the contract test suite and verify all assertions pass:
  `python -m pytest tests/test_codeql_workflow.py -v`.

<!-- spec-review: passed -->
<!-- code-review: passed -->
