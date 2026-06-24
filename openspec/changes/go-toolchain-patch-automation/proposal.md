## Why

Go patch releases that fix security vulnerabilities (CVEs) are reported on
GitHub's security tab for all Go repositories in the organization (via
OSV-Scanner), but no automation exists to create PRs bumping the `toolchain`
directive in `go.mod`. Dependabot's `gomod` ecosystem manages third-party
module dependencies but does **not** support bumping the `go` or `toolchain`
directives ([dependabot-core#13520](https://github.com/dependabot/dependabot-core/issues/13520),
open since Nov 2025, no assignee or milestone).

A custom workflow (`vuln_check_fix.yml`) previously existed in complyctl
(PR #314, Oct 2025) and successfully created an automated bump PR (#332,
Nov 2025). It was removed during the org-infra workflow sync migration
(PR #335, Nov 2025) under the assumption that Dependabot or org-infra
reusable workflows would cover this gap. They do not. Manual Go version
bumps continue to this day (e.g., org-infra commit `ac385c6`, Jun 2026).

## What Changes

- Deploy [Renovate](https://github.com/renovatebot/renovate) via
  `renovatebot/github-action`, running as a centralized scheduled
  workflow in org-infra. Renovate's `gomod` manager natively supports
  the `toolchain` depType with patch-only filtering.
- Create a dedicated GitHub App (`complytime-renovate[bot]`) with
  minimal permissions (`contents:write`, `pull-requests:write`),
  installed on the 4 Go repositories. The App token ensures PRs
  trigger CI automatically (unlike `GITHUB_TOKEN`).
- Define a shared Renovate preset in org-infra
  (`go-toolchain-patches.json`) applied to all managed repos via
  `globalExtends`. Consumer repos require zero configuration files.
- Only patch versions are bumped automatically (e.g., 1.25.9 to
  1.25.11). Minor and major version decisions remain with maintainers.

## Alternatives Considered

### Custom Reusable Workflow

A focused reusable workflow in org-infra that queries `go.dev/dl/`
for the latest patch release, updates `go.mod`, and creates a PR
via `peter-evans/create-pull-request`. Integrated into the existing
`ci_scheduled.yml` via per-repo variable substitution in
`sync-config.yml`.

**Why not chosen:**
- **Custom logic to maintain**: ~60 lines of shell for version
  detection, `go.mod` editing, vendor handling, and PR creation.
  Renovate handles all of this natively with declarative config.
- **GITHUB_TOKEN limitation**: PRs created with `GITHUB_TOKEN` do
  not trigger `pull_request` events, requiring maintainers to
  close/reopen PRs to trigger CI. Solving this requires a GitHub
  App token regardless -- at which point Renovate's built-in PR
  management offers more value than custom shell scripts.
- **Extensibility**: Each new Dependabot gap (base images, Helm
  charts, cross-repo version pins) would require a new custom
  workflow. Renovate covers these with config changes.

**Custom workflow strengths:**
- Zero new tool dependencies (only `peter-evans/create-pull-request`)
- Follows existing org-infra patterns (reusable workflows,
  sync-config variable substitution)
- Simpler mental model for a single-purpose automation

### Renovate Hosted App (Mend)

Install the official Mend-hosted Renovate GitHub App
(`github.com/apps/renovate`). Zero infrastructure to manage.

**Why not chosen:**
- **Broad permissions**: The hosted app requests 8 permission types
  including `Workflows: Read & Write` and `Dependabot secrets: Read`.
  These permissions cannot be scoped down -- GitHub Apps have a fixed
  permission set defined by the app developer.
- **Workflows write risk**: Allows the app to modify
  `.github/workflows/*.yml` files. Since App-created PRs trigger CI
  with full secret access, a compromised app could exfiltrate
  secrets (QUAY_PASSWORD, SYNC_APP_PRIVATE_KEY, OIDC tokens) via
  injected workflow steps -- before any human reviews the PR.
- **Inconsistent with org posture**: The org already creates
  purpose-built apps with minimal permissions (e.g.,
  `complytime-repo-sync[bot]` with only `contents:write` +
  `pull-requests:write`). Installing a third-party app with broad
  permissions would be a step backward.

### Updatecli

[Updatecli](https://github.com/updatecli/updatecli) (Apache-2.0, 933
stars) is a declarative update policy engine with a `golang/gomod`
plugin that can read/write `go.mod`. It runs as a CLI in GitHub
Actions with minimal permissions.

**Why not chosen:**
- **Smaller community**: 933 stars, 134 forks, primarily
  maintainer-driven. Code-Review scored 1/10 on OpenSSF Scorecard
  (only 2/11 changesets reviewed). Branch-Protection scored 3/10
  (does not require approvers on main).
- **New tool dependency**: Introduces a new action, a new policy
  language (YAML manifests), and a new binary. The `golang/gomod`
  plugin does not handle vendoring natively.
- **Overhead vs. value**: Updatecli's declarative engine adds
  abstraction without proportional benefit compared to Renovate,
  which has broader community adoption and native Go toolchain
  support.

**Updatecli strengths (for future reference):**
- Apache-2.0 license (same as org repos)
- OpenSSF Scorecard 7.5/10 (higher than Renovate)
- Signed releases with Cosign/Sigstore
- Token-Permissions scored 10/10

## Non-goals

- Bumping Go minor or major versions (maintainer decision).
- Replacing Dependabot for Go module dependency management.
- Adopting Renovate organization-wide for all dependency types
  (scoped to Go toolchain patches only; Dependabot continues to
  manage module dependencies and GitHub Actions pins).
- Detecting whether a patch release contains a specific CVE fix
  (all patches within the current minor series are applied; Go
  patch releases are exclusively bug and security fixes).
- Using the Mend-hosted Renovate App (dedicated GitHub App with
  minimal permissions instead).

## Capabilities

### New Capabilities

- `renovate-runner`: Centralized Renovate workflow in org-infra
  (`ci_renovate.yml`) that runs on a daily schedule and manages Go
  toolchain patch updates across all configured repositories. Uses
  a dedicated GitHub App for authentication. Generates a JSON run
  report uploaded as a GitHub Actions artifact.
- `renovate-preset`: Shared Renovate preset
  (`go-toolchain-patches.json`) that restricts Renovate to only
  `gomod` manager, `toolchain` depType, `patch` updateType using
  a three-rule pattern with `separateMinorPatch`. Applied via
  `globalExtends` -- consumer repos need no local config.

### Modified Capabilities

None. Unlike the custom workflow approach, this change does not
modify `ci_scheduled.yml` or `sync-config.yml`.

## Impact

- **New workflow**: `ci_renovate.yml` added to
  `.github/workflows/` in org-infra only (not synced).
- **New config files**: `go-toolchain-patches.json` and
  `renovate-config.js` added to org-infra repo root.
- **GitHub App**: New `complytime-renovate[bot]` app created in
  org settings with `contents:write` and `pull-requests:write`.
  Installed on complyctl, complytime, complytime-providers,
  complytime-collector-components.
- **Secrets**: `RENOVATE_APP_CLIENT_ID` and
  `RENOVATE_APP_PRIVATE_KEY` added to org-infra repository secrets.
- **Consumer repos**: Zero changes required. No files synced, no
  config needed. Renovate operates via the centralized runner.
- **Third-party actions**: Adds `renovatebot/github-action`
  (SHA-pinned) and `actions/create-github-app-token` (SHA-pinned,
  already used in `sync_org_repositories.yml`) as dependencies.
- **Existing workflows**: No modifications to `ci_scheduled.yml`,
  `sync-config.yml`, or any other existing workflow.
