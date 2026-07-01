## ADDED Requirements

### Requirement: Manual release trigger with tag input

The preflight workflow SHALL be triggered exclusively via `workflow_call` with a required
`tag` string input specifying the semver version to release.

#### Scenario: Reusable workflow invoked by consumer

- **WHEN** a consumer workflow calls `reusable_release_preflight.yml` with tag `v1.2.3`
- **THEN** the preflight executes all validation steps using the provided tag value

---

### Requirement: Full history checkout with security hardening

The preflight workflow SHALL checkout the repository with full git history for tag
operations and file-based CI discovery. Credentials SHALL NOT be persisted beyond the
checkout step; tag push authentication SHALL use explicit token-based mechanisms.

#### Scenario: Full history available for tag operations

- **WHEN** the preflight workflow executes
- **THEN** the repository is checked out with full history (all tags and commits
  available)
- **AND** `persist-credentials` is set to `false`

#### Scenario: Tag push uses explicit authentication

- **WHEN** the tag creation step pushes to the remote
- **THEN** authentication uses the `GITHUB_TOKEN` via `gh` CLI or explicit URL, not
  persisted git credentials

---

### Requirement: Tag format validation with configurable pre-release support

The preflight workflow SHALL validate that the provided tag matches strict semver format
(`v<major>.<minor>.<patch>`). When the `allow_prerelease` input is set to `true`, the
workflow SHALL also accept tags with pre-release suffixes
(`v<major>.<minor>.<patch>-<prerelease>`).

#### Scenario: Valid strict semver tag accepted

- **WHEN** the preflight receives tag `v1.2.3` with `allow_prerelease` set to `false`
- **THEN** the tag format validation passes

#### Scenario: Pre-release tag accepted when allowed

- **WHEN** the preflight receives tag `v1.0.0-beta.0` with `allow_prerelease` set to
  `true`
- **THEN** the tag format validation passes

#### Scenario: Pre-release tag rejected when not allowed

- **WHEN** the preflight receives tag `v1.0.0-beta.0` with `allow_prerelease` set to
  `false`
- **THEN** the workflow fails with an error describing the required format

#### Scenario: Invalid tag format rejected

- **WHEN** the preflight receives tag `1.0.0` (missing `v` prefix)
- **THEN** the workflow fails with an error describing the required format

#### Scenario: Incomplete version rejected

- **WHEN** the preflight receives tag `v1.0` (missing patch component)
- **THEN** the workflow fails with an error describing the required format

#### Scenario: Build metadata rejected

- **WHEN** the preflight receives tag `v1.0.0+build.123`
- **THEN** the workflow fails with an error stating build metadata is not supported

#### Scenario: Pre-release conforms to semver section 9

- **WHEN** the preflight receives tag `v1.0.0-alpha.1.beta` with `allow_prerelease` set
  to `true`
- **THEN** the tag format validation passes (dot-separated alphanumeric identifiers with
  hyphens)

---

### Requirement: Smart tag uniqueness with re-run resilience

The preflight workflow SHALL check whether the tag already exists on the remote. If the
tag exists and points at the current HEAD commit, the workflow SHALL treat this as a
re-run and proceed. If the tag exists at a different commit, the workflow SHALL fail.

#### Scenario: Tag does not exist

- **WHEN** the provided tag does not exist on the remote
- **THEN** the uniqueness check passes and the workflow proceeds to ordering verification

#### Scenario: Tag exists at HEAD (re-run)

- **WHEN** the provided tag already exists and points at HEAD
- **THEN** the uniqueness check passes
- **AND** semver ordering verification is skipped
- **AND** unreleased commits verification is skipped
- **AND** tag creation is skipped

#### Scenario: Tag exists at different commit (conflict)

- **WHEN** the provided tag already exists and points at a commit other than HEAD
- **THEN** the workflow fails with an error identifying the conflicting commit

---

### Requirement: Semver ordering verification

