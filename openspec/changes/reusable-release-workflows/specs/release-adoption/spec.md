## ADDED Requirements

### Requirement: Adoption guide for release workflows

An adoption guide SHALL exist in `docs/RELEASE_WORKFLOWS.md` providing maintainers with
complete instructions to migrate their repositories to the reusable release workflows.

#### Scenario: Guide found in documentation

- **WHEN** a maintainer looks for release workflow documentation in org-infra
- **THEN** `docs/RELEASE_WORKFLOWS.md` exists with adoption instructions

---

### Requirement: Architecture overview with visual diagram

The adoption guide SHALL include an overview section with an ASCII architecture diagram
showing the reusable workflows, their composition patterns, and how they relate to
existing publishing workflows.

#### Scenario: Architecture diagram present

- **WHEN** a maintainer reads the overview section
- **THEN** an ASCII diagram shows the preflight and GoReleaser workflows
- **AND** the diagram shows how they compose with existing reusable workflows
  (publish_ghcr, trivy_image_scan, sign_and_verify)

---

### Requirement: Per-repo-type adoption instructions

The adoption guide SHALL provide separate adoption instructions for each repository
type: CLI/binary tool (GoReleaser), container service, library (release notes only), and
hybrid (both binary and container).

#### Scenario: CLI/binary tool instructions

- **WHEN** a maintainer of a GoReleaser-based repo reads the adoption guide
- **THEN** they find step-by-step instructions specific to binary release repos
- **AND** a copy-pasteable consumer workflow template

#### Scenario: Container service instructions

- **WHEN** a maintainer of a container-only repo reads the adoption guide
- **THEN** they find step-by-step instructions for adding preflight before their
  existing container pipeline

#### Scenario: Library instructions

- **WHEN** a maintainer of a Go library reads the adoption guide
- **THEN** they find instructions for using preflight with a simple GitHub Release step

---

### Requirement: Consumer workflow templates

The adoption guide SHALL include complete, copy-pasteable consumer workflow YAML
templates for each repo type. Templates SHALL include comments explaining each input.

#### Scenario: Template used without modification

- **WHEN** a maintainer copies the CLI/binary tool template into their repo
- **AND** their repo has `ci_local.yml`, `ci_checks.yml`, and `ci_security.yml`
- **THEN** the workflow functions correctly with zero modification

#### Scenario: Template with override

- **WHEN** a maintainer copies the template and adds a `ci_checks` override
- **THEN** the workflow uses the explicit check list instead of auto-discovery

---

### Requirement: CI check auto-discovery explanation

The adoption guide SHALL explain how automatic CI check discovery works, which files are
read, how check names are constructed, and when to use the explicit `ci_checks` override.

#### Scenario: Auto-discovery mechanism documented

- **WHEN** a maintainer reads the CI check discovery section
- **THEN** the section describes which files are read (`ci_local.yml`, `ci_checks.yml`,
  `ci_security.yml`), how check names are constructed, and when the `ci_checks` override
  should be used, with examples

---

### Requirement: GoReleaser configuration standards

The adoption guide SHALL document the required supply chain sections that every
`.goreleaser.yaml` file should include (SBOM generation and cosign signing), with
copy-pasteable YAML blocks.

#### Scenario: Supply chain blocks documented

- **WHEN** a maintainer reads the GoReleaser configuration section
- **THEN** the section includes copy-pasteable `sboms:` and `signs:` YAML blocks and
  states they are required by the organization's supply chain standards

---

### Requirement: Workflow inputs reference tables

The adoption guide SHALL include reference tables documenting all inputs and outputs for
both reusable workflows, including types, defaults, and descriptions.

#### Scenario: Input reference consulted

- **WHEN** a maintainer needs to know what inputs `reusable_release_preflight.yml`
  accepts
- **THEN** a table lists each input with its type, required/optional status, default
  value, and description

---

### Requirement: Migration checklist

The adoption guide SHALL include a migration checklist that maintainers can follow to
verify their repo is ready for adoption and track progress through the migration steps.

#### Scenario: Checklist used for migration

- **WHEN** a maintainer starts migrating their repo
- **THEN** they can follow a checklist of items to verify and complete
- **AND** the checklist covers prerequisites, workflow creation, old workflow removal,
  testing, and documentation updates

---

### Requirement: Troubleshooting section

The adoption guide SHALL include a troubleshooting section covering common issues
encountered during adoption, with problem descriptions and solutions.

#### Scenario: Troubleshooting consulted

- **WHEN** a maintainer encounters "no CI checks discovered" during a release
- **THEN** the troubleshooting section explains the cause and provides a solution

---

### Requirement: Repo adoption status tracking

The adoption guide SHALL include a table showing each organization repository, its
current release type, CI local presence, supply chain status, and adoption readiness.

#### Scenario: Status table consulted

- **WHEN** a maintainer wants to know the adoption status of their repo
- **THEN** a table shows whether their repo has `ci_local.yml`, its release type, and
  what steps are needed

---

### Requirement: Reference to release process runbook

The adoption guide SHALL reference the separate release process document
(`docs/RELEASE_PROCESS.md`) and explain the distinction: the adoption guide covers
one-time workflow setup, while the release process document covers ongoing release
operations.

#### Scenario: Distinction understood

- **WHEN** a maintainer reads the adoption guide
- **THEN** they find a reference to `docs/RELEASE_PROCESS.md` for operational procedures
- **AND** they understand that the adoption guide is for setup and the release process
  doc is for day-to-day release operations
