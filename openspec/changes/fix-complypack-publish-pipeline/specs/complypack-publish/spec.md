# Spec Delta

## MODIFIED Requirements

### Requirement: Reusable complypack pack and push
The reusable workflow SHALL accept a content directory path, registry image
name, tag, evaluator ID, complypack ID, and complypack version as inputs and
produce a complypack OCI artifact pushed to GHCR. The workflow SHALL execute
on protected branches and on tag refs.

#### Scenario: Successful pack and push
- **WHEN** the reusable workflow is called with valid inputs including a content directory containing policy files
- **THEN** the workflow packs the content directory into a complypack OCI artifact and pushes it to `ghcr.io/<image_name>:<tag>`

#### Scenario: Complypack config generated from inputs
- **WHEN** the reusable workflow executes
- **THEN** the workflow generates a complypack config containing id, evaluator-id, and version fields from the provided inputs, without requiring a checked-in config file

#### Scenario: Digest and output validation
- **WHEN** the artifact is successfully pushed to GHCR
- **THEN** the workflow outputs digest in sha256 hex format, image matching the input image_name, and tag matching the input tag

#### Scenario: Pack failure
- **WHEN** the complypack CLI fails to pack the content directory
- **THEN** the workflow fails with a non-zero exit code and the CLI error output is visible in the workflow logs

#### Scenario: Digest retrieval failure
- **WHEN** the ORAS manifest fetch fails or returns a digest not matching the expected format
- **THEN** the workflow fails with a clear error message indicating the unexpected digest format

#### Scenario: Publish from a tag ref
- **WHEN** the reusable workflow is called from a tag ref
- **THEN** the workflow SHALL execute the publish job (the ref_protected guard SHALL NOT block tag refs)

#### Scenario: Publish blocked on unprotected branch
- **WHEN** the reusable workflow is called from an unprotected branch (not main, not a tag)
- **THEN** the publish job is skipped

### Requirement: Supply chain attestations
The reusable workflow SHALL generate SLSA provenance and SBOM attestations
for published complypack artifacts when attestation generation is enabled.
The consumer workflow SHALL force attestations on release builds.

#### Scenario: Provenance and SBOM on protected ref
- **WHEN** the workflow runs on a protected ref with attestation generation set to auto
- **THEN** SLSA provenance attestation and an SBOM attestation are generated and pushed to the registry alongside the artifact

#### Scenario: No attestations on unprotected ref with auto mode
- **WHEN** the workflow runs on an unprotected ref with attestation generation set to auto
- **THEN** no attestations are generated

#### Scenario: Forced attestation generation
- **WHEN** the workflow runs with attestation generation set to true
- **THEN** SLSA provenance and SBOM attestations are generated regardless of ref protection status

#### Scenario: Release builds force attestations
- **WHEN** the consumer workflow publishes a complypack for release promotion
- **THEN** the consumer SHALL pass generate_attestations as true to ensure attestations are present on the release artifact

### Requirement: Release-gated Quay promotion
The consumer workflow SHALL promote the complypack artifact from GHCR to
Quay only during a release flow, using the release tag as the Quay image
tag. Promotion SHALL rebuild the artifact from the release commit to ensure
the GHCR image exists with the release tag before copying to Quay.

#### Scenario: Manual dispatch triggers rebuild and promotion
- **WHEN** the workflow is manually dispatched from a release tag with promotion enabled
- **THEN** the workflow rebuilds the complypack from the release commit, publishes to GHCR with the release tag, signs the artifact, and promotes to Quay with the same tag

#### Scenario: Release tag derived from ref
- **WHEN** the workflow is dispatched from a tag ref
- **THEN** the release tag SHALL be derived from the ref name without requiring the user to manually specify it

#### Scenario: Source image verification before promotion
- **WHEN** the promote job starts after the publish job completes
- **THEN** the GHCR artifact with the release tag SHALL exist because the workflow published it in a preceding job

#### Scenario: Immutable Quay tags
- **WHEN** a release tag already exists on Quay
- **THEN** the promotion fails with a non-zero exit code and an error message indicating the destination tag already exists, without modifying the existing artifact

### Requirement: Manual dispatch
The consumer workflow SHALL support manual triggering for re-publishing to
GHCR or for combined publish-and-promote to Quay.

#### Scenario: Manual dispatch for GHCR only
- **WHEN** the workflow is manually dispatched without promotion enabled
- **THEN** the workflow publishes the complypack artifact to GHCR with the specified or default tag

#### Scenario: Manual dispatch with tag override
- **WHEN** the workflow is manually dispatched with a tag_override value and promotion disabled
- **THEN** the workflow publishes the complypack artifact to GHCR with the provided tag

#### Scenario: Manual dispatch for release promotion
- **WHEN** the workflow is manually dispatched from a release tag with promotion enabled
- **THEN** the workflow publishes to GHCR with the release tag, signs, and promotes to Quay in a single run

### Requirement: Keyless signing on GHCR
The consumer workflow SHALL sign the GHCR artifact using Sigstore keyless
signing after a successful publish, including for release builds from tags.

#### Scenario: Sign after publish on protected ref
- **WHEN** a complypack artifact is successfully pushed to GHCR on a protected ref
- **THEN** the artifact is signed with Sigstore keyless signing and the signature is verifiable with cosign

#### Scenario: Sign after publish from tag ref
- **WHEN** a complypack artifact is successfully pushed to GHCR from a tag ref during release promotion
- **THEN** the artifact is signed with Sigstore keyless signing

## ADDED Requirements

### Requirement: Complypack artifact version alignment
The consumer workflow SHALL derive the complypack artifact version from the
release tag for release builds and use a fixed development version for
non-release builds.

#### Scenario: Development build version
- **WHEN** the workflow publishes a complypack artifact from a push to main
- **THEN** the complypack artifact version SHALL be a fixed development placeholder distinct from any release version

#### Scenario: Release build version
- **WHEN** the workflow publishes a complypack artifact for release promotion from a tag
- **THEN** the complypack artifact version SHALL be derived from the release tag

### Requirement: CLI version pinning
The consumer workflow SHALL pin the complypack CLI to a specific release
version for build reproducibility.

#### Scenario: Pinned CLI version
- **WHEN** the consumer workflow installs the complypack CLI
- **THEN** it SHALL use a pinned release version rather than latest

## REMOVED Requirements

### Requirement: Workflow file naming correction
**Reason**: This requirement was delivered in the original complypack-publish
change and is no longer relevant to this delta.
**Migration**: No migration needed; the rename is already applied.
