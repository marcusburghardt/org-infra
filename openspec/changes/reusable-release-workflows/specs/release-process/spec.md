## ADDED Requirements

### Requirement: Generic release process document

A release process document SHALL exist in `docs/RELEASE_PROCESS.md` providing a
repository-agnostic runbook that covers the standard release flow for all projects
adopting the reusable release workflows.

#### Scenario: Document found in org-infra

- **WHEN** an operator looks for release process documentation in org-infra
- **THEN** `docs/RELEASE_PROCESS.md` exists with the standard release process

---

### Requirement: Release philosophy statement

The release process document SHALL open with a statement establishing the release
philosophy: simplicity, automation, predictability, and low cost for maintainers.

#### Scenario: Philosophy communicated

- **WHEN** an operator reads the opening section
- **THEN** the section contains a statement establishing simplicity, automation, and
  predictability as guiding principles

---

### Requirement: Standard release flow description

The release process document SHALL describe the standard release flow from trigger to
published release, covering: the `workflow_dispatch` trigger with a tag input, preflight
validation (tag format, CI gates, security scan, semver ordering), build and artifact
generation, and GitHub Release publication.

#### Scenario: End-to-end flow documented

- **WHEN** an operator reads the release flow section
- **THEN** the section describes each phase of the release pipeline: workflow_dispatch
  trigger, preflight validation, build and artifact generation, and GitHub Release
  publication
- **AND** they know what validations the preflight performs automatically

#### Scenario: Operator follows the flow to trigger a release

- **WHEN** an operator follows the documented steps to trigger a release
- **THEN** they can successfully initiate a release via `workflow_dispatch`
- **AND** they understand how to specify the tag input

---

### Requirement: Supply chain expectations

The release process document SHALL describe the supply chain artifacts that every release
is expected to produce (cosign signatures, SBOMs) and how to verify them after a release.

#### Scenario: Supply chain artifacts documented

- **WHEN** an operator reads the supply chain section
- **THEN** the section lists the expected artifacts: checksums, cosign Sigstore
  signatures, and SBOMs
- **AND** the section includes verification commands for cosign signature validation and
  SBOM inspection

---

### Requirement: Release verification steps

The release process document SHALL include post-release verification steps that an
operator can follow to confirm a release completed successfully, including checking the
GitHub Release page, verifying artifact checksums, and validating supply chain
signatures.

#### Scenario: Verification checklist followed

- **WHEN** an operator completes a release and follows the verification steps
- **THEN** they can confirm the release artifacts are complete and correctly signed

---

### Requirement: Failure recovery procedures

The release process document SHALL document recovery procedures for common failure
scenarios: GoReleaser failure after tag creation (re-run the workflow), preflight
validation failures (fix the issue and re-trigger), and partial release cleanup.

#### Scenario: GoReleaser failure recovery

- **WHEN** a release fails during the GoReleaser build phase
- **THEN** the document explains that the workflow can be safely re-run
- **AND** the preflight detects the existing tag at HEAD and skips to the build phase

#### Scenario: Preflight validation failure recovery

- **WHEN** a release fails because CI checks have not passed
- **THEN** the document explains what to verify and how to re-trigger after fixing

---

### Requirement: Release cadence guidance

The release process document SHALL provide guidance on release cadence expectations,
noting that specific cadence is repository-dependent and should be agreed upon by
project maintainers.

#### Scenario: Cadence guidance provided

- **WHEN** an operator reads the cadence section
- **THEN** the section states that release cadence is repository-dependent and agreed
  upon by project maintainers
- **AND** the document provides general guidance without prescribing a fixed schedule

---

### Requirement: Extension points for repository-specific procedures

The release process document SHALL explicitly identify extension points where
repositories are expected to add their own procedures, and provide guidance on how to
structure a repository-level release process document that references the org-wide
standard.

#### Scenario: Extension guidance followed

- **WHEN** a maintainer creates a repo-level `docs/RELEASE_PROCESS.md`
- **THEN** the org-wide document provides clear guidance on how to reference the
  standard and where to add repo-specific sections

#### Scenario: Common extension categories identified

- **WHEN** a maintainer reads the extension points section
- **THEN** they find a list of common repo-specific procedures to document (e.g.,
  downstream package updates, container promotion, Homebrew tap publishing, registry
  mirroring)

---

### Requirement: Pre-release and release candidate process

The release process document SHALL describe how pre-release versions (alpha, beta, RC)
work with the standard release flow, including how the `allow_prerelease` input affects
tag validation and how pre-release ordering is handled correctly.

#### Scenario: Pre-release workflow documented

- **WHEN** an operator needs to publish a beta release
- **THEN** the section documents the `allow_prerelease` input with a configuration
  example and describes the expected version progression (alpha, beta, RC, GA)

---

### Requirement: Roles and responsibilities

The release process document SHALL identify who can trigger releases and what
permissions are needed, without naming specific individuals.

#### Scenario: Roles documented

- **WHEN** a new contributor reads the roles section
- **THEN** the section identifies project maintainers as the actors who trigger releases
  and lists the required repository permissions
