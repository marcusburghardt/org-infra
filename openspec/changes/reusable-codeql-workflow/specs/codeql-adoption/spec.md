## Purpose

Quickstart guide and consumer workflow templates enabling downstream repositories
to adopt CodeQL analysis via the org-infra reusable workflow.

## ADDED Requirements

### Requirement: Opt-in adoption model

Downstream repositories SHALL adopt CodeQL by creating their own consumer
workflow that calls the reusable workflow cross-repo. The workflow SHALL NOT
be distributed via sync-config.yml.

#### Scenario: Standard Go repository adoption

- **WHEN** a single-module Go repository wants to adopt CodeQL
- **THEN** the repository creates a consumer workflow calling the reusable
  workflow with default inputs (no additional configuration required)

#### Scenario: Multi-module repository adoption

- **WHEN** a Go repository with a non-standard build structure wants to adopt
  CodeQL
- **THEN** the repository creates a consumer workflow providing a custom
  `go-version-file` and `build-command` input tailored to its layout

#### Scenario: Multi-language repository adoption

- **WHEN** a repository with multiple CodeQL-supported languages wants to adopt
- **THEN** the repository creates a consumer workflow using a matrix strategy
  to invoke the reusable workflow once per language

### Requirement: Documented adoption guide

A quickstart guide SHALL provide copy-paste consumer workflow examples for each
known repository structure in the org, including required permissions and
trigger configuration. Consumer workflow templates SHOULD include `paths:`
filters scoped to relevant source directories (e.g., `'**.go'`, `'go.mod'`,
`'go.sum'`) to avoid running CodeQL on documentation-only PRs.

#### Scenario: Guide completeness

- **WHEN** a repository maintainer reads the quickstart guide
- **THEN** the guide includes a working consumer workflow example for
  single-module Go repos, multi-module Go repos, and multi-language repos,
  each with trigger configuration and path filters

### Requirement: Contract test for the reusable workflow

A CI test workflow in org-infra SHALL validate the reusable workflow's input
contract and step structure without running actual CodeQL analysis. The test
SHALL follow the `test_vuln_scan_workflow.py` pattern: a Python pytest test
file that parses the workflow YAML and asserts on structural properties.

**Testability boundary**: The contract test validates structural properties
(parseable from YAML). Runtime properties (Go version matching, CodeQL
analysis execution, SARIF upload, fail-on-alert behavior) are verified only
via downstream adoption testing.

#### Scenario: Input defaults are validated

- **WHEN** the contract test parses the reusable workflow YAML
- **THEN** it confirms `language` is `required: true` with no default, and
  all optional inputs have their specified default values

#### Scenario: Permissions are least-privilege

- **WHEN** the contract test parses the workflow permissions
- **THEN** workflow-level permissions are `{}` and job-level permissions
  include only `contents: read`, `security-events: write`, and `actions: read`

#### Scenario: Action references are SHA-pinned

- **WHEN** the contract test scans action references
- **THEN** every `uses:` line matches the pattern `<owner>/<repo>@<40-hex-chars>`

#### Scenario: Go-conditional steps have correct expressions

- **WHEN** the contract test inspects conditional steps
- **THEN** the `setup-go` and build steps have `if:` conditions that check
  `inputs.language == 'go'`

#### Scenario: Step ordering is correct for Go

- **WHEN** the contract test inspects the step sequence
- **THEN** `setup-go` appears before `codeql/init` in the step list

### Requirement: SpecKit documentation

A feature specification and quickstart guide SHALL be created in the `specs/`
directory following the established `008-codeql-workflow` numbering pattern.

#### Scenario: Spec directory structure

- **WHEN** the feature is implemented
- **THEN** the `specs/` directory contains `spec.md` and `quickstart.md` under
  `specs/008-codeql-workflow/`
