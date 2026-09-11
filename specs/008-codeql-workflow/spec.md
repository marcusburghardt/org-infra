# Feature Specification: Reusable CodeQL Analysis Workflow

## Document Overview

This specification details a centralized, reusable workflow for CodeQL semantic
static analysis (SAST) that can be consumed by Go repositories across the
organization. The workflow controls the Go version from the repository's own
`go.mod` or `go.work`, supports both automatic and manual build modes, and
uploads findings as advisory or blocking Code Scanning alerts.

**Key Metadata:**
- Workflow File: `.github/workflows/reusable_codeql.yml`
- Date: 2026-09-11
- Current Status: Active
- Related Issue: #537

## Core User Scenarios

### Priority 1: Go Version-Controlled CodeQL Analysis

Repository maintainers can enable CodeQL analysis that uses the Go version
declared in their repository's `go.mod` or `go.work` file, preventing the
runner version mismatch that breaks default code scanning setup when Dependabot
bumps the Go directive.

**Test Coverage:** Contract tests verify that `setup-go` executes before
`codeql/init`, that Go-specific steps are conditional on language input, and
that `go-version-file` is configurable.

### Priority 1: Advisory SAST Alerts

Repositories receive semantic SAST findings (interprocedural taint tracking,
data flow analysis) as non-blocking Code Scanning alerts by default. Findings
appear in the repository's Security tab without failing PR checks.

**Test Coverage:** Contract tests verify that `fail-on-alert` defaults to
`false` and that no workflow output is exposed (SARIF uploads directly).

### Priority 2: Configurable Build Mode

Repositories with non-standard build structures (multi-module workspaces,
custom toolchains) can provide a custom build command. Standard repositories
use CodeQL's autobuild without any configuration.

**Test Coverage:** Contract tests verify the build-command conditional logic
and that the custom build step uses environment variable indirection.

### Priority 2: Multi-Language Support

The workflow accepts any CodeQL-supported language. Go-specific steps are
conditional. Multi-language repositories invoke the workflow multiple times
via a caller-side matrix strategy.

**Test Coverage:** Contract tests verify that the `language` input is required
with no default and that `setup-go` is conditional on `inputs.language == 'go'`.

## Edge Cases Addressed

- **Multi-module Go workspaces**: Custom `build-command` with `GOWORK=off`
  for repos with broken `go.work` entries
- **Non-Go languages**: Build step is skipped entirely for interpreted
  languages (Python, JavaScript)
- **Blocking mode with no findings**: Workflow succeeds when `fail-on-alert`
  is true but CodeQL finds zero alerts

## Functional Requirements Summary

The specification mandates that the CodeQL workflow must:

1. **Control Go version**: Install the Go version from the repository's
   `go.mod` or `go.work` before initializing CodeQL
2. **Support configurable builds**: Use autobuild by default, accept custom
   build commands for non-standard repos
3. **Produce advisory alerts**: Upload SARIF to Code Scanning without
   failing the workflow, with an opt-in blocking mode
4. **Maintain security**: Follow least-privilege permissions, SHA-pinned
   actions, credential hygiene, and env-var indirection for inputs
5. **Provide flexible configuration**: Accept inputs for language, Go
   version file, build command, query suite, and alert behavior
6. **Support multi-language**: Handle any CodeQL-supported language with
   Go-specific steps conditional on the language input
7. **Prevent resource waste**: Use concurrency groups and job timeouts

## Success Metrics

Adoption success requires:
- Any Go repository can enable CodeQL analysis via a single consumer
  workflow file with zero custom configuration
- Go version mismatches from Dependabot bumps no longer break CodeQL
- Multi-module repositories can adopt with a custom build command
- Findings appear as Code Scanning alerts without blocking PRs
- Consumer workflows remain minimal (5-15 lines)

## Scope Boundaries

**Included:**
- Centralized reusable workflow for CodeQL SAST analysis
- Go version management via `actions/setup-go`
- Autobuild and manual build mode support
- Advisory and blocking alert modes
- Contract test for workflow structural validation
- Quickstart adoption guide with consumer workflow templates

**Excluded:**
- Syncing consumer workflows to downstream repos (opt-in model)
- Replacing SonarCloud (complementary tools)
- Scheduled analysis runs (event-based only)
- Enabling CodeQL on org-infra (no Go application code)
- Custom CodeQL query packs (use standard suites)
