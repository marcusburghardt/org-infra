## Purpose

Reusable GitHub Actions workflow that wraps CodeQL semantic static analysis with
controlled Go version management, configurable build modes, and advisory or
blocking alert handling.

## Input Contract

| Input | Type | Required | Default | Valid Values |
|-------|------|----------|---------|--------------|
| `language` | string | yes | (none) | CodeQL-supported languages: `go`, `python`, `javascript`, `java`, etc. |
| `go-version-file` | string | no | `go.mod` | Path to `go.mod` or `go.work` in the repository |
| `build-command` | string | no | `""` (empty = autobuild) | Any valid shell command; empty triggers autobuild for compiled languages |
| `query-suite` | string | no | `default` | `default`, `security-extended`, `security-and-quality` |
| `fail-on-alert` | boolean | no | `false` | `true`, `false` |

## Output Contract

The workflow SHALL NOT expose `workflow_call` outputs. SARIF results are
uploaded directly to GitHub Code Scanning via `codeql-action/analyze`.

## ADDED Requirements

### Requirement: Go version derived from repository

The workflow SHALL install the Go version declared by the calling repository's
own version file before initializing CodeQL, ensuring the analysis uses the
same Go version the repository targets. The `setup-go` step SHALL execute
before `codeql/init` to ensure the CodeQL tracer binds to the correct Go
toolchain.

#### Scenario: Single-module repo with go.mod

- **WHEN** the workflow is called with `go-version-file` set to `go.mod`
- **THEN** the Go version installed on the runner matches the version declared
  in that `go.mod`

#### Scenario: Multi-module repo with go.work

- **WHEN** the workflow is called with `go-version-file` set to `go.work`
- **THEN** the Go version installed on the runner matches the version declared
  in that `go.work`

#### Scenario: Non-Go language

- **WHEN** the workflow is called with a language other than `go`
- **THEN** the Go setup step is skipped entirely

#### Scenario: Step ordering for Go

- **WHEN** the workflow is invoked with `language` set to `go`
- **THEN** the `setup-go` step executes before the `codeql/init` step

#### Scenario: Missing go-version-file

- **WHEN** the workflow is called with `language` set to `go`
- **AND** `go-version-file` points to a file that does not exist
- **THEN** the setup-go step fails and the workflow surfaces the error

### Requirement: Single-language invocation

The workflow SHALL analyze exactly one language per invocation. Callers needing
multi-language analysis SHALL invoke the workflow multiple times (e.g., via a
matrix strategy in their consumer workflow).

#### Scenario: Go analysis

- **WHEN** the workflow is called with `language` set to `go`
- **THEN** CodeQL initializes and analyzes only Go source code

#### Scenario: Non-compiled language analysis

- **WHEN** the workflow is called with a language that does not require building
  (e.g., `python`, `javascript`)
- **THEN** CodeQL initializes and analyzes that language without a build step

### Requirement: Configurable build mode

The workflow SHALL support both automatic and manual build modes for compiled
languages. When no custom build command is provided, CodeQL's autobuild runs.
When a custom build command is provided, the workflow executes it instead.
The `build-command` input SHALL be passed to the `run:` block via an
environment variable (not inline `${{ inputs.build-command }}`), consistent
with the org's established input-handling pattern.

#### Scenario: Autobuild default

- **WHEN** the workflow is called with an empty `build-command` and `language`
  is `go`
- **THEN** CodeQL autobuild detects the project's build system and compiles the
  code automatically

#### Scenario: Custom build command

- **WHEN** the workflow is called with `build-command` set to a non-empty value
- **THEN** the workflow executes that command as the build step and CodeQL
  autobuild is skipped

#### Scenario: Custom build command failure

- **WHEN** the workflow is called with a `build-command` that exits non-zero
- **THEN** the workflow fails with the build command's error output visible

#### Scenario: No build for interpreted languages

- **WHEN** the workflow is called with `language` set to `python` and
  `build-command` is empty
- **THEN** no build step executes (neither autobuild nor a custom command)

### Requirement: Configurable query suite

The workflow SHALL allow callers to select which CodeQL query suite to run,
controlling the precision-vs-coverage tradeoff.

#### Scenario: Default query suite

- **WHEN** the workflow is called without specifying `query-suite`
- **THEN** CodeQL uses the `default` query suite (highest precision, lowest
  false positive rate)

#### Scenario: Extended query suite

- **WHEN** the workflow is called with `query-suite` set to `security-extended`
- **THEN** CodeQL uses the `security-extended` suite with broader coverage

### Requirement: Advisory alerts by default

The workflow SHALL upload CodeQL findings to GitHub Code Scanning as alerts
without failing the workflow run, unless explicitly configured to block.

#### Scenario: Advisory mode (default)

- **WHEN** the workflow is called without specifying `fail-on-alert` or with
  `fail-on-alert` set to `false`
- **THEN** findings appear as Code Scanning alerts in the repository's Security
  tab but the workflow completes successfully

#### Scenario: Blocking mode with alerts

- **WHEN** the workflow is called with `fail-on-alert` set to `true`
- **AND** CodeQL finds one or more alerts (SARIF results with `level` of
  `error` or `warning`)
- **THEN** the fail-on-alert step parses the SARIF output, detects alerts,
  and exits with a non-zero code

#### Scenario: Blocking mode without alerts

- **WHEN** the workflow is called with `fail-on-alert` set to `true`
- **AND** CodeQL finds zero alerts
- **THEN** the workflow completes successfully

### Requirement: Least-privilege permissions

The workflow SHALL request only the minimum permissions required for CodeQL
analysis and SARIF upload. Workflow-level permissions SHALL deny all access,
with specific grants at the job level only. The checkout step SHALL set
`persist-credentials: false` to prevent credential exposure to subsequent steps.

#### Scenario: Permission scope

- **WHEN** the workflow runs
- **THEN** the job-level permissions are limited to `contents: read`,
  `security-events: write`, and `actions: read`

### Requirement: SHA-pinned action references

All action references within the workflow SHALL be pinned to full 40-character
commit SHAs with an inline version comment.

#### Scenario: Action reference format

- **WHEN** the workflow references an external action
- **THEN** the reference uses the format `<owner>/<repo>@<full-sha> # vX.Y.Z`

### Requirement: Concurrency control

The workflow SHALL define a concurrency group to avoid wasting runner minutes
on superseded commits. Superseded runs SHALL be cancelled in progress.

#### Scenario: Concurrent runs on same ref

- **WHEN** multiple commits are pushed to the same branch in rapid succession
- **THEN** only the most recent workflow run continues; earlier runs are
  cancelled

### Requirement: Job timeout

The workflow SHALL set a `timeout-minutes` value on the analysis job to prevent
stuck runs from consuming runner capacity up to the GitHub default of 6 hours.

#### Scenario: Timeout enforcement

- **WHEN** the workflow runs
- **THEN** the job has a `timeout-minutes` value set (recommended: 45 minutes)
