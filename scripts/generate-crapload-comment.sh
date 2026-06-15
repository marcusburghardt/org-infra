#!/usr/bin/env bash
# generate-crapload-comment.sh
# ============================
# Generates the PR comment body for CRAP load analysis results.
# Reads gaze crap JSON and gaze report JSON, writes Markdown to
# /tmp/crapload-comment-body.md.
#
# Required environment variables:
#   BASELINE       - path to baseline file (checked for existence)
#   GAZE_VERSION   - gaze version string (used in quickstart instructions)
#   STATUS         - "pass" or "fail" from the compare step
#
# Optional environment variables (for footer link):
#   GITHUB_SERVER_URL  - e.g. https://github.com
#   GITHUB_REPOSITORY  - e.g. owner/repo
#   GITHUB_RUN_ID      - numeric run ID
#
# Usage:
#   bash generate-crapload-comment.sh [CRAP_JSON] [REPORT_JSON]
#
# Arguments default to /tmp/crapload-current.json and
# /tmp/gaze-report.json when omitted.
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

CRAP_JSON="${1:-/tmp/crapload-current.json}"
REPORT_JSON="${2:-/tmp/gaze-report.json}"
COMMENT_FILE="/tmp/crapload-comment-body.md"

# Extract summary metrics from gaze crap JSON.
TOTAL_FUNCS=$(jq -r '.summary.total_functions // 0' "$CRAP_JSON")
AVG_COMPLEXITY=$(jq -r '(.summary.avg_complexity // 0) * 10 | round / 10' "$CRAP_JSON")
AVG_LINE_COV=$(jq -r '(.summary.avg_line_coverage // 0) * 10 | round / 10' "$CRAP_JSON")
AVG_CRAP=$(jq -r '(.summary.avg_crap // 0) * 10 | round / 10' "$CRAP_JSON")
CRAP_THRESH=$(jq -r '.summary.crap_threshold // 15' "$CRAP_JSON")
CRAPLOAD=$(jq -r '.summary.crapload // 0' "$CRAP_JSON")
AVG_CONTRACT_COV=$(jq -r '(.summary.avg_contract_coverage // 0) * 10 | round / 10' "$CRAP_JSON")
AVG_GAZE_CRAP=$(jq -r '(.summary.avg_gaze_crap // 0) * 10 | round / 10' "$CRAP_JSON")
GAZE_CRAP_THRESH=$(jq -r '.summary.gaze_crap_threshold // 15' "$CRAP_JSON")
GAZE_CRAPLOAD=$(jq -r '.summary.gaze_crapload // 0' "$CRAP_JSON")
REG_COUNT=$(jq -r '.comparison.regressions // 0' "$CRAP_JSON")
IMP_COUNT=$(jq -r '.comparison.improvements // 0' "$CRAP_JSON")
NEW_COUNT=$(jq -r '(.comparison.new_functions // 0) + (.comparison.new_violations // 0)' "$CRAP_JSON")

# No-baseline path: generate quickstart comment.
if [ ! -f "$BASELINE" ] || [ ! -s "$BASELINE" ]; then
	cat >"$COMMENT_FILE" <<EOF
<!-- crapload-analysis-marker -->
## &#x2705; CRAP Load Analysis: PASS (no baseline)

