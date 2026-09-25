# Tasks

## 1. Reusable Workflow: Relax ref_protected Guard and Pin CLI

- [ ] 1.1 In `.github/workflows/reusable_publish_complypack.yml` line 91, change
  `if: ${{ github.ref_protected }}` to
  `if: ${{ github.ref_protected || github.ref_type == 'tag' }}`.
  Verify: the YAML is valid (`yamllint .github/workflows/reusable_publish_complypack.yml`
  passes) and the `if` condition now includes the tag check.

- [ ] 1.2 In `.github/workflows/reusable_publish_complypack.yml`, update the
  `complypack_cli_ref` input description (around line 51-53) to remove the
  statement "complypack has no formal releases yet" and note that v0.1.0 is
  available. Verify: the description accurately reflects complypack's
  release status.

## 2. Consumer Workflow: Restructure for Release Promotion

- [ ] 2.1 In `.github/workflows/ci_publish_complypack.yml`, remove the mutual
  exclusion on `publish-ghcr`: change the `if` condition (line 66-68) so
  that the publish job runs for push events, workflow_dispatch without
  promote_quay, AND workflow_dispatch with promote_quay. The publish job
  must run for all event types that need a GHCR image.
  Verify: the `publish-ghcr` job `if` condition no longer excludes
  `promote_quay=true`.

- [ ] 2.2 In `.github/workflows/ci_publish_complypack.yml`, modify the `tag`
  input to `publish-ghcr` (line 78) to use the release tag when
  `promote_quay` is true. When dispatched from a tag with promote_quay,
  the tag should be derived from `github.ref_name`. When dispatched
  without promote_quay, use `tag_override` or `sha-<commit>` as before.
  Verify: the tag expression correctly resolves for both promote and
  non-promote dispatch paths.

- [ ] 2.3 In `.github/workflows/ci_publish_complypack.yml`, change
  `complypack_version` (line 81) from hardcoded `0.1.0-dev` to a
  conditional: use the version derived from the release tag (strip `v`
  prefix from `github.ref_name`) when `promote_quay` is true, and
  `0.0.0-dev` otherwise.
  Verify: the version expression produces valid semver in both paths.

- [ ] 2.4 In `.github/workflows/ci_publish_complypack.yml`, pin
  `complypack_cli_ref` by adding `go_version: "1.26"` and
  `complypack_cli_ref: "v0.1.0"` to the `publish-ghcr` `with` block
  (adding the cli_ref parameter explicitly rather than relying on the
  default).
  Verify: the `with` block includes both parameters.

- [ ] 2.5 In `.github/workflows/ci_publish_complypack.yml`, add
  `generate_attestations: "true"` to the `publish-ghcr` `with` block
  when `promote_quay` is true. For non-promote builds, keep `"auto"` (the
  default).
  Verify: the attestation parameter is conditionally set.

- [ ] 2.6 In `.github/workflows/ci_publish_complypack.yml`, update the
  `sign-ghcr` job's `if` condition (line 87-90) to also succeed when
  publishing from a tag ref (since the current condition depends on
  `publish-ghcr` which now runs in both promote and non-promote paths,
  verify the `always()` + success check still works correctly).
  Verify: the sign job runs after successful publish for both push-to-main
  and release-promotion paths.

- [ ] 2.7 In `.github/workflows/ci_publish_complypack.yml`, update the
  `promote-quay` job: change its dependency to require `sign-ghcr` instead
  of `verify-ghcr-source`. Update the `source_tag` to use the release tag
  (same tag the publish job used). Update the `dest_tag` to use the
  release tag (derived from `github.ref_name` or `inputs.release_tag`).
  Verify: the promote job depends on sign-ghcr and uses consistent tags.

- [ ] 2.8 In `.github/workflows/ci_publish_complypack.yml`, remove or simplify
  the `verify-ghcr-source` job. Since the pipeline now publishes before
  promoting, the standalone verification is redundant. If retained as a
  sanity check, update its source tag to use the release tag instead of
  the sha-based lookup.
  Verify: the workflow graph is coherent with no orphaned or unreachable
  jobs.

- [ ] 2.9 In `.github/workflows/ci_publish_complypack.yml`, simplify the
  `workflow_dispatch` inputs: the `source_sha` input is no longer needed
  (we rebuild instead of finding an existing image). Either remove it or
  mark it as deprecated. Update the `release_tag` description to note that
  it defaults to `github.ref_name` when dispatched from a tag.
  Verify: the inputs section is accurate and non-misleading.

- [ ] 2.10 Update the header comment block in
  `.github/workflows/ci_publish_complypack.yml` (lines 1-21) to reflect
  the new flow: when promote_quay is true, the workflow publishes to GHCR
  first, then promotes.
  Verify: the comment accurately describes the new behavior.

## 3. Cleanup and Documentation

- [ ] 3.1 Delete the root `complypack.yaml` file. Verify: `git rm complypack.yaml`
  succeeds and no workflow, Makefile, or test references the file.

- [ ] 3.2 Update `docs/COMPLYPACK_PUBLISH.md`: revise the dual-registry strategy
  table, flow diagrams, "Manual Quay Promotion" section, and
  troubleshooting section to reflect the new rebuild-and-promote flow.
  Remove references to `source_sha` if the input was removed. Update the
  local testing section to use `0.0.0-dev` instead of `0.1.0-test`.
  Verify: the document is internally consistent with the updated
  workflows and no stale references remain.

## 4. Validation

- [ ] 4.1 Run `yamllint` on both modified workflow files and verify zero errors:
  `yamllint .github/workflows/reusable_publish_complypack.yml .github/workflows/ci_publish_complypack.yml`.

- [ ] 4.2 Manually trace the workflow logic for the three trigger paths (push to
  main, workflow_dispatch promote_quay=false, workflow_dispatch
  promote_quay=true from a tag) and verify each path produces the
  expected job execution sequence as described in the spec.

- [ ] 4.3 Verify no other files in the repository reference the deleted
  `complypack.yaml` (search for `complypack.yaml` excluding workflow
  files and docs that have been updated).
