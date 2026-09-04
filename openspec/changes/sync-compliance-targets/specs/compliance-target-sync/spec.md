## Purpose

Keeps the compliance scan target list in `complytime.yaml` synchronized with
the organization's repository inventory defined in `peribolos.yaml`, detecting
drift and filing pull requests to reconcile differences.

## ADDED Requirements

### Requirement: Detect added repositories

The system SHALL identify repositories present in `peribolos.yaml` that have
no corresponding scan target in `complytime.yaml`. The system SHALL return the
set of added repository names as a data structure.

#### Scenario: New repository added to peribolos

- **WHEN** a repository exists in `peribolos.yaml` but has no matching target
  in `complytime.yaml`
- **THEN** the system SHALL include it in the returned set of added
  repositories

#### Scenario: All repositories already covered

- **WHEN** every repository in `peribolos.yaml` has a matching target in
  `complytime.yaml`
- **THEN** the returned set of added repositories SHALL be empty

### Requirement: Detect removed repositories

The system SHALL identify scan targets in `complytime.yaml` whose
repositories no longer exist in `peribolos.yaml`. The system SHALL return the
set of removed repository names as a data structure.

#### Scenario: Repository removed from peribolos

- **WHEN** a `complytime.yaml` target references a repository that is not
  present in `peribolos.yaml`
- **THEN** the system SHALL include it in the returned set of removed
  repositories

#### Scenario: No stale targets

- **WHEN** every `complytime.yaml` target references a repository that exists
  in `peribolos.yaml`
- **THEN** the returned set of removed repositories SHALL be empty

### Requirement: Generate updated compliance configuration

When drift is detected, the system SHALL produce an updated `complytime.yaml`
that reflects the current repository inventory from `peribolos.yaml`.

#### Scenario: Repositories added

- **WHEN** new repositories are detected
- **THEN** the generated file SHALL contain a scan target entry for each new
  repository with an `id` derived from the repo name (prefixed with
  `complytime-` unless the repo name already starts with `complytime-`), a
  `variables.url` of `https://github.com/complytime/<repo-name>`, and a
  `variables.specs` value of `builtin:github/branch-rules.yaml`

#### Scenario: Repositories removed

- **WHEN** stale repositories are detected
- **THEN** the generated file SHALL omit the scan target entries for removed
  repositories

#### Scenario: Policies and complypacks preserved

- **WHEN** the system generates an updated configuration
- **THEN** the `policies` and `complypacks` sections SHALL be preserved
  unchanged from the original file

#### Scenario: Targets sorted deterministically

- **WHEN** the system generates an updated configuration
- **THEN** the targets SHALL be sorted alphabetically by target ID for
  consistent, reviewable output

#### Scenario: Output written to separate path

- **WHEN** the system generates an updated file
- **THEN** the output SHALL be written to a separate path (not in-place),
  preserving the original file in case of failure

### Requirement: Signal drift detection result

The system SHALL exit with a distinct status code to indicate the outcome,
enabling the calling workflow to decide whether to create a PR.

#### Scenario: No drift

- **WHEN** the generated target list matches the current target list
- **THEN** the system SHALL exit with status 0

#### Scenario: Drift detected

- **WHEN** the generated target list differs from the current target list
- **THEN** the system SHALL exit with status 2

#### Scenario: Operational error

- **WHEN** the system cannot complete the comparison (missing input file,
  YAML parse failure, invalid peribolos schema, missing org key)
- **THEN** the system SHALL exit with status 1 and print a diagnostic
  message to stderr

### Requirement: Handle invalid input gracefully

The system SHALL validate inputs and fail with clear diagnostics rather than
producing corrupt output.

#### Scenario: Peribolos file missing or malformed

- **WHEN** the peribolos file does not exist or contains invalid YAML
- **THEN** the system SHALL exit with status 1 and print a descriptive
  error to stderr

#### Scenario: Complytime file missing or malformed

- **WHEN** the complytime configuration file does not exist or contains
  invalid YAML
- **THEN** the system SHALL exit with status 1 and print a descriptive
  error to stderr

#### Scenario: Org key not found in peribolos

- **WHEN** the specified organization is not present in the peribolos data
- **THEN** the system SHALL exit with status 1 and print a descriptive
  error to stderr

#### Scenario: Repository name validation

- **WHEN** a repository name in peribolos does not match `^[a-zA-Z0-9._-]+$`
- **THEN** the system SHALL skip it with a warning to stderr

### Requirement: Exclude specified repositories

The system SHALL accept an explicit list of repository names to exclude from
comparison. Excluded repos SHALL be removed from both the peribolos set and
the complytime target set before drift is computed.

#### Scenario: Excluded repo in peribolos not treated as addition

- **WHEN** a repository is present in `peribolos.yaml` but listed in the
  exclusion list
- **THEN** the system SHALL NOT include it in the added set and SHALL NOT
  generate a target entry for it

#### Scenario: Excluded repo in complytime not treated as removal

- **WHEN** a `complytime.yaml` target references a repository listed in the
  exclusion list
- **THEN** the system SHALL NOT include it in the removed set

#### Scenario: No exclusions specified

- **WHEN** the exclusion list is empty
- **THEN** the system SHALL compare all repositories without filtering

### Requirement: Automated pull request on drift

When the target list is out of sync, the system SHALL create a pull request
with the updated `complytime.yaml`.

#### Scenario: PR created for drift

- **WHEN** the sync workflow detects drift between peribolos and complytime
  targets
- **THEN** a pull request SHALL be created with the updated `complytime.yaml`
  and a description listing added and removed repositories

#### Scenario: Existing PR updated

- **WHEN** commits are pushed to the fixed sync branch and a PR already
  exists for that branch
- **THEN** the existing PR SHALL be updated by the push rather than creating
  a duplicate

#### Scenario: No drift no PR

- **WHEN** peribolos and complytime targets are already in sync
- **THEN** no pull request SHALL be created
