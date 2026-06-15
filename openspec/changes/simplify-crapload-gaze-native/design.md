## Approach

Replace the two-step gaze pipeline (gaze report + compare-crapload.sh)
with `gaze crap --baseline` for comparison, while keeping `gaze report`
for supplementary quality metrics and quadrant data in the PR comment.

## Design Decisions

### D1: Keep `gaze report` for supplementary data

The current PR comment includes quality metrics (contract coverage,
over-specification) and quadrant distribution (Q1-Q4) from
`gaze report` output. `gaze crap` does not include these fields.

**Decision**: Keep `gaze report` as a supplementary step. Use
`gaze crap --baseline` for comparison and pass/fail determination.

### D2: Keep workflow inputs, write temporary .gaze.yaml

`new-function-threshold` and `regression-epsilon` are configurable
via `.gaze.yaml` in gaze native, but have no CLI flags. The workflow
inputs cannot be passed directly.

**Decision**: Keep the workflow inputs. Before running `gaze crap`,
the workflow writes a temporary `.gaze.yaml` with the input values
(only if the consumer repo does not already have one). This preserves
backward compatibility while allowing consumer repos to migrate to
their own `.gaze.yaml` at their own pace.

```yaml
# Written by workflow when no .gaze.yaml exists
baseline:
  epsilon: ${{ inputs.regression-epsilon }}
  new_function_threshold: ${{ inputs.new-function-threshold }}
```

If a `.gaze.yaml` already exists in the consumer repo, the workflow
respects it and does not overwrite -- the repo's config takes
precedence over the workflow inputs.

### D3: PR comment generation moves inline

The ~120-line comment body generation from `compare-crapload.sh`
moves to an inline step in the workflow. The comment is built from:
- `gaze crap --format=json` output (comparison section, scores)
- `gaze report --format=json` output (quality, quadrant data)

**Decision**: Use `jq` + heredoc to construct the markdown comment
body at `/tmp/crapload-comment-body.md`. This preserves the artifact
contract with `ci_crapload.yml`'s `post-comment` job.

### D4: No-baseline quickstart comment preserved

When no baseline exists, gaze exits 0 with no comparison data.
The current helpful onboarding comment must be preserved.

**Decision**: Detect the no-baseline case by checking whether
the baseline file exists before running `gaze crap`. If absent,
generate the quickstart comment inline and skip comparison.

### D5: Sparse checkout unchanged

The sparse checkout of org-infra scripts is still needed for
`resolve-go-packages.sh`. Deleting `compare-crapload.sh` simply
means it will not be present in the checkout.

**Decision**: Keep the sparse checkout step as-is.

### D6: Workflow outputs preserved

The reusable workflow exposes 5 outputs consumed by the `post-comment`
job and potentially by other workflows:
- `status` (pass/fail)
- `crapload-count`
- `gaze-crapload-count`
- `regressions-count`
- `improvements-count`

**Decision**: Extract these from `gaze crap --format=json` output
via `jq` and emit them as step outputs. The output names and
semantics are preserved.

## Data Flow (After)

```text
Consumer repo checkout
       |
       v
[Write .gaze.yaml if absent] -- from workflow inputs
       |
       v
go test -coverprofile=coverage.out
       |
       v
gaze report --format=json --> /tmp/gaze-report.json (quality, quadrant)
       |
       v
gaze crap --baseline --format=json --coverprofile=coverage.out
       |-> JSON output with comparison section
       |-> jq extracts: status, counts, scores
       |-> jq + heredoc builds /tmp/crapload-comment-body.md
       |-> outputs emitted to $GITHUB_OUTPUT
       |
       v
Upload artifacts (comment body + detailed JSON)
       |
       v
Enforce threshold (exit 1 if fail)
```

## Step Mapping (Before -> After)

| Before | After |
|--------|-------|
| Step 10: Run Gaze analysis (gaze report) | Kept: gaze report for quality/quadrant data |
| Step 11: Compare against baseline (compare-crapload.sh) | Replaced: gaze crap --baseline + inline jq/heredoc |
| Step 12: Write step summary | Kept unchanged |
| Step 13: Upload analysis artifact | Kept unchanged |
| Step 14: Upload detailed analysis | Kept unchanged |
| Step 15: Enforce threshold | Kept unchanged |
