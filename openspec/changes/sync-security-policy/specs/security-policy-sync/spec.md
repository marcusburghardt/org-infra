## ADDED Requirements

### Requirement: Stub SECURITY.md contains security contact

The synced `SECURITY.md` stub SHALL include the organization's security contact
email address directly in the file body, enabling OSPS Baseline Level 1
compliance (OSPS-VM-02.01) without requiring the reader to follow external
links.

#### Scenario: Reader opens SECURITY.md in any synced repository

- **GIVEN** a repository that receives the synced `SECURITY.md` stub
- **WHEN** a user reads the `SECURITY.md` file
- **THEN** the file MUST contain the security contact email
  (`complytime-security@redhat.com`) and a link to the full organization-wide
  security policy in the `community` repository

#### Scenario: Automated scanner checks for security contacts

- **GIVEN** a repository that receives the synced `SECURITY.md` stub
- **WHEN** an automated tool (e.g., OpenSSF Scorecard) scans the repository's
  `SECURITY.md` for security contact information
- **THEN** the tool SHALL find contact information directly in the file without
  needing to follow external links

### Requirement: Stub SECURITY.md references GitHub Private Vulnerability Reporting

The synced `SECURITY.md` stub SHALL include instructions for reporting
vulnerabilities via GitHub's Private Vulnerability Reporting feature.

#### Scenario: Reader looks for private reporting instructions

- **GIVEN** a repository that receives the synced `SECURITY.md` stub
- **WHEN** a user reads the `SECURITY.md` file looking for how to report a
  security issue
- **THEN** the file MUST reference GitHub Private Vulnerability Reporting as a
  reporting channel

### Requirement: Stub SECURITY.md warns against public issue disclosure

The synced `SECURITY.md` stub SHALL include a warning that security
vulnerabilities MUST NOT be reported via public GitHub issues.

#### Scenario: Reader considers reporting a vulnerability

- **GIVEN** a repository that receives the synced `SECURITY.md` stub
- **WHEN** a user reads the `SECURITY.md` file looking for how to report a
  security issue
- **THEN** the file MUST contain an explicit warning not to open a public
  GitHub issue for security vulnerabilities

### Requirement: SECURITY.md is included in sync configuration

The `sync-config.yml` file SHALL include a `SECURITY.md` entry in
`files_to_sync` so the stub is distributed to all org repositories during the
sync process.

#### Scenario: Sync process includes SECURITY.md

- **GIVEN** `sync-config.yml` has been loaded successfully
- **WHEN** the sync process runs against the org repositories
- **THEN** `SECURITY.md` SHALL be included in the set of files evaluated for
  synchronization

#### Scenario: Source and destination paths match

- **GIVEN** `sync-config.yml` has been loaded successfully
- **WHEN** the sync configuration is evaluated for `SECURITY.md`
- **THEN** the source path SHALL be `SECURITY.md` and the destination path
  SHALL be `SECURITY.md` (root of the target repository)

### Requirement: Community repository is excluded from SECURITY.md sync

The `community` repository SHALL be excluded from receiving the synced
`SECURITY.md` stub because it holds the canonical full security policy.

#### Scenario: Sync runs against community repository

- **GIVEN** `sync-config.yml` has been loaded with the `SECURITY.md` entry
- **WHEN** the sync process evaluates `SECURITY.md` for the `community`
  repository
- **THEN** the `community` repository SHALL be skipped for that file

#### Scenario: Sync runs against non-excluded repositories

- **GIVEN** `sync-config.yml` has been loaded with the `SECURITY.md` entry
- **WHEN** the sync process evaluates `SECURITY.md` for any repository not in
  the exclusion list (e.g., `complyctl`, `.github`, `website`)
- **THEN** the stub SHALL be synced to that repository

### Requirement: Sync test coverage for SECURITY.md entry

The test suite SHALL validate that the `SECURITY.md` sync entry exists in the
loaded `sync-config.yml` and follows expected conventions.

#### Scenario: Sync config loaded and validated

- **GIVEN** the test suite has loaded `sync-config.yml`
- **WHEN** the test checks `files_to_sync`
- **THEN** there SHALL be an entry with source `SECURITY.md`

#### Scenario: Community exclusion verified

- **GIVEN** the test suite has loaded `sync-config.yml`
- **WHEN** the test inspects the `SECURITY.md` entry in `files_to_sync`
- **THEN** the `exclude_repos` list for that entry SHALL contain `community`

### Requirement: Content validation for SECURITY.md stub

The test suite SHALL validate that the `SECURITY.md` file in org-infra contains
the required content elements for OSPS Baseline Level 1 compliance.

#### Scenario: Security contact email is present

- **GIVEN** the test suite reads `SECURITY.md` from the repository root
- **WHEN** the test checks the file content
- **THEN** the file SHALL contain the string `complytime-security@redhat.com`

#### Scenario: Public issue disclosure warning is present

- **GIVEN** the test suite reads `SECURITY.md` from the repository root
- **WHEN** the test checks the file content
- **THEN** the file SHALL contain a warning against opening public GitHub
  issues for security vulnerabilities

#### Scenario: Link to canonical policy is present

- **GIVEN** the test suite reads `SECURITY.md` from the repository root
- **WHEN** the test checks the file content
- **THEN** the file SHALL contain a link to `community/SECURITY.md`
