## Why

Every Go project in the ComplyTime and Unbound Force organizations maintains its own
release workflow with inline preflight validation, GoReleaser execution, and supply chain
steps. Analysis of 7 repositories reveals significant duplication, inconsistent supply
chain coverage (3 of 7 repos lack SBOMs and cosign signing), action version drift across
repos, hardcoded CI check names that break silently when workflows are renamed, and two
functional bugs in the newest preflight implementation (re-run blocking and `sort -V`
pre-release ordering inversion -- complytime/complyctl#654).

The constitution mandates that workflows SHOULD be centralized in org-infra
(Infrastructure Standards Centralization). Every other CI concern (linting, security
scanning, dependency review, compliance) already follows this pattern via `reusable_*`
workflows. The release pipeline is the last major standalone workflow.

Container-only repos already benefit from centralized reusable workflows
(`reusable_publish_ghcr.yml`, `reusable_trivy_image_scan.yml`,
`reusable_sign_and_verify.yml`), but they lack the preflight validation gate that binary
release repos have developed. Standardizing the preflight across all release types
ensures consistent quality gates regardless of artifact type.

Closes complytime/complyctl#655 (org-infra reusable release workflow follow-up).
Addresses complytime/complyctl#654 (re-run blocking and pre-release ordering bugs).

## What Changes

- **New `reusable_release_preflight.yml` workflow** in org-infra providing universal
  release preflight validation: tag format validation (with configurable pre-release
  support), smart tag uniqueness with re-run resilience, semver-aware ordering
  verification (fixing the `sort -V` pre-release inversion), automatic CI check
  discovery from workflow files (`ci_local.yml`, `ci_checks.yml`, `ci_security.yml`),
  security scan gate, unreleased commits verification, and idempotent annotated tag
  creation.
- **New `reusable_release_goreleaser.yml` workflow** in org-infra providing standardized
  GoReleaser execution with enforced supply chain: Go version always read from `go.mod`,
  cosign and syft always installed, standardized action versions (single source of
  truth), and consistent build environment.
- **New `docs/RELEASE_WORKFLOWS.md` adoption guide** with per-repo-type migration
  instructions (CLI/binary, container service, library, hybrid), consumer workflow
  templates, GoReleaser configuration standards for supply chain sections, CI check
  auto-discovery explanation, migration checklist, and troubleshooting guide.
- **Proper API error handling** in CI check verification: replaces the `2>/dev/null`
  pattern (which masks rate limits and network errors) with separated API calls and
  explicit error surfacing.
- **Paginated check-runs queries** to handle repos with more than 30 CI check runs.
- **New `docs/RELEASE_PROCESS.md` operational runbook** providing a generic, org-wide
  release process document covering the standard release flow (trigger, preflight,
  build, verification), release cadence guidance, failure recovery procedures, and
  supply chain expectations. This serves as the canonical reference that each repository
  can extend locally with repo-specific procedures (e.g., Fedora packaging, Homebrew tap
  publishing, container promotion). Inspired by complyctl's existing
  `docs/RELEASE_PROCESS.md` but generalized to be repository-agnostic.

## Non-goals

- **macOS code signing and notarization**: The Unbound Force repos have Apple Developer
  ID signing and Homebrew tap publishing. This remains in each UF repo and is out of
  scope for the centralized workflows.
- **GoReleaser configuration templating**: The `.goreleaser.yaml` file stays in each
  repo, fully owned by maintainers. The adoption guide documents the required supply
  chain sections but does not enforce them programmatically.
- **Reusable GitHub Release workflow for non-GoReleaser repos**: Container-only and
  library repos that need a GitHub Release without binary builds may benefit from a
  `reusable_release_github.yml` in the future, but it is out of scope for this change.
- **Automated migration of existing release workflows**: Repos adopt the new reusable
  workflows at their own pace. This change provides the infrastructure and documentation
  but does not modify any consuming repository.
- **Syncing release workflows via `sync-config.yml`**: The reusable workflows are
  consumed via cross-repo `uses:` references (e.g.,
  `complytime/org-infra/.github/workflows/reusable_release_preflight.yml@v1`), consistent
  with how all existing reusable workflows are consumed.

## Capabilities

### New Capabilities

- `release-preflight`: Universal release preflight validation gate with tag format
  validation, smart re-run resilience, semver-aware ordering (including pre-release
  tags), file-based CI check auto-discovery, security scan gate, and idempotent tag
  creation.
- `release-goreleaser`: Standardized GoReleaser execution with enforced supply chain
  (cosign signing, syft SBOMs), Go version from `go.mod`, and centralized action version
  management.
- `release-adoption`: Adoption documentation covering per-repo-type migration
  instructions, consumer workflow templates, GoReleaser configuration standards,
  migration checklist, and troubleshooting.
- `release-process`: Generic release process runbook covering the standard release flow,
  cadence guidance, failure recovery, supply chain expectations, and extension points
  for repo-specific procedures.

### Modified Capabilities

(none -- existing reusable workflows are unchanged)

## Impact

- **New files in org-infra**:
  - `.github/workflows/reusable_release_preflight.yml`
  - `.github/workflows/reusable_release_goreleaser.yml`
  - `docs/RELEASE_WORKFLOWS.md`
  - `docs/RELEASE_PROCESS.md`
- **Downstream repos** (no changes in this PR, but enables future adoption):
  - complyctl, complytime-providers, complypack, complybeacon,
    gemara-content-service, compliance-to-policy-go, oscal-sdk-go (ComplyTime org)
  - uf-gaze, uf-dewey, uf-unbound-force, uf-replicator (Unbound Force org)
- **Dependencies**: No new external dependencies. Uses the same GitHub Actions already in
  use across the org (actions/checkout, actions/setup-go, sigstore/cosign-installer,
  anchore/sbom-action, goreleaser/goreleaser-action).
- **Permissions**: The preflight workflow requires `contents: write` (tag creation) and
  `checks: read` (verify check conclusions). The GoReleaser workflow requires
  `contents: write` (GitHub Release) and `id-token: write` (Sigstore OIDC). These match
  existing permission patterns in current release workflows.
