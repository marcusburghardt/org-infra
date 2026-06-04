## 1. Typo Fix: Rename Promote Workflow

- [x] 1.1 Rename `.github/workflows/resuable_publish_quay.yml` to `.github/workflows/reusable_publish_quay.yml`
- [x] 1.2 Update `README.md` reference from `resuable_publish_quay.yml` to `reusable_publish_quay.yml`
- [ ] 1.3 File a follow-up issue in `complytime-collector-components` to update their SHA-pinned reference in `ci_publish_quay.yml`

## 2. Reusable Workflow: Scaffold and Permissions

- [x] 2.1 Create `.github/workflows/reusable_publish_complypack.yml` with header comment block describing purpose
- [x] 2.2 Define `workflow_call` inputs: `content_path`, `image_name`, `tag`, `evaluator_id`, `complypack_id`, `complypack_version`, `go_version` (default: `stable`), `complypack_cli_ref` (default: `latest`), `generate_attestations` (default: `auto`)
- [x] 2.3 Define `workflow_call` outputs: `digest`, `image`, `tag`
- [x] 2.4 Set workflow-level permissions to `none` and job-level permissions to minimum required (`contents: read`, `packages: write`, `id-token: write`, `attestations: write`)
- [x] 2.5 Add concurrency group (`reusable-complypack-<image_name>-<ref>`) with `cancel-in-progress: true`
- [x] 2.6 Set `timeout-minutes` on the publish job (e.g., 15 minutes), consistent with existing reusable workflows

## 3. Reusable Workflow: Job Steps

- [x] 3.1 Add checkout step with `persist-credentials: false`
- [x] 3.2 Add GHCR login step using `docker/login-action` (pinned to SHA) with `GITHUB_TOKEN`
- [x] 3.3 Add `actions/setup-go` step (pinned to SHA) using `go_version` input
- [x] 3.4 Add step to install complypack CLI via `go install github.com/complytime/complypack/cmd/complypack@<complypack_cli_ref>`
- [x] 3.5 Add step to generate `complypack.yaml` from `evaluator_id`, `complypack_id`, and `complypack_version` inputs
- [x] 3.6 Add step to run `complypack pack <content_path> ghcr.io/<image_name>:<tag>`
- [x] 3.7 Add `oras-project/setup-oras` step (pinned to SHA) for digest retrieval
- [x] 3.8 Add step to fetch and validate digest via `oras manifest fetch` with `sha256:<64hex>` format check
- [x] 3.9 Add attestation policy resolution step (auto vs true, matching `reusable_publish_ghcr.yml` pattern)
- [x] 3.10 Add `actions/attest-build-provenance` step (pinned to SHA, conditional on attestation policy) for SLSA provenance
- [x] 3.11 Add `anchore/sbom-action` step (pinned to SHA, conditional on attestation policy) scanning `content_path` to generate `sbom.spdx.json`
- [x] 3.12 Add `actions/attest` step (pinned to SHA, conditional on attestation policy) to attach the SBOM attestation
- [x] 3.13 Add step to set output values (`digest`, `image`, `tag`)

## 4. Consumer Workflow: Scaffold and Triggers

- [x] 4.1 Create `.github/workflows/ci_publish_complypack.yml` with header comment block describing dual-registry strategy
- [x] 4.2 Define triggers: `push` (branches: `[main]`, paths: `['compliance/ampel/branch-protection/**']`), `release` (types: `[published]`), `workflow_dispatch` (with optional `tag_override` input)
- [x] 4.3 Set workflow-level permissions to `none`
- [x] 4.4 Add concurrency group (e.g., `ci-complypack-ampel-bp-${{ github.ref }}`) with `cancel-in-progress: true` for push, `false` for release

## 5. Consumer Workflow: GHCR Publish Job

- [x] 5.1 Add `publish-ghcr` job, conditioned on `push` or `workflow_dispatch` events
- [x] 5.2 Call `reusable_publish_complypack.yml` with: `content_path: compliance/ampel/branch-protection`, `image_name: complytime/complypack-ampel-branch-protection`, `tag: sha-${{ github.sha }}`, `evaluator_id: ampel`, `complypack_id: io.complytime.ampel-branch-protection`, `complypack_version: 0.1.0-dev`, `go_version: '1.26'`
- [x] 5.3 Set job-level permissions: `contents: read`, `packages: write`, `id-token: write`, `attestations: write`

## 6. Consumer Workflow: GHCR Signing Job

- [x] 6.1 Add `sign-ghcr` job, dependent on `publish-ghcr`, conditioned on success and protected ref
- [x] 6.2 Call `reusable_sign_and_verify.yml` with outputs from `publish-ghcr`, `verify_vuln: false`, and `allowed_identity_regex` matching org-infra workflows
- [x] 6.3 Set job-level permissions: `packages: write`, `id-token: write`

## 7. Consumer Workflow: Quay Promotion Jobs

- [x] 7.1 Add `verify-ghcr-source` job, conditioned on `release` event, that uses `crane` to check the GHCR artifact exists at `sha-${{ github.sha }}` with a clear error message if missing
- [x] 7.2 Add `promote-quay` job, dependent on `verify-ghcr-source`, calling `reusable_publish_quay.yml` (renamed) with `source_registry: ghcr.io`, `source_image: complytime/complypack-ampel-branch-protection`, `source_tag: sha-${{ github.sha }}`, `dest_registry: quay.io`, `dest_image: complytime/complypack-ampel-branch-protection`, `dest_tag: ${{ github.event.release.tag_name }}`, `allowed_identity_regex: https://github.com/complytime/org-infra(/.*)?`, `fail_if_dest_exists: true`
- [x] 7.3 Pass Quay credentials via secrets: `dest_username: ${{ secrets.QUAY_USERNAME }}`, `dest_password: ${{ secrets.QUAY_PASSWORD }}`

## 8. Documentation Updates

- [x] 8.1 Add `reusable_publish_complypack.yml` and `ci_publish_complypack.yml` entries to `README.md` directory structure with descriptions
- [x] 8.2 Add a Recent Changes entry to `AGENTS.md` for this feature (new workflows, rename, OCI dependencies)

## 9. Validation

- [x] 9.1 Run `make lint` (yamllint) on all new and modified workflow files -- zero lint errors
- [x] 9.2 Verify all `uses:` action references are pinned to full 40-character commit SHAs with inline version comment
- [x] 9.3 Verify workflow-level permissions are set to `none` and job-level permissions are minimal
- [x] 9.4 Verify the renamed `reusable_publish_quay.yml` has no broken in-repo references (grep for old name)
- [x] 9.5 Verify neither `reusable_publish_complypack.yml` nor `ci_publish_complypack.yml` appear in `sync-config.yml`
<!-- spec-review: passed -->
<!-- code-review: passed -->
