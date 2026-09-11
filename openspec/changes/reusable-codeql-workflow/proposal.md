## Why

Repositories using GitHub's default code scanning setup for CodeQL have no control
over the Go version used during analysis. The Go version is determined by the runner
image, not by the repository. When Dependabot bumps the Go directive in `go.mod`
(e.g., to `go 1.25.12`), but the runner image ships an older version with
`GOTOOLCHAIN=local`, the CodeQL go-extractor fails with a fatal error. This affects
every Go repo in the org and will recur on every Go version bump.

Beyond the Go version management problem, the org has no semantic SAST coverage.
Existing tools (OSV-Scanner, Trivy, OpenSSF Scorecard, gosec via golangci-lint)
cover dependency vulnerabilities, secrets, misconfigurations, supply chain posture,
and AST-pattern security checks -- but none performs interprocedural taint-tracking
analysis on first-party Go source code. CodeQL fills this unoccupied layer by
tracing tainted data from sources (HTTP parameters, file reads, environment
variables) through the entire call chain across packages, catching injection
vulnerabilities, path traversal, command injection, and similar issues that
pattern-based tools miss.

Closes #537.

## What Changes

- Add `reusable_codeql.yml` -- a reusable workflow wrapping CodeQL analysis with
  `actions/setup-go` for Go version control. Accepts a single language per
  invocation; multi-language repos use a caller-side matrix strategy.
- The workflow is NOT synced to downstream repos. Repos opt in by creating their
  own consumer workflow calling the reusable cross-repo, following the same
  adoption model as `reusable_sonarqube.yml`.
- Go-specific steps (`setup-go`, build) are conditional on the `language` input,
  so the workflow also supports non-compiled languages (Python, JavaScript) where
  CodeQL extracts directly from source without a build step.
- Build flexibility: repos can use CodeQL's `autobuild` (default) or provide a
  custom `build-command` input for non-standard build structures (e.g.,
  multi-module workspaces with `go.work`).
- Alerts are advisory by default (non-blocking). Repos can opt into blocking mode
  via a `fail-on-alert` input.
- Add `ci_test_codeql.yml` to validate the reusable workflow contract in org-infra
  CI (input validation, step sequencing, permissions).
- Add spec and quickstart documentation following the established `specs/NNN-*`
  pattern.

## Non-goals

- Replacing SonarCloud. CodeQL fills the taint-tracking SAST gap; SonarCloud
  provides code quality metrics, coverage gates, and complementary SAST. They
  coexist.
- Syncing consumer workflows to downstream repos. With only 3-4 Go repos
  needing this and one requiring a custom build command (incompatible with the
  `vars` system's single-token substitution), opt-in adoption is the right model.
- Modifying `ci_security.yml` or the existing vulnerability scanning pipeline.
  CodeQL is a separate concern with its own consumer workflow.
- Enabling CodeQL on org-infra itself. This repo has no Go application code to
  analyze.
- Scheduled analysis runs. Event-based triggers only; repos can add `schedule:`
  triggers to their consumer workflows independently if desired.

## Capabilities

### New Capabilities

- `codeql-analysis`: Reusable workflow for CodeQL semantic SAST with Go version
  management, configurable build mode, language support, query suite selection,
  and advisory/blocking alert handling.
- `codeql-adoption`: Quickstart guide and consumer workflow templates for
  downstream repository adoption.

### Modified Capabilities

(none)

## Impact

- **New files in org-infra**:
  - `.github/workflows/reusable_codeql.yml` (reusable workflow)
  - `.github/workflows/ci_test_codeql.yml` (contract test)
  - `specs/008-codeql-workflow/spec.md` (feature specification)
  - `specs/008-codeql-workflow/quickstart.md` (adoption guide)
- **New dependencies (action references)**:
  - `github/codeql-action/init` (SHA-pinned)
  - `github/codeql-action/autobuild` (SHA-pinned)
  - `github/codeql-action/analyze` (SHA-pinned)
  - `actions/setup-go` (existing dependency, same SHA pin as other workflows)
- **Downstream repos** (opt-in): `complyctl`, `complytime-providers`, `complypack`,
  `complytime-collector-components` each create a `ci_codeql.yml` consumer workflow.
  `complyapi` can adopt when populated. Repos with no Go code (`complytime`,
  `.github`, `community`) do not adopt.
- **No changes** to `sync-config.yml`, `ci_security.yml`, or any existing workflow.
- **Permissions**: `security-events: write` (already granted in similar workflows)
  and `contents: read` at job level.
