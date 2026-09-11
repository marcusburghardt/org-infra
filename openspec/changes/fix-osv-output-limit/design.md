## Context

See `proposal.md` for motivation. The reusable vulnerability scan delegates OSV pull-request scanning to Google's pinned reusable workflow. The currently pinned upstream version supports an `export-results` input whose default is false, still uploads old and new JSON reports as artifacts, and independently controls SARIF upload and vulnerability failure behavior.

Relying only on the upstream default leaves the organization vulnerable to a future default change. Because output size is evaluated inside the called workflow, the caller cannot recover after oversized reports have been exported.

## Goals / Non-Goals

**Goals:**

- Make suppression of complete JSON job outputs explicit at the org-infra integration boundary.
- Preserve the existing upstream artifact, SARIF, and vulnerability enforcement behavior.
- Add automated validation that prevents removal or reversal of the result-export setting.

**Non-Goals:**

- Forking or reproducing Google's OSV pull-request scan workflow.
- Adding downstream summary outputs without an identified consumer.
- Changing report retention, scanner arguments, or vulnerability policy.

## Decisions

### Explicitly disable upstream result exports

Pass `export-results: false` to the pinned upstream reusable workflow. This uses the upstream control designed for the output-limit condition, documents the required behavior at the call site, and protects against upstream default changes.

Alternatives considered:

- Rely on the current upstream default. Rejected because the safety property would be implicit and could regress when updating the pin.
- Reimplement the upstream workflow locally. Rejected because it duplicates checkout, scanning, reporting, artifact, and SARIF logic, increasing maintenance and divergence risk.
- Truncate or compress JSON before export. Rejected because complete reports remain available as artifacts and no current downstream consumer requires report outputs.

### Validate configuration rather than manufacture a 1 MiB runtime payload

Add a static regression assertion that the OSV reusable-workflow call explicitly disables result exports while preserving artifact-producing integration and existing security inputs. Use the documented failing run as operational evidence for the platform boundary.

Alternatives considered:

- Generate oversized OSV results in a live GitHub Actions test. Rejected because it is slow, dependent on external scanner behavior, and difficult to reproduce deterministically in local CI.
- Omit regression coverage and rely on review. Rejected because a future dependency update could silently remove the explicit protection.

### Do not add summary outputs without demand

Keep the reusable workflow output surface unchanged. If a consumer later requires vulnerability counts or a boolean, specify and implement those outputs under a dedicated change.

Alternatives considered:

- Add counts preemptively. Rejected because there is no identified consumer and additional output parsing expands scope.

## Risks / Trade-offs

- [The upstream workflow could rename or remove `export-results`] -> Pin upstream revisions and let workflow validation or GitHub invocation checks expose an incompatible update.
- [Static validation does not execute GitHub's output evaluator] -> Assert the exact upstream control that prevents report export and retain the linked failure as documented reproduction evidence.
- [A downstream consumer may have relied on complete report outputs] -> The current org-infra wrapper does not expose those outputs; retain complete reports as artifacts for diagnostics.

## Migration Plan

1. Add the explicit upstream input and regression assertion in org-infra.
2. Run repository lint and tests, then validate the workflow through the existing CI path.
3. Publish an org-infra release containing the updated reusable workflow, then
   synchronize the consumer workflow references through the normal rollout process.
4. Roll back by reverting the explicit input and test if the pinned upstream workflow rejects the input; do not enable complete report exports as a workaround.

## Validation Evidence

The downstream failure in issue #574 provides an oversized-report reproduction: its old and new JSON artifacts were approximately 262.8 KB each, with a combined UTF-16 output estimate of 1,051,004 bytes exceeding GitHub's 1,048,576-byte limit. Both JSON artifacts and SARIF uploaded before GitHub failed final job-output evaluation.

The pinned upstream workflow gates only its `$GITHUB_OUTPUT` writes with `export-results`; JSON artifact uploads and SARIF publication are independent steps. The regression tests therefore verify that org-infra explicitly disables result exports while retaining the pinned artifact-producing integration, SARIF and failure-policy inputs, and permissions. A successful live GitHub run remains a post-push CI confirmation rather than a prerequisite for completing local implementation.

Mandatory validation also exposed two pre-existing `yq` compatibility failures in
`tests/test_preflight_token.sh`. The focused blocker fix uses the supported `type`
operator for string selection and raw scalar output for exact text comparison; it
does not change the release-preflight workflow or its security assertions.