The preflight workflow SHALL verify that the new tag represents a version higher than the
latest existing tag. For tags without pre-release suffixes, version sort comparison is
sufficient. When either the new tag or the latest existing tag contains a pre-release
suffix, the workflow SHALL use semver-aware comparison where pre-release versions have
lower precedence than the associated release version.

#### Scenario: Higher version accepted

- **WHEN** the latest existing tag is `v1.0.0` and the new tag is `v1.1.0`
- **THEN** the ordering verification passes

#### Scenario: Lower version rejected

- **WHEN** the latest existing tag is `v2.0.0` and the new tag is `v1.5.0`
- **THEN** the workflow fails with an error identifying the ordering violation

#### Scenario: First release accepted

- **WHEN** no existing tags are found in the repository
- **THEN** the ordering verification passes

#### Scenario: GA release after pre-release accepted

- **WHEN** the latest existing tag is `v1.0.0-beta.0` and the new tag is `v1.0.0`
- **THEN** the ordering verification passes (GA has higher precedence than pre-release)

#### Scenario: Pre-release after GA rejected

- **WHEN** the latest existing tag is `v1.0.0` and the new tag is `v1.0.0-rc.1`
- **THEN** the workflow fails with an error identifying the ordering violation

#### Scenario: Sequential pre-releases accepted

- **WHEN** the latest existing tag is `v1.0.0-alpha.1` and the new tag is
  `v1.0.0-beta.0`
- **THEN** the ordering verification passes

#### Scenario: Numeric vs alphanumeric pre-release precedence

- **WHEN** the latest existing tag is `v1.0.0-1` and the new tag is `v1.0.0-alpha`
- **THEN** the ordering verification passes (numeric identifiers have lower precedence
  than alphanumeric)

#### Scenario: Dot-separated identifier comparison

- **WHEN** the latest existing tag is `v1.0.0-alpha.1` and the new tag is
  `v1.0.0-alpha.beta`
- **THEN** the ordering verification passes

#### Scenario: Numeric identifier ordering

- **WHEN** the latest existing tag is `v1.0.0-beta.2` and the new tag is
  `v1.0.0-beta.11`
- **THEN** the ordering verification passes (numeric identifiers compared as integers)

---

### Requirement: Automatic CI check discovery from workflow files

When no explicit `ci_checks` input is provided, the preflight workflow SHALL discover
required CI checks by reading workflow files from the checked-out repository.

#### Scenario: ci_local.yml discovered

- **WHEN** the file `.github/workflows/ci_local.yml` exists in the repository
- **THEN** the preflight extracts the workflow name and job names from the file
- **AND** constructs expected check names using the pattern
  `<workflow name> / <job name>`
- **AND** requires all constructed check names to have passed on HEAD

#### Scenario: ci_checks.yml discovered

- **WHEN** the file `.github/workflows/ci_checks.yml` exists in the repository
- **THEN** the preflight requires the check `CI / Standardized CI / Run linters`
  (constructed as `<workflow name> / <caller job name> / <reusable job name>`)
  to have passed on HEAD

#### Scenario: ci_security.yml discovered

- **WHEN** the file `.github/workflows/ci_security.yml` exists in the repository
- **THEN** the preflight requires at least one check matching the pattern
  `Security Checks / OSV-Scanner / *` to have concluded `success` on HEAD

#### Scenario: Workflow file not present

- **WHEN** any of the three discovery files does not exist in the repository
- **THEN** the corresponding gate is skipped without error

#### Scenario: No checks discovered and no override provided

- **WHEN** none of the three discovery files exist and no `ci_checks` input is provided
- **THEN** the preflight emits a warning but does not fail

#### Scenario: YAML parser unavailable

- **WHEN** the `yq` tool is not found on the runner
- **THEN** the `ci_local.yml` discovery step is skipped with a warning
- **AND** discovery proceeds with `ci_checks.yml` and `ci_security.yml` only
- **AND** the warning message identifies the missing tool

