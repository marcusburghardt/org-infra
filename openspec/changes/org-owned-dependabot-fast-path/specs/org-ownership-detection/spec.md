# Spec: org-ownership-detection

## ADDED Requirements

### Requirement: Detect org-owned dependencies

The Dependabot reviewer workflow SHALL determine whether a dependency
originates from the same GitHub organization as the repository consuming it.
The check SHALL compare the first path segment of the dependency name against
the consuming repository's owner (`github.repository_owner`). The result SHALL
be exposed as a workflow output named `is_org_owned` with string values `"true"`
or `"false"` for downstream decision logic.

The ownership classification is only meaningful when the PR author has been
verified as `dependabot[bot]` by the existing actor gate. The `is_org_owned`
output alone is not sufficient for trust decisions without the actor
verification.

#### Scenario: Reusable workflow dependency from the same org

- **WHEN** the dependency name is
  `complytime/org-infra/.github/workflows/reusable_security.yml` and the
  consuming repository owner is `complytime`
- **THEN** the output `is_org_owned` SHALL be `"true"`

#### Scenario: Standard action from the same org

- **WHEN** the dependency name is `complytime/some-action` and the consuming
  repository owner is `complytime`
- **THEN** the output `is_org_owned` SHALL be `"true"`

#### Scenario: Third-party dependency

- **WHEN** the dependency name is `actions/checkout` and the consuming
  repository owner is `complytime`
- **THEN** the output `is_org_owned` SHALL be `"false"`

#### Scenario: Dependency with no recognizable owner segment

- **WHEN** the dependency name cannot be split into an owner segment (e.g.,
  a bare package name from a non-GitHub ecosystem)
- **THEN** the output `is_org_owned` SHALL be `"false"`

#### Scenario: Empty dependency name

- **WHEN** the dependency name is empty or unset (dependency info extraction
  failed)
- **THEN** the output `is_org_owned` SHALL be `"false"`

#### Scenario: Forked repository consuming original org's dependency

- **WHEN** a fork owned by `someuser` consumes a dependency from
  `complytime/org-infra` and `github.repository_owner` is `someuser`
- **THEN** the output `is_org_owned` SHALL be `"false"`

#### Scenario: Transferred repository

- **WHEN** a repository was transferred from `complytime` to `other-org` and
  `github.repository_owner` now returns `other-org`
- **THEN** dependencies from `complytime/*` SHALL be classified as `"false"`
  (correct behavior -- ownership reflects the current state)

#### Scenario: Unknown update type for org-owned dependency

- **WHEN** a Dependabot PR bumps an org-owned dependency but the update type
  cannot be determined (risk defaults to `high`)
- **THEN** the output `is_org_owned` SHALL be `"true"` (ownership is
  independent of risk classification; risk gating is handled downstream)

### Requirement: No configuration for ownership detection

The ownership detection mechanism SHALL NOT require any workflow inputs,
environment variables, or allowlists to function. It SHALL rely solely on
runtime context available in every workflow run.

#### Scenario: Reusable workflow called without extra inputs

- **WHEN** the Dependabot reviewer workflow is called by a consumer workflow
  that provides no ownership-related inputs
- **THEN** ownership detection SHALL still produce a correct result based on
  the runtime context

### Requirement: Ownership output available to callers

The Dependabot reviewer workflow SHALL expose the ownership classification as
a `workflow_call` output named `is_org_owned` (string, `"true"` or `"false"`)
that can be consumed by downstream jobs in the calling workflow.

#### Scenario: Consumer workflow reads ownership output

- **WHEN** the Dependabot reviewer workflow completes for an org-owned
  dependency
- **THEN** the calling workflow SHALL be able to read
  `needs.call_dependabot_reviewer.outputs.is_org_owned` as `"true"` and use
  it in conditional logic
