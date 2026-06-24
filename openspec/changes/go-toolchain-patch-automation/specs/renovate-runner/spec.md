## ADDED Requirements

### Requirement: Centralized Renovate runner workflow

The org-infra repository SHALL contain a scheduled workflow
(`ci_renovate.yml`) that runs Renovate via
`renovatebot/github-action` to manage Go toolchain patch updates
across configured repositories.

#### Scenario: Daily scheduled execution

- **WHEN** the daily cron schedule triggers
- **THEN** the workflow SHALL generate a GitHub App token and run
  Renovate against all repositories listed in `renovate-config.js`

#### Scenario: Manual dispatch

- **WHEN** a maintainer triggers the workflow via `workflow_dispatch`
- **THEN** the workflow SHALL support a `dry_run` string choice input
  with values `"full"` (simulate PR creation without side effects),
  `"lookup"` (discover updates only), or `"none"` (normal operation)

#### Scenario: Workflow permissions

- **WHEN** the workflow executes
- **THEN** the workflow-level permissions SHALL be set to
  `contents: read` (required for `actions/checkout` to clone
  org-infra) and the GitHub App token (not `GITHUB_TOKEN`) SHALL
  be used for all Renovate operations on consumer repos

### Requirement: Shared Renovate preset

The org-infra repository SHALL contain a shared Renovate preset
(`go-toolchain-patches.json`) that restricts Renovate to Go
toolchain patch updates only.

#### Scenario: Preset configuration

- **GIVEN** the shared preset
- **THEN** it SHALL use a three-rule package rule pattern:
  (1) disable all gomod depTypes by default,
  (2) re-enable `toolchain` depType with `separateMinorPatch: true`
  to allow independent version lookup for patch and minor updates,
  (3) disable `toolchain` updates with `matchUpdateTypes:
  ["minor", "major"]`. This avoids the chicken-and-egg problem
  where `matchUpdateTypes` requires a version lookup that only
  runs for enabled deps.

#### Scenario: Post-update options

- **GIVEN** the shared preset
- **THEN** it SHALL include `postUpdateOptions: ["gomodTidy",
  "gomodVendor"]` to handle both standard and vendored Go modules
  (`complyctl` and `complytime-providers` use vendoring)

#### Scenario: Dependency Dashboard disabled

- **GIVEN** the shared preset
- **THEN** it SHALL set `dependencyDashboard: false` to suppress
  the per-repo Dashboard issue, which adds noise for a single
  narrow dependency type

#### Scenario: PR metadata

- **GIVEN** the shared preset
- **THEN** PRs created by Renovate SHALL use conventional commit
  prefixes (`chore(deps):`) and include the `dependencies` label

### Requirement: Run report artifact

Each workflow run SHALL generate a JSON report and upload it as
a GitHub Actions artifact for observability.

#### Scenario: Report generation

- **WHEN** the Renovate step completes (success or failure)
- **THEN** the workflow SHALL upload `/tmp/renovate-report.json` as
  a `renovate-report` artifact with 30-day retention. The report
  contains dependency versions, update proposals, and branch/PR
  decisions with no sensitive data (no tokens, secrets, or
  credentials).

### Requirement: Global configuration

The org-infra repository SHALL contain a `renovate-config.js` file
that configures the self-hosted Renovate instance.

#### Scenario: Explicit repository list

- **GIVEN** the global configuration
- **THEN** it SHALL list target repositories explicitly in a
  `repositories` array rather than using autodiscovery

#### Scenario: Preset enforcement

- **GIVEN** the global configuration
- **THEN** it SHALL use `globalExtends` to apply the shared preset
  to all target repos without requiring a local `renovate.json`

#### Scenario: Onboarding disabled

- **GIVEN** the global configuration
- **THEN** it SHALL set `onboarding: false` and
  `requireConfig: 'optional'` so consumer repos need no Renovate
  artifacts

### Requirement: Dedicated GitHub App

A dedicated GitHub App (`complytime-renovate[bot]`) SHALL be created
with minimal permissions for Renovate authentication.

#### Scenario: App permissions

- **GIVEN** the GitHub App
- **THEN** it SHALL request only `contents: write` and
  `pull-requests: write` repository permissions

#### Scenario: App installation scope

- **GIVEN** the GitHub App
- **THEN** it SHALL be installed only on the Go repositories that
  require toolchain updates (complyctl, complytime,
  complytime-providers, complytime-collector-components). The App
  does not need to be installed on org-infra --
  `actions/create-github-app-token` generates tokens scoped to
  repos where the App is installed, and `globalExtends` fetches
  the preset via public GitHub API

#### Scenario: Secrets storage

- **GIVEN** the GitHub App credentials
- **THEN** `RENOVATE_APP_CLIENT_ID` and `RENOVATE_APP_PRIVATE_KEY`
  SHALL be stored as repository secrets in org-infra only, not as
  org-level secrets

### Requirement: Graceful failure handling

The Renovate runner workflow SHALL fail visibly and recover
automatically via the daily schedule. Individual failures SHALL
NOT affect other target repositories.

#### Scenario: App token generation failure

- **WHEN** `RENOVATE_APP_CLIENT_ID` or `RENOVATE_APP_PRIVATE_KEY`
  is missing, expired, or the App installation is revoked
- **THEN** the `actions/create-github-app-token` step SHALL fail
  with a non-zero exit code and the workflow run SHALL be marked
  as failed in GitHub Actions

#### Scenario: Renovate runtime failure

- **WHEN** Renovate encounters a network error, GitHub API rate
  limit, or internal error while processing a target repository
- **THEN** Renovate SHALL log the error and continue processing
  remaining repositories. The workflow exit code SHALL reflect
  whether any repository failed.

#### Scenario: Target repository inaccessible

- **WHEN** a repository listed in `renovate-config.js` is
  archived, deleted, or the App is not installed on it
- **THEN** Renovate SHALL log an error for that repository and
  continue processing remaining repositories

#### Scenario: Post-update failure

- **WHEN** `go mod tidy` or `go mod vendor` fails during a
  toolchain update (e.g., upstream module unavailability)
- **THEN** Renovate SHALL not create a PR for that repository and
  SHALL log the failure. The next scheduled run SHALL retry.

#### Scenario: Automatic recovery

- **WHEN** a workflow run fails for any reason
- **THEN** the daily cron schedule SHALL automatically retry on
  the next run without manual intervention