---

### Requirement: Explicit CI check override

When the `ci_checks` input is provided as a JSON array of check names, the preflight
workflow SHALL use the provided list instead of auto-discovery.

#### Scenario: Explicit check list provided

- **WHEN** the `ci_checks` input is `["unit-test", "e2e-test", "integration-test"]`
- **THEN** the preflight verifies exactly those three checks passed on HEAD
- **AND** file-based auto-discovery is skipped

#### Scenario: Malformed JSON rejected

- **WHEN** the `ci_checks` input contains invalid JSON (e.g., `["unit-test"`)
- **THEN** the workflow fails with an error identifying the expected JSON array format

#### Scenario: Empty array rejected

- **WHEN** the `ci_checks` input is an empty array `[]`
- **THEN** the workflow fails with an error stating at least one check name is required

#### Scenario: Input sanitized

- **WHEN** the `ci_checks` input is a valid JSON array
- **THEN** each element is validated to contain only alphanumeric characters, hyphens,
  underscores, spaces, and forward slashes

---

### Requirement: CI check verification with proper error handling

The preflight workflow SHALL verify check conclusions by querying the GitHub Checks API
with pagination. API errors (rate limits, network timeouts, authentication failures)
SHALL be surfaced as distinct errors, not masked as "check not found."

#### Scenario: Check passed on HEAD

- **WHEN** the check `unit-test` has conclusion `success` on HEAD
- **THEN** the verification passes for that check

#### Scenario: Check failed on HEAD

- **WHEN** the check `unit-test` has conclusion `failure` on HEAD
- **THEN** the workflow fails with an error identifying the check and its conclusion

#### Scenario: Check not found on HEAD

- **WHEN** no check run with name `unit-test` exists for the HEAD commit
- **THEN** the workflow fails with an error stating the check was not found

#### Scenario: API error surfaced

- **WHEN** the GitHub Checks API returns a rate limit or network error
- **THEN** the workflow fails with an error identifying the API failure
- **AND** the error message includes the API response, not "not found"

#### Scenario: More than 30 check runs on HEAD

- **WHEN** the HEAD commit has more than 30 check runs
- **THEN** the verification queries all pages of results
- **AND** correctly identifies checks beyond the first page

---

### Requirement: Security scan gate

When `ci_security.yml` exists in the repository, the preflight workflow SHALL verify
that at least one security scan check has passed on HEAD.

#### Scenario: Security scan passed

- **WHEN** `ci_security.yml` exists and a matching security scan check has conclusion
  `success` on HEAD
- **THEN** the security gate passes

#### Scenario: No security scan passed

- **WHEN** `ci_security.yml` exists and no matching security scan check has conclusion
  `success` on HEAD
- **THEN** the workflow fails with an error identifying the security gate failure

---

### Requirement: Unreleased commits verification

The preflight workflow SHALL verify that commits exist between the latest existing tag
and HEAD to prevent empty releases.

#### Scenario: Commits exist since last tag

- **WHEN** there are 5 commits since the latest tag
- **THEN** the verification passes and reports the commit count

#### Scenario: No commits since last tag

- **WHEN** there are zero commits since the latest tag
- **THEN** the workflow fails with an error stating nothing to release

#### Scenario: First release with commits

- **WHEN** no previous tags exist and the repository has commits
- **THEN** the verification passes

#### Scenario: Empty repository

- **WHEN** no previous tags exist and the repository has no commits
- **THEN** the workflow fails with an error stating nothing to release

---

### Requirement: Idempotent annotated tag creation

The preflight workflow SHALL create an annotated tag on HEAD and push it to the remote.
If the tag already exists (re-run path), the creation step SHALL be skipped.

#### Scenario: Tag created and pushed

- **WHEN** the provided tag does not exist on the remote
- **THEN** the workflow creates an annotated tag on HEAD
- **AND** pushes it to the remote

