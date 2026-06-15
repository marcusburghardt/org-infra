# Changelog

## Unreleased

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
