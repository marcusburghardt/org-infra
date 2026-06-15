## Why

Gaze has merged native baseline comparison into `gaze crap` (PR
unbound-force/gaze#120), which subsumes the custom comparison
logic in `scripts/compare-crapload.sh` (315 lines of bash) and
its test suite `TestCompareCrapload` (203 lines of Python).
Adopting the native capability eliminates ~570 lines of maintained
code while gaining structured JSON comparison output, configurable
epsilon/threshold via `.gaze.yaml`, and upstream test coverage
(34 tests in gaze itself).

Closes #328.

## What Changes

- **DELETE** `scripts/compare-crapload.sh` -- all comparison logic
  (baseline lookup, regression detection, pass/fail, numeric
  validation) is now native to `gaze crap --baseline`
- **MODIFY** `reusable_crapload_analysis.yml` -- replace the
  two-step pipeline (gaze report + compare-crapload.sh) with a
  single `gaze crap --baseline` invocation for comparison; keep
  `gaze report` for supplementary quality/quadrant data; generate
  PR comment markdown inline via jq + heredoc
- **MODIFY** `tests/test_crapload_package_resolution.py` -- remove
  `TestCompareCrapload` class (5 tests, ~203 lines); keep
  `TestCrapLoadPackageResolution` and `TestWorkflowInputValidation`
- **MODIFY** `ci_test_crapload.yml` -- remove
  `scripts/compare-crapload.sh` from path triggers
- **UPDATE** `specs/001-crapload-workflow/quickstart.md` -- update
  baseline generation instructions to use `gaze crap`; fix stale
  `post-comment` input reference
- **UPDATE** `specs/001-crapload-workflow/data-model.md` -- remove
  `baseline-lookup.tsv` from intermediate artifacts; fix stale
  `post-comment` input reference

## Non-goals

- Changing the consumer workflow interface (`ci_crapload.yml`
  outputs or `post-comment` job) -- the artifact-based contract
  is preserved
- Removing `scripts/resolve-go-packages.sh` -- package resolution
  is orthogonal; the sparse checkout step remains for it
- Adding `.gaze.yaml` to org-infra itself -- this repo has no Go
  code to analyze
- Changing the PR comment visual format substantially -- content
  parity is the goal, not a redesign
- Removing `new-function-threshold` and `regression-epsilon`
  workflow inputs -- kept for backward compatibility

## Capabilities

### New Capabilities

None -- this is a refactoring, not a new feature.

### Modified Capabilities

None at the OpenSpec spec level. The `crapload-analysis` workflow
capability is defined in `specs/001-crapload-workflow/` (SpecKit),
and its external interface (inputs, outputs, artifact contract) is
preserved. Only internal implementation changes.

## Impact

- **Workflow consumers**: All Go repos consuming `ci_crapload.yml`
  via sync-config.yml. The reusable workflow interface is preserved
  so consumers are unaffected.
- **Gaze version dependency**: Consumer repos MUST use a gaze
  version that includes `--baseline` support. The `gaze-version`
  input should specify a minimum version during transition.
- **PR comment format**: Minor visual changes since the comment is
  generated from `gaze crap` JSON rather than the bespoke bash
  script. Content is equivalent.
- **Test coverage**: 5 tests removed from org-infra; 34 tests in
  gaze upstream cover the same comparison logic.