No baseline file found at \`${BASELINE}\`. Showing current scores without regression detection.

### How to Enable Regression Detection

Generate and commit a baseline file to track CRAP score changes over time:

\`\`\`bash
# 1. Install gaze
go install github.com/unbound-force/gaze/cmd/gaze@${GAZE_VERSION}

# 2. Run tests and generate baseline
go test -coverprofile=coverage.out ./...
mkdir -p .gaze
gaze crap --format=json --coverprofile=coverage.out ./... > .gaze/baseline.json

# 3. Commit the baseline
git add .gaze/baseline.json
git commit -m "chore: add CRAP baseline for regression detection"
\`\`\`

**For more information**:
- [Gaze README](https://github.com/unbound-force/gaze/blob/main/README.md)
- [CI Integration Guide](https://github.com/unbound-force/gaze/blob/main/docs/guides/ci-integration.md)

### Summary

| Metric | Value |
|--------|-------|
| Functions analysed | ${TOTAL_FUNCS} |
| Avg complexity | ${AVG_COMPLEXITY} |
| Avg line coverage | ${AVG_LINE_COV}% |
| Avg CRAP score | ${AVG_CRAP} |
| CRAPload (>= ${CRAP_THRESH}) | ${CRAPLOAD} |
| Avg contract coverage | ${AVG_CONTRACT_COV}% |
| Avg GazeCRAP score | ${AVG_GAZE_CRAP} |
| GazeCRAPload (>= ${GAZE_CRAP_THRESH}) | ${GAZE_CRAPLOAD} |

[View full analysis logs](${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID})
EOF
	exit 0
fi

# Baseline path: generate full comparison comment.
STATUS_BADGE="&#x2705;"
STATUS_TEXT="PASS"
if [ "$STATUS" = "fail" ]; then
	STATUS_BADGE="&#x274C;"
	STATUS_TEXT="FAIL"
fi

cat >"$COMMENT_FILE" <<EOF
<!-- crapload-analysis-marker -->
## ${STATUS_BADGE} CRAP Load Analysis: ${STATUS_TEXT}

### Summary

| Metric | Value |
|--------|-------|
| Functions analysed | ${TOTAL_FUNCS} |
| Avg complexity | ${AVG_COMPLEXITY} |
| Avg line coverage | ${AVG_LINE_COV}% |
| Avg CRAP score | ${AVG_CRAP} |
| CRAPload (>= ${CRAP_THRESH}) | ${CRAPLOAD} |
| Avg contract coverage | ${AVG_CONTRACT_COV}% |
| Avg GazeCRAP score | ${AVG_GAZE_CRAP} |
| GazeCRAPload (>= ${GAZE_CRAP_THRESH}) | ${GAZE_CRAPLOAD} |
| Regressions | ${REG_COUNT} |
| Improvements | ${IMP_COUNT} |
| New functions | ${NEW_COUNT} |
EOF

# Add quality metrics from gaze report if available.
QUALITY_COV=$(jq -r '(.quality.summary.average_contract_coverage // empty) * 10 | round / 10' "$REPORT_JSON" 2>/dev/null || true)
if [ -n "$QUALITY_COV" ]; then
	QUALITY_OVERSPEC=$(jq -r '(.quality.summary.average_over_specification // 0) * 10 | round / 10' "$REPORT_JSON" 2>/dev/null || echo "0")
	printf '| Avg contract coverage (quality) | %s%% |\n' "$QUALITY_COV" >>"$COMMENT_FILE"
	printf '| Avg over-specification | %s%% |\n' "$QUALITY_OVERSPEC" >>"$COMMENT_FILE"
fi

# Add quadrant distribution from gaze report if available.
Q1=$(jq -r '.crap.summary.quadrant_counts.Q1_Safe // empty' "$REPORT_JSON" 2>/dev/null || true)
if [ -n "$Q1" ]; then
	Q2=$(jq -r '.crap.summary.quadrant_counts.Q2_ComplexButTested // 0' "$REPORT_JSON" 2>/dev/null || echo "0")
	Q3=$(jq -r '.crap.summary.quadrant_counts.Q3_SimpleButUnderspecified // 0' "$REPORT_JSON" 2>/dev/null || echo "0")
	Q4=$(jq -r '.crap.summary.quadrant_counts.Q4_Dangerous // 0' "$REPORT_JSON" 2>/dev/null || echo "0")
	cat >>"$COMMENT_FILE" <<EOF

### Quadrant Distribution

| Quadrant | Count |
|----------|-------|
| Q1 Safe | ${Q1} |
| Q2 Complex but Tested | ${Q2} |
| Q3 Simple but Underspecified | ${Q3} |
| Q4 Dangerous | ${Q4} |
EOF
fi

# Add regressions table from gaze crap comparison JSON.
REGRESSIONS_TABLE=$(jq -r '
  [.scores[] | select(.status == "regression")] |
  if length > 0 then
    "\n### Regressions\n\n| Function | Baseline CRAP | Current CRAP | Delta | Baseline GazeCRAP | Current GazeCRAP | Delta |\n|----------|---------------|--------------|-------|-------------------|------------------|-------|\n" +
    (map("| `\(.file):\(.function)` | \(.baseline_crap // "N/A") | \(.crap) | \(.crap_delta // "N/A") | \(.baseline_gaze_crap // "N/A") | \(.gaze_crap // "N/A") | \(.gaze_crap_delta // "N/A") |") | join("\n"))
  else empty end
' "$CRAP_JSON" 2>/dev/null || true)
if [ -n "$REGRESSIONS_TABLE" ]; then
	printf '%s\n' "$REGRESSIONS_TABLE" >>"$COMMENT_FILE"
fi

# Add improvements table.
IMPROVEMENTS_TABLE=$(jq -r '
  [.scores[] | select(.status == "improvement")] |
  if length > 0 then
    "\n### Improvements\n\n| Function | Baseline CRAP | Current CRAP | Delta | Baseline GazeCRAP | Current GazeCRAP | Delta |\n|----------|---------------|--------------|-------|-------------------|------------------|-------|\n" +
    (map("| `\(.file):\(.function)` | \(.baseline_crap // "N/A") | \(.crap) | \(.crap_delta // "N/A") | \(.baseline_gaze_crap // "N/A") | \(.gaze_crap // "N/A") | \(.gaze_crap_delta // "N/A") |") | join("\n"))
  else empty end
' "$CRAP_JSON" 2>/dev/null || true)
if [ -n "$IMPROVEMENTS_TABLE" ]; then
	printf '%s\n' "$IMPROVEMENTS_TABLE" >>"$COMMENT_FILE"
fi

# Add new functions table.
NEW_FUNCS_TABLE=$(jq -r '
  .new_functions // [] |
  if length > 0 then
    "\n### New Functions\n\n| Status | Function | CRAP | GazeCRAP | Note |\n|--------|----------|------|----------|------|\n" +
    (map(
      (if .status == "new_violation" then "!+" else "+" end) as $icon |
      "| \($icon) | `\(.file):\(.function)` | \(.crap) | \(.gaze_crap // "N/A") | \(.status | gsub("_"; " ")) |"
    ) | join("\n"))
  else empty end
' "$CRAP_JSON" 2>/dev/null || true)
if [ -n "$NEW_FUNCS_TABLE" ]; then
	printf '%s\n' "$NEW_FUNCS_TABLE" >>"$COMMENT_FILE"
fi

# Add analysis warnings from gaze report if any.
FAILED_STEPS=$(jq -r '.errors | to_entries[] | select(.value != null) | "- **\(.key)**: \(.value)"' "$REPORT_JSON" 2>/dev/null || true)
if [ -n "$FAILED_STEPS" ]; then
	printf '\n### Analysis Warnings\n\n%s\n' "$FAILED_STEPS" >>"$COMMENT_FILE"
fi

# Add footer.
printf '\n[View full analysis logs](%s/%s/actions/runs/%s)\n' \
	"$GITHUB_SERVER_URL" "$GITHUB_REPOSITORY" "$GITHUB_RUN_ID" >>"$COMMENT_FILE"
