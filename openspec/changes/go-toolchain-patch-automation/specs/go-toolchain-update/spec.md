## ADDED Requirements

### Requirement: Detect available Go patch updates

Renovate's `gomod` manager SHALL detect whether a newer Go patch
release exists within the current minor series by comparing the
`toolchain` directive in `go.mod` against upstream Go releases.

#### Scenario: Patch update available

- **WHEN** the `toolchain` directive in `go.mod` specifies a version
  older than the latest patch in the same minor series
- **THEN** Renovate SHALL create a PR proposing the update with both
  current and target versions identified

#### Scenario: Already on latest patch

- **WHEN** the `toolchain` directive in `go.mod` already matches the
  latest patch in the current minor series
- **THEN** Renovate SHALL take no action

#### Scenario: No toolchain directive present

- **WHEN** the `go.mod` file does not contain a `toolchain` directive
- **THEN** Renovate SHALL skip the repository with no error

### Requirement: Apply toolchain update to go.mod

Renovate SHALL update the `toolchain` directive in `go.mod` to the
latest patch version and regenerate dependent files via post-update
options.

#### Scenario: Standard Go module

- **WHEN** a patch update is available and the repository does not
  contain a `vendor/` directory
- **THEN** Renovate SHALL update the `toolchain` directive and run
  `go mod tidy` (the `gomodVendor` post-update option is a no-op
  when no `vendor/` directory exists)

#### Scenario: Vendored Go module (complyctl, complytime-providers)

- **WHEN** a patch update is available and the repository contains
  a `vendor/` directory
- **THEN** Renovate SHALL update the `toolchain` directive, run
  `go mod tidy`, and regenerate the vendor directory via
  `postUpdateOptions: ["gomodTidy", "gomodVendor"]`

### Requirement: Create pull request for toolchain update

Renovate SHALL create a pull request containing the toolchain update
with a descriptive title, body, and appropriate labels.

#### Scenario: New update PR

- **WHEN** a patch update is available and no existing update PR is
  open for this dependency
- **THEN** Renovate SHALL create a pull request on a dedicated branch
  with the current and target versions in the title and body

#### Scenario: Existing update PR

- **WHEN** a patch update is available and an update PR is already
  open for a previous patch version
- **THEN** Renovate SHALL rebase or update the existing PR with the
  new version rather than creating a duplicate

### Requirement: Restrict updates to patch versions only

The Renovate preset SHALL restrict updates to the `toolchain` depType
to patch versions only. Minor and major version changes are excluded.
This is achieved via the three-rule preset pattern with
`separateMinorPatch: true` (see `renovate-runner/spec.md` for the
rule structure).

#### Scenario: Patch version bump

- **WHEN** the latest available version differs only in the patch
  component from the current version
- **THEN** Renovate SHALL propose the update

#### Scenario: Minor version available

- **WHEN** a newer minor series is available but the current minor
  series has no newer patch
- **THEN** Renovate SHALL not propose any update

### Requirement: Multi-module repository support

Renovate SHALL detect and update `toolchain` directives in
repositories with multiple `go.mod` files in subdirectories
(e.g., `complytime-collector-components` with modules in
`/proofwatch` and `/truthbeam`).

#### Scenario: Multi-module repository

- **WHEN** a repository contains multiple `go.mod` files in
  subdirectories rather than a single root-level `go.mod`
- **THEN** Renovate SHALL detect and update the `toolchain`
  directive in each `go.mod` independently

#### Scenario: Mixed vendoring in multi-module repository

- **WHEN** a multi-module repository has some modules that vendor
  and some that do not
- **THEN** Renovate SHALL apply `gomodVendor` only to modules
  that contain a `vendor/` directory

### Requirement: Scoped to target repositories only

The Renovate runner SHALL operate only on explicitly listed
repositories. Target repositories are defined in the centralized
`renovate-config.js` in org-infra.

#### Scenario: Listed Go repository

- **WHEN** a repository is listed in the `repositories` array of
  `renovate-config.js`
- **THEN** Renovate SHALL scan it for toolchain patch updates

#### Scenario: Unlisted repository

- **WHEN** a repository is not listed in the `repositories` array
- **THEN** Renovate SHALL not scan or interact with it

### Requirement: PRs trigger CI automatically

PRs created by Renovate SHALL trigger CI workflows (`pull_request`
events) automatically, without maintainer intervention.

#### Scenario: App token PR

- **WHEN** Renovate creates a PR using the GitHub App token
- **THEN** the PR SHALL trigger `pull_request` CI workflows with
  full secret access, as the actor is the App and not
  `github-actions[bot]`
