## ADDED Requirements

### Requirement: Stub SECURITY.md contains security contact

The synced `SECURITY.md` stub SHALL include the organization's security contact
email address directly in the file body, enabling OSPS Baseline Level 1
compliance (OSPS-VM-02.01) without requiring the reader to follow external
links.

#### Scenario: Reader opens SECURITY.md in any synced repository

- **WHEN** a user reads the `SECURITY.md` file in any org repository that
  receives the synced stub
- **THEN** the file MUST contain the security contact email
  (`complytime-security@redhat.com`) and a link to the full organization-wide
  security policy in the `community` repository

#### Scenario: Automated scanner checks for security contacts

- **WHEN** an automated tool (e.g., OpenSSF Scorecard) scans a repository's
  `SECURITY.md` for security contact information
- **THEN** the tool SHALL find contact information directly in the file without
  needing to follow external links

### Requirement: Stub SECURITY.md warns against public issue disclosure

The synced `SECURITY.md` stub SHALL include a warning that security
vulnerabilities MUST NOT be reported via public GitHub issues.

#### Scenario: Reader considers reporting a vulnerability

- **WHEN** a user reads the `SECURITY.md` file looking for how to report a
  security issue
- **THEN** the file MUST contain an explicit warning not to open a public
  GitHub issue for security vulnerabilities

### Requirement: SECURITY.md is included in sync configuration

The `sync-config.yml` file SHALL include a `SECURITY.md` entry in
`files_to_sync` so the stub is distributed to all org repositories during the
sync process.

#### Scenario: Sync process includes SECURITY.md

- **WHEN** the sync process runs against the org repositories
- **THEN** `SECURITY.md` SHALL be included in the set of files evaluated for
  synchronization

#### Scenario: Source and destination paths match

- **WHEN** the sync configuration is evaluated for `SECURITY.md`
- **THEN** the source path SHALL be `SECURITY.md` and the destination path
  SHALL be `SECURITY.md` (root of the target repository)

### Requirement: Community repository is excluded from SECURITY.md sync

The `community` repository SHALL be excluded from receiving the synced
`SECURITY.md` stub because it holds the canonical full security policy.

#### Scenario: Sync runs against community repository

- **WHEN** the sync process evaluates `SECURITY.md` for the `community`
  repository
- **THEN** the `community` repository SHALL be skipped for that file

#### Scenario: Sync runs against non-excluded repositories

- **WHEN** the sync process evaluates `SECURITY.md` for any repository not in
  the exclusion list (e.g., `complyctl`, `.github`, `website`)
- **THEN** the stub SHALL be synced to that repository

### Requirement: Sync test coverage for SECURITY.md entry

The test suite SHALL validate that the `SECURITY.md` sync entry exists in the
loaded `sync-config.yml` and follows expected conventions.

#### Scenario: Sync config loaded and validated

- **WHEN** the test suite loads `sync-config.yml` and checks `files_to_sync`
- **THEN** there SHALL be an entry with source `SECURITY.md`

#### Scenario: Community exclusion verified

- **WHEN** the test suite inspects the `SECURITY.md` entry in `files_to_sync`
- **THEN** the `exclude_repos` list for that entry SHALL contain `community`