#### Scenario: Tag creation skipped on re-run

- **WHEN** the provided tag already exists at HEAD (re-run detected in uniqueness step)
- **THEN** the tag creation step is skipped

---

### Requirement: Preflight outputs

The preflight workflow SHALL output the validated tag string and whether the tag was
created or already existed, for use by downstream jobs.

#### Scenario: Tag created output

- **WHEN** the preflight creates a new tag
- **THEN** the `tag` output contains the validated tag string
- **AND** the `tag_created` output is `true`

#### Scenario: Re-run output

- **WHEN** the preflight detects a re-run (tag already at HEAD)
- **THEN** the `tag` output contains the validated tag string
- **AND** the `tag_created` output is `false`

---

### Requirement: Configurable default branch

The preflight workflow SHALL accept an optional `default_branch` input (defaulting to
`main`) used for CI check context. The input SHALL be validated to contain only
alphanumeric characters, hyphens, underscores, and forward slashes, and SHALL NOT begin
with a hyphen.

#### Scenario: Default branch used

- **WHEN** no `default_branch` input is provided
- **THEN** the workflow uses `main` as the default branch

#### Scenario: Custom default branch

- **WHEN** `default_branch` is set to `develop`
- **THEN** the workflow uses `develop` for branch context

#### Scenario: Invalid branch name rejected

- **WHEN** `default_branch` contains shell metacharacters or begins with a hyphen
- **THEN** the workflow fails with an error identifying the invalid input

---

### Requirement: Least-privilege permissions

The preflight workflow SHALL declare minimal permissions: `contents: write` for tag
creation and `checks: read` for querying check run conclusions. No additional permissions
SHALL be required.

#### Scenario: Permissions declared

- **WHEN** the workflow file is inspected
- **THEN** workflow-level permissions are empty
- **AND** job-level permissions grant only `contents: write` and `checks: read`

---

### Requirement: Concurrency control

The preflight workflow SHALL define a concurrency group scoped to the repository to
prevent parallel release workflows from racing through tag operations. Concurrent runs
SHALL NOT cancel in-progress releases.

#### Scenario: Sequential release execution

- **WHEN** two workflow runs start concurrently for the same or different tags
- **THEN** only one run executes at a time
- **AND** subsequent runs are queued, not cancelled

---

### Requirement: Execution timeout

The preflight workflow SHALL specify a job-level timeout appropriate for API calls and
git operations.

#### Scenario: Timeout enforced

- **WHEN** the preflight job exceeds the configured timeout
- **THEN** the workflow fails with the standard GitHub Actions timeout error

---

### Requirement: User inputs routed through env blocks

All workflow `run:` steps that reference user-controlled inputs SHALL use `env:` block
indirection rather than direct expression interpolation to prevent command injection.

#### Scenario: Tag input in run block

- **WHEN** a `run:` step uses the `tag` input value
- **THEN** the value is accessed via an environment variable set in the step's `env:`
  block
- **AND** no direct input interpolation appears inside the `run:` script body

---

### Requirement: Token routed through env blocks

All workflow `run:` steps that use `GITHUB_TOKEN` SHALL access it via an `env:` block
variable, following the same indirection pattern required for user inputs.

#### Scenario: Token in API calls

- **WHEN** a `run:` step calls `gh api` or other GitHub CLI commands
- **THEN** the token is provided via `GH_TOKEN` environment variable set in the step's
  `env:` block
- **AND** no direct `${{ secrets.GITHUB_TOKEN }}` expression appears inside the `run:`
  script body

---

### Requirement: Action references pinned to commit SHAs

All `uses:` action references in the workflow SHALL be pinned to full 40-character commit
SHAs with an inline version comment.

#### Scenario: SHA-pinned actions

- **WHEN** the workflow file is inspected
- **THEN** every `uses:` reference specifies a full commit SHA
- **AND** each SHA is accompanied by an inline comment indicating the version

