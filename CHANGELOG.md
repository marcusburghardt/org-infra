# Changelog

## Unreleased

### Added

- **SECURITY.md sync**: Added `SECURITY.md` to `sync-config.yml` for
  org-wide security policy distribution. Each synced repository receives a
  stub with the security contact email (`complytime-security@redhat.com`),
  GitHub Private Vulnerability Reporting instructions, and a link to the
  canonical policy in `community/SECURITY.md`. The `community` repository
  is excluded from sync (it holds the canonical policy). This ensures OSPS
  Baseline Level 1 compliance (OSPS-VM-02.01) across all org repositories.

### Changed

- **crapload workflow**: Replaced custom `scripts/compare-crapload.sh`
  (315 lines) with gaze's native `gaze crap --baseline` comparison.
  The workflow now writes a temporary `.gaze.yaml` from workflow inputs
  when the consumer repo has no config file, preserving backward
  compatibility. PR comment generation is inline via jq. (#328)

### Removed

- `scripts/compare-crapload.sh` — comparison logic is now native to gaze
- `TestCompareCrapload` test class (5 tests, 203 lines) — covered by
  34 upstream tests in gaze
