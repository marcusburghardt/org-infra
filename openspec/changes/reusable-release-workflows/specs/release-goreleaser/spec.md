## ADDED Requirements

### Requirement: Reusable GoReleaser execution workflow

The GoReleaser workflow SHALL be a reusable workflow (`workflow_call`) that runs
GoReleaser with a standardized environment, callable by any Go project's consumer
release workflow.

#### Scenario: Consumer invokes GoReleaser workflow

- **WHEN** a consumer workflow calls `reusable_release_goreleaser.yml` with a tag input
- **THEN** GoReleaser executes using the repository's `.goreleaser.yaml` configuration
- **AND** a GitHub Release is created with the release artifacts

---

### Requirement: Go version read from go.mod

The workflow SHALL determine the Go version by reading the repository's `go.mod` file.
The Go version SHALL NOT be hardcoded in the workflow or accepted as an input.

#### Scenario: Go version from go.mod

- **WHEN** the repository's `go.mod` specifies `go 1.25.11`
- **THEN** the workflow installs Go version 1.25.11

#### Scenario: Missing go.mod
- **WHEN** the repository does not contain a `go.mod` file
- **THEN** the workflow fails with an error identifying the missing file

---

### Requirement: Supply chain tooling always installed

The workflow SHALL always install cosign (Sigstore keyless signing) and syft (SBOM
generation) before running GoReleaser, regardless of whether the repository's
`.goreleaser.yaml` references them.

#### Scenario: cosign and syft available to GoReleaser

- **WHEN** the GoReleaser workflow executes
- **THEN** the `cosign` binary is available on PATH
- **AND** the `syft` binary is available on PATH
- **AND** GoReleaser can invoke both for signing and SBOM generation

#### Scenario: cosign installation failure
- **WHEN** the cosign installer step fails (e.g., network error, release unavailable)
- **THEN** the workflow fails before GoReleaser execution
- **AND** the error output from the installer is surfaced

---

### Requirement: OIDC token for Sigstore keyless signing

The workflow SHALL request `id-token: write` permission to enable Sigstore keyless
signing via OIDC. This allows cosign to sign artifacts without managing private keys.

#### Scenario: Keyless signing succeeds

- **WHEN** GoReleaser invokes cosign with the `--yes` flag (keyless mode)
- **THEN** cosign obtains an OIDC token from the GitHub Actions provider
- **AND** signs the artifact using Sigstore Fulcio and Rekor

#### Scenario: OIDC token unavailable
- **WHEN** the GitHub Actions OIDC provider is unavailable or `id-token: write` is not granted
- **THEN** cosign keyless signing fails
- **AND** the workflow fails with an error identifying the permission issue

---

### Requirement: Tag environment variable set

The workflow SHALL set the `GORELEASER_CURRENT_TAG` environment variable to the input tag
value to ensure GoReleaser uses the correct version for the release.

#### Scenario: GoReleaser uses input tag

- **WHEN** the workflow is called with tag `v1.2.3`
- **THEN** GoReleaser creates a release for version `v1.2.3`
- **AND** the `GORELEASER_CURRENT_TAG` environment variable is set to `v1.2.3`

#### Scenario: GoReleaser build failure
- **WHEN** GoReleaser exits with a non-zero code during the build phase
- **THEN** the workflow fails and surfaces the GoReleaser error output
- **AND** partial artifacts are not published as a release

---

### Requirement: Full git history checkout

The workflow SHALL checkout the repository with full history (`fetch-depth: 0`) at the
specified tag ref, with `persist-credentials: false` for security.

#### Scenario: Full history available

- **WHEN** GoReleaser generates a changelog from git history
- **THEN** all commits and tags are available for changelog generation

---

### Requirement: Build cache disabled for release builds

The workflow SHALL disable Go module caching for release builds to ensure reproducible
artifacts not influenced by stale cache entries.

#### Scenario: No cached modules used

- **WHEN** the GoReleaser workflow builds release binaries
- **THEN** the Go module cache is not used
- **AND** modules are fetched fresh from the configured sources

---

### Requirement: Configurable GoReleaser version and arguments

The workflow SHALL accept optional inputs for the GoReleaser version and command-line
arguments, with sensible defaults.

#### Scenario: Default GoReleaser invocation

- **WHEN** no version or args inputs are provided
- **THEN** GoReleaser is invoked with the default version constraint
- **AND** GoReleaser is invoked with the default arguments `release --clean --verbose`

#### Scenario: Custom GoReleaser version

- **WHEN** the `goreleaser_version` input is set to a specific pinned version
- **THEN** that exact version of GoReleaser is used

---

### Requirement: Standardized action versions

The workflow SHALL pin all action references to specific commit SHAs, serving as the
single source of truth for action versions across all consuming repositories.

#### Scenario: Action version consistency

- **WHEN** two different repositories use `reusable_release_goreleaser.yml`
- **THEN** both use identical versions of checkout, setup-go, cosign-installer,
  sbom-action, and goreleaser-action

---

### Requirement: Least-privilege permissions

The workflow SHALL declare minimal permissions: `contents: write` for creating the
GitHub Release and uploading assets, and `id-token: write` for Sigstore OIDC.

#### Scenario: Permissions declared

- **WHEN** the workflow file is inspected
- **THEN** workflow-level permissions are empty
- **AND** job-level permissions grant only `contents: write` and `id-token: write`

---

### Requirement: Execution timeout

The GoReleaser workflow SHALL specify a job-level timeout appropriate for Go compilation and artifact generation across supported platforms.

#### Scenario: Timeout enforced
- **WHEN** the GoReleaser job exceeds the configured timeout
- **THEN** the workflow fails with the standard GitHub Actions timeout error

---

### Requirement: User inputs routed through env blocks

All workflow `run:` steps that reference user-controlled inputs SHALL use `env:` block
indirection rather than direct expression interpolation.

#### Scenario: Tag input in run block

- **WHEN** a `run:` step uses the tag input value
- **THEN** the value is accessed via an environment variable set in the step's `env:`
  block

---

### Requirement: Token routed through env blocks

All workflow `run:` steps that use `GITHUB_TOKEN` SHALL access it via an `env:` block variable, following the same indirection pattern required for user inputs.

#### Scenario: Token in GoReleaser environment
- **WHEN** GoReleaser executes with `GITHUB_TOKEN` for release publishing
- **THEN** the token is provided via an environment variable in the step's `env:` block
- **AND** no direct `${{ secrets.GITHUB_TOKEN }}` expression appears inside any `run:` script body

---

### Requirement: Action references pinned to commit SHAs

All `uses:` action references in the workflow SHALL be pinned to full 40-character commit
SHAs with an inline version comment.

#### Scenario: SHA-pinned actions

- **WHEN** the workflow file is inspected
- **THEN** every `uses:` reference specifies a full commit SHA
- **AND** each SHA is accompanied by an inline comment indicating the version
