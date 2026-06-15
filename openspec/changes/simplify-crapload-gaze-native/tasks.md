# Tasks

## T1: Delete `scripts/compare-crapload.sh`
- [ ] Remove the file entirely (315 lines)
- Files: `scripts/compare-crapload.sh`

## T2: Modify `reusable_crapload_analysis.yml`
- [ ] Add step to write temporary `.gaze.yaml` from workflow inputs
      (only when consumer repo has no `.gaze.yaml`)
- [ ] Keep "Run Gaze analysis" step (gaze report) for quality data
- [ ] Remove jq path normalization (gaze emits relative paths)
- [ ] Replace "Compare against baseline" step with gaze crap
      --baseline invocation and inline jq output extraction
- [ ] Handle no-baseline case: generate quickstart comment inline
- [ ] Build PR comment body inline via jq + heredoc
- [ ] Preserve `<!-- crapload-analysis-marker -->` in comment body
- [ ] Verify all 5 workflow outputs are correctly emitted
- Files: `.github/workflows/reusable_crapload_analysis.yml`

## T3: Modify `tests/test_crapload_package_resolution.py`
- [ ] Delete `TestCompareCrapload` class (lines 273-475, 5 tests)
- [ ] Delete `_MINIMAL_SUMMARY` constant if only used by that class
- [ ] Keep `TestCrapLoadPackageResolution` and
      `TestWorkflowInputValidation` unchanged
- Files: `tests/test_crapload_package_resolution.py`

## T4: Modify `ci_test_crapload.yml`
- [ ] Remove `scripts/compare-crapload.sh` from `pull_request.paths`
- [ ] Remove `scripts/compare-crapload.sh` from `push.paths`
- Files: `.github/workflows/ci_test_crapload.yml`

## T5: Update `specs/001-crapload-workflow/quickstart.md`
- [ ] Update baseline generation instructions to use `gaze crap`
- [ ] Remove stale `post-comment: false` input reference
- Files: `specs/001-crapload-workflow/quickstart.md`

## T6: Update `specs/001-crapload-workflow/data-model.md`
- [ ] Remove `baseline-lookup.tsv` from Intermediate Artifacts
- [ ] Remove stale `post-comment` input from Workflow Inputs table
- [ ] Update `crapload-current.json` description to reference
      `gaze crap` output
- Files: `specs/001-crapload-workflow/data-model.md`

## T7: Documentation gate
- [ ] Add entry to `CHANGELOG.md`
- [ ] Verify `AGENTS.md` needs no updates
- Files: `CHANGELOG.md`, `AGENTS.md`

## T8: Validation
- [ ] Run `make lint` (yamllint + ruff)
- [ ] Run `make test` (pytest -- verify remaining tests pass)
- [ ] Run `/review-council` before PR submission
