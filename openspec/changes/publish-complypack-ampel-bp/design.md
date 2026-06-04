## Context

The ampel granular policies (5 JSON files in `compliance/ampel/branch-protection/`) are the canonical source for branch protection compliance checks across the ComplyTime org. Currently, `reusable_compliance.yml` manually copies them at runtime via a TEMPORARY `cp` step (lines 106-112).

With complyctl#536 merged, `complyctl get` can now pull complypack OCI artifacts from registries via a `complypacks:` config section. The `complypack` CLI (`github.com/complytime/complypack`) provides a `pack` subcommand that creates properly-structured OCI artifacts (`artifactType: application/vnd.complypack.artifact.v1`).

The org already has established patterns for OCI artifact publishing:
- `reusable_publish_ghcr.yml` / `reusable_publish_oras.yml`: push to GHCR with provenance
- `reusable_sign_and_verify.yml`: keyless Sigstore signing
- `resuable_publish_quay.yml` (typo): promote from GHCR to Quay with signature verification
- `complytime-collector-components`: exemplifies the dual-registry pattern (GHCR on push, Quay on release tag)

## Goals / Non-Goals

**Goals:**
- Automate complypack artifact publishing for ampel branch-protection policies
- Follow org conventions: GHCR first (dev/test), Quay on release (production)
- Create a reusable workflow generic enough for any evaluator's complypack
- Chain existing sign and promote workflows for full supply-chain coverage
- Fix the `resuable_publish_quay.yml` typo

**Non-Goals:**
- Removing the TEMPORARY staging step in `reusable_compliance.yml` (depends on downstream provider changes, tracked as #307)
- Publishing complypacks for non-ampel evaluators from this repo
- Creating a dedicated GitHub Action (like `gemara-publish-action`) for complypack
- Modifying the complypack CLI or library

## Decisions

### D1: GHCR-first with release-gated Quay promotion

**Decision**: Publish to GHCR on every push-to-main that changes policy files. Promote to Quay only when a GitHub release is published.

**Alternatives considered**:
- *Direct Quay publish on push*: Rejected. Pollutes the production registry with every commit. No clear way to distinguish stable from dev.
- *Dual-publish on every push*: Rejected. Quay should contain only release-quality content. Matches the user's requirement that "GHCR is for tests, Quay is for production."
- *Quay-only (no GHCR)*: Rejected. Loses the dev/test staging area and breaks the org convention established by collector-components.

### D2: Reuse existing promote and sign workflows

**Decision**: Chain `reusable_sign_and_verify.yml` (with `verify_vuln: false`) for GHCR signing and `reusable_publish_quay.yml` (renamed) for GHCR-to-Quay promotion. Do not build new signing or promotion logic.

**Alternatives considered**:
- *Embed signing in the complypack workflow*: Rejected. Duplicates cosign setup and signing logic already maintained in `reusable_sign_and_verify.yml`. Violates DRY.
- *All-in-one action (like gemara-publish-action)*: Rejected. Higher initial effort, less reusable across different publish patterns, and harder to maintain. The composable workflow-chaining approach matches the collector-components precedent.

### D3: Generate complypack.yaml at workflow time

**Decision**: The reusable workflow generates `complypack.yaml` from input parameters (`evaluator_id`, `complypack_id`, `complypack_version`) rather than reading a checked-in config file.

**Alternatives considered**:
- *Checked-in complypack.yaml*: Rejected. The `version` field would need to be maintained manually or overridden at workflow time. Generating it avoids this lifecycle complexity and keeps version derivation in the CI layer where it belongs.
- *Accept config_path input*: Rejected. Forces callers to manage a config file with a version that must match the publish tag. The generation approach makes the workflow self-contained.

### D4: Go stable default for complypack CLI installation

**Decision**: Use `actions/setup-go` with `go-version: 'stable'` by default, with an optional `go_version` input override. Install the complypack CLI via `go install`.

**Alternatives considered**:
- *Download pre-built binary from GitHub releases*: Considered but the complypack repo only has 2 tags and no published release binaries. `go install` is reliable and the setup-go action caches the toolchain.
- *Hard-coded Go version*: Rejected. The `stable` keyword in setup-go always resolves to the latest stable release, avoiding version rot.

### D5: ORAS for digest retrieval after pack

**Decision**: Install ORAS and use `oras manifest fetch --descriptor | jq -r '.digest'` to retrieve the pushed artifact's digest. This matches the pattern in `reusable_publish_oras.yml`.

**Alternatives considered**:
- *Parse complypack CLI output*: Rejected. The CLI's output format is not documented and may change. Relying on OCI tooling (ORAS) for digest retrieval is standard and stable.
- *Use crane*: Viable but ORAS is already used in `reusable_publish_oras.yml`, providing consistency. Both would work.

### D6: Provenance-only attestations (no SBOM)

**Decision**: Generate only SLSA provenance attestation via `actions/attest-build-provenance`. Skip SBOM generation.

**Alternatives considered**:
- *Provenance + SBOM*: Rejected for complypacks specifically. SBOM scanning policy JSON files produces a trivial, uninformative SBOM (no dependencies, no software bill). Provenance alone provides the supply-chain traceability needed.
- *No attestations*: Rejected. Provenance is a core org requirement for published artifacts.

### D7: Single consumer workflow with conditional jobs

**Decision**: One `ci_publish_complypack.yml` with multiple triggers (`push`, `release`, `workflow_dispatch`) and conditional job execution based on the event type.

**Alternatives considered**:
- *Separate workflows per trigger*: Rejected. Creates more files for a simple routing concern. The collector-components does use separate files (`ci_publish_ghcr.yml`, `ci_publish_quay.yml`), but their pipeline is more complex (multi-image builds, scanning, integration tests). Our case is simpler.

### D8: Typo fix via rename + follow-up issue

**Decision**: Rename `resuable_publish_quay.yml` to `reusable_publish_quay.yml` in org-infra, update the README reference, and file a follow-up issue in `complytime-collector-components`.

**Alternatives considered**:
- *Keep the typo*: Rejected. The typo violates the `reusable_` naming convention. SHA-pinned external references will continue to work at their pinned commit; the rename only affects future callers.
- *Coordinate a simultaneous cross-repo rename*: Rejected. Unnecessary complexity. SHA pinning makes this a safe, incremental change.

## Risks / Trade-offs

- **[Risk] complypack CLI interface changes** -- The workflow calls `complypack pack <dir> <ref>` which is the documented CLI interface. If the API changes, the workflow breaks. Mitigation: pin `complypack_cli_ref` to a specific release tag rather than `latest` in the consumer workflow.

- **[Risk] Quay attestation compatibility** -- GitHub's `actions/attest-build-provenance` pushes attestations via OCI referrers API. Quay supports this, but the behavior with `cosign copy` (used by the promote workflow) should be verified. Mitigation: the promote workflow already works for container images with attestations; complypack artifacts use the same OCI manifest structure.

- **[Risk] Release without prior GHCR publish** -- If someone cuts a release tag on a commit that never triggered the push-to-main workflow (e.g., non-policy changes only), the promote job will fail because no GHCR image exists. Mitigation: the consumer workflow includes a `verify-ghcr-source` job that checks GHCR before attempting promotion, with a clear error message.

- **[Trade-off] Go toolchain in reusable workflow** -- Installing Go adds ~15-20s to the workflow. Acceptable for a workflow that runs infrequently (only on policy file changes). If complypack publishes release binaries in the future, this can be swapped for a direct binary download.
