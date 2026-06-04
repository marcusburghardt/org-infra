# Proposal: org-owned-dependabot-fast-path

## Why

Every org-infra release triggers dozens of Dependabot PRs across all consumer
repositories (one per reusable workflow reference, per repo). These PRs bump
SHA-pinned references to workflows that the organization itself authored and
released. The current auto-approval pipeline treats them identically to
third-party dependencies: it requires a 24-hour release age cooling period and
does not enable auto-merge. In repositories requiring two approvals, this means
two humans must manually review each of these routine, self-authored bumps.

The 24-hour cooling period is a supply chain attack mitigation designed for
third-party dependencies where a compromised release could be consumed before
detection. For org-owned dependencies, the organization controls the release
process and the risk model is fundamentally different. Applying the same
quarantine to self-authored releases creates unnecessary friction without
meaningful security benefit.

## What Changes

- Detect org-owned dependencies by comparing the dependency owner against
  `github.repository_owner` at runtime. No configuration or allowlists.
- Skip the 24-hour release age requirement for org-owned dependencies that are
  patch or minor updates and pass dependency review.
- Enable GitHub auto-merge on the PR after auto-approval for org-owned
  dependencies, so repositories with a single required approval merge
  automatically and repositories requiring two approvals merge as soon as one
  human approves.
- Major version bumps of org-owned dependencies continue to require full manual
  review (potential breaking changes).
- Update the PR comment to surface the ownership signal and the auto-merge
  status.

## Non-goals

- Configurable trust lists or cross-org trust relationships. Ownership is
  strictly `github.repository_owner` matching the dependency's first path
  segment.
- Direct merge bypassing branch protection. Auto-merge respects all existing
  protection rules (required reviews, status checks).
- Changes to third-party dependency handling. The existing approval flow for
  non-org-owned dependencies remains unchanged.

## Capabilities

### New Capabilities

- `org-ownership-detection`: Detect whether a dependency originates from the
  same GitHub organization as the consuming repository using
  `github.repository_owner`. Output a boolean signal for downstream decision
  logic.
- `org-owned-auto-merge`: Enable GitHub auto-merge on Dependabot PRs that are
  org-owned, patch/minor, and pass dependency review. Differentiate the approval
  flow based on ownership trust level.

### Modified Capabilities

_(none — this adds new decision branches without changing existing third-party
approval logic)_

## Impact

- **Workflows**: `reusable_dependabot_reviewer.yml` (new output),
  `ci_dependencies.yml` (new approval branch, auto-merge step, updated comment
  template).
- **Permissions**: The auto-merge job in `ci_dependencies.yml` requires
  `contents: write` in addition to the existing `pull-requests: write`. This
  propagates to all consumer repos via sync.
- **Repository settings**: Repos must have "Allow auto-merge" enabled in GitHub
  settings for auto-merge to take effect. Where not enabled, the approval still
  fires but auto-merge is a no-op.
- **Sync**: `ci_dependencies.yml` changes require a sync cycle to propagate.
  `reusable_dependabot_reviewer.yml` changes take effect immediately (called
  remotely).
