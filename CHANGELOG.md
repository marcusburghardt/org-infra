# Changelog

## Unreleased

### Added

- **Project board review-status advance**: The Compliance Automation
  planning board sync moves items from Ready for Review to In Review when
  a non-author human comments or submits a PR review after the Status
  change. See `docs/PROJECT_BOARD_SYNC.md`.

- **Epic issue template**: Added `.github/ISSUE_TEMPLATE/epic.yml` for
  parent issues that group a set of user stories. Size and sprint live
  on the child stories, not the epic. Synced to org repos via
  `sync-config.yml`.

- **Sprint velocity report**: Manual workflow that counts Done issues per
  completed Iteration on the Compliance Automation planning board, then
  averages those counts (including by Size, Organization, and Milestone).
  The open sprint is listed separately and is not in the mean. Board sync
  and this report share `scripts/lib/github_client.py`. See
  `docs/SPRINT_VELOCITY.md`.

- **Stale review alerts**: Added `reusable_stale_reviews.yml` and
  `ci_stale_reviews.yml` to detect and flag PRs with review requests
  pending beyond a configurable business-day threshold. Applies a
  `stale-review` label and posts a reminder comment @-mentioning
  assigned reviewers. Synced to org repos via `sync-config.yml` with
  staged rollout (org-infra first). (#478)

- **SECURITY.md sync**: Added `SECURITY.md` to `sync-config.yml` for
  org-wide security policy distribution. Each synced repository receives a
  stub with the security contact email (`complytime-security@redhat.com`),
  GitHub Private Vulnerability Reporting instructions, and a link to the
  canonical policy in `community/SECURITY.md`. The `community` repository
  is excluded from sync (it holds the canonical policy). This ensures OSPS
  Baseline Level 1 compliance (OSPS-VM-02.01) across all org repositories.

### Changed

- **Constitution**: v1.3.0 documents the org-infra-only workflow naming
  convention (`sync_` / `report_` prefixes).

- **Project board sync**: Harden copying Priority / Review priority from
  linked issues: keep the highest rank when an issue appears twice on the
  board, warn when closing-issue refs are truncated, and log unmapped
  option names. (#536)

- **Project board sync**: Run the Compliance Automation planning board
  sync every 5 minutes instead of once daily. GitHub Actions does not
  honor a 1-minute cron; 5 minutes is the documented minimum. Concurrent
  runs are serialized so ticks do not pile up.

- **crapload workflow**: Replaced custom `scripts/compare-crapload.sh`
  (315 lines) with gaze's native `gaze crap --baseline` comparison.
  The workflow now writes a temporary `.gaze.yaml` from workflow inputs
  when the consumer repo has no config file, preserving backward
  compatibility. PR comment generation is inline via jq. (#328)

### Fixed

- **Vulnerability scan**: Prevent OSV scan failures when JSON results exceed
  GitHub's 1 MiB job-output limit by explicitly disabling result exports.
  Complete reports remain available as workflow artifacts. (#574)

### Removed

- `scripts/compare-crapload.sh` — comparison logic is now native to gaze
- `TestCompareCrapload` test class (5 tests, 203 lines) — covered by
  34 upstream tests in gaze
