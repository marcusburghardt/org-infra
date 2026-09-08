#!/usr/bin/env bash

# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# YAML-structure assertions for tag_push_token secret
# Verifies spec scenarios against reusable_release_preflight.yml

if ! command -v yq &>/dev/null; then
	echo "ERROR: yq is required but not found"
	exit 1
fi

WORKFLOW=".github/workflows/reusable_release_preflight.yml"
FAILURES=0
TESTS=0

pass() {
	TESTS=$((TESTS + 1))
	echo "PASS: $1"
}
fail() {
	TESTS=$((TESTS + 1))
	FAILURES=$((FAILURES + 1))
	echo "FAIL: $1"
}

# Resolve path relative to repo root (support running from any directory)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOW_PATH="$REPO_ROOT/$WORKFLOW"

if [[ ! -f "$WORKFLOW_PATH" ]]; then
	echo "ERROR: Workflow file not found: $WORKFLOW_PATH"
	exit 1
fi

# ---------------------------------------------------------------------------
# 4.1 Assert secrets.tag_push_token exists with required: false
# ---------------------------------------------------------------------------

if yq '.on.workflow_call.secrets.tag_push_token' "$WORKFLOW_PATH" | grep -q -v '^null$'; then
	pass "4.1a secrets.tag_push_token is declared in the workflow"
else
	fail "4.1a secrets.tag_push_token is NOT declared in the workflow"
fi

REQUIRED=$(yq '.on.workflow_call.secrets.tag_push_token.required' "$WORKFLOW_PATH")
if [[ "$REQUIRED" == "false" ]]; then
	pass "4.1b tag_push_token has required: false"
else
	fail "4.1b tag_push_token does NOT have required: false (got: $REQUIRED)"
fi

# ---------------------------------------------------------------------------
# 4.2 Assert the fallback expression appears only in "Create and push tag"
# ---------------------------------------------------------------------------

FALLBACK_EXPR="secrets.tag_push_token != '' && secrets.tag_push_token || secrets.GITHUB_TOKEN"

# Count total occurrences of the fallback expression
FALLBACK_COUNT=$(grep -c "$FALLBACK_EXPR" "$WORKFLOW_PATH" || true)

if [[ "$FALLBACK_COUNT" -eq 1 ]]; then
	pass "4.2a fallback expression appears exactly once in the workflow"
else
	fail "4.2a fallback expression appears $FALLBACK_COUNT times (expected 1)"
fi

CREATE_TAG_ENV=$(yq '.jobs.preflight.steps[] | select(.name == "Create and push tag") | .env.GH_TOKEN' "$WORKFLOW_PATH")

if echo "$CREATE_TAG_ENV" | grep -q "$FALLBACK_EXPR"; then
	pass "4.2b fallback expression is in the 'Create and push tag' step"
else
	fail "4.2b fallback expression is NOT in the 'Create and push tag' step"
fi

# ---------------------------------------------------------------------------
# 4.3 Assert no other step references secrets.tag_push_token (negative test)
# ---------------------------------------------------------------------------

OTHER_STEPS=$(yq '.jobs.preflight.steps[] | select(.name != "Create and push tag") | .. | select(type == "string")' "$WORKFLOW_PATH" |
	grep -c 'tag_push_token' || true)

if [[ "$OTHER_STEPS" -eq 0 ]]; then
	pass "4.3 no other step references secrets.tag_push_token"
else
	fail "4.3 found $OTHER_STEPS unexpected reference(s) to secrets.tag_push_token in other steps"
fi

# ---------------------------------------------------------------------------
# 4.4 Assert description contains exact warning text
# ---------------------------------------------------------------------------

EXPECTED_DESC="Optional elevated token for tag creation. When provided, the tag event can trigger downstream workflows. WARNING: Do not use an elevated token in downstream workflows that re-invoke this preflight workflow, or you will create a recursive loop."

DESC_BLOCK=$(yq -r '.on.workflow_call.secrets.tag_push_token.description' "$WORKFLOW_PATH")

if [[ "$DESC_BLOCK" == "$EXPECTED_DESC" ]]; then
	pass "4.4 description contains exact warning text"
else
	fail "4.4 description does not match expected warning text"
	echo "  Expected: $EXPECTED_DESC"
	echo "  Got:      $DESC_BLOCK"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "========================================="
echo "Results: $((TESTS - FAILURES))/$TESTS passed"
if [[ "$FAILURES" -gt 0 ]]; then
	echo "$FAILURES FAILED"
	exit 1
else
	echo "All assertions passed"
	exit 0
fi
