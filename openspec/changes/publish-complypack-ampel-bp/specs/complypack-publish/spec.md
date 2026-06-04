## ADDED Requirements

### Requirement: Reusable complypack pack and push
The reusable workflow SHALL accept a content directory path, registry image name, tag, evaluator ID, complypack ID, and complypack version as inputs and produce a complypack OCI artifact pushed to GHCR.

#### Scenario: Successful pack and push
- **WHEN** the reusable workflow is called with valid inputs including a content directory containing policy files
- **THEN** the workflow packs the content directory into a complypack OCI artifact and pushes it to `ghcr.io/<image_name>:<tag>`

#### Scenario: Complypack config generated from inputs
- **WHEN** the reusable workflow executes
- **THEN** the workflow generates a `complypack.yaml` configuration from the provided evaluator ID, complypack ID, and complypack version inputs without requiring a checked-in config file

#### Scenario: Digest output after push
- **WHEN** the artifact is successfully pushed to GHCR
- **THEN** the workflow outputs the artifact digest in `sha256:<64-hex-chars>` format

### Requirement: SLSA provenance attestation
The reusable workflow SHALL generate SLSA provenance attestation for published complypack artifacts when attestation generation is enabled.

#### Scenario: Provenance on protected ref
- **WHEN** the workflow runs on a protected ref with attestation generation set to auto
- **THEN** SLSA provenance attestation is generated and pushed to the registry alongside the artifact

#### Scenario: No provenance on unprotected ref with auto mode
- **WHEN** the workflow runs on an unprotected ref with attestation generation set to auto
- **THEN** no attestation is generated

#### Scenario: Forced provenance generation
- **WHEN** the workflow runs with attestation generation set to true
- **THEN** SLSA provenance attestation is generated regardless of ref protection status

### Requirement: Automatic publish on policy change
The consumer workflow SHALL publish a complypack artifact to GHCR whenever ampel branch-protection policy files change on the main branch.

#### Scenario: Policy file pushed to main
- **WHEN** a commit is pushed to the main branch that modifies files under `compliance/ampel/branch-protection/`
- **THEN** the complypack is packed and pushed to GHCR with a `sha-<commit>` tag

#### Scenario: Unrelated files changed
- **WHEN** a commit is pushed to the main branch that does not modify files under `compliance/ampel/branch-protection/`
- **THEN** the complypack publish workflow does not trigger

### Requirement: Keyless signing on GHCR
The consumer workflow SHALL sign the GHCR artifact using Sigstore keyless signing after a successful publish.

#### Scenario: Sign after publish
- **WHEN** a complypack artifact is successfully pushed to GHCR on a protected ref
- **THEN** the artifact is signed with Sigstore keyless signing and the signature is verifiable with cosign

### Requirement: Release-gated Quay promotion
The consumer workflow SHALL promote the complypack artifact from GHCR to Quay only when a GitHub release is published, using the release tag as the Quay image tag.

#### Scenario: Release triggers promotion
- **WHEN** a GitHub release is published with a semver tag
- **THEN** the complypack artifact is copied from GHCR to Quay with the release tag and the source signature is verified before promotion

#### Scenario: Source image verification before promotion
- **WHEN** the promote job starts for a release event
- **THEN** the workflow verifies that the GHCR artifact for the release commit exists before attempting promotion

#### Scenario: Missing GHCR source
- **WHEN** a release is published but no GHCR artifact exists for that commit
- **THEN** the promotion fails with a clear error message indicating the GHCR source is missing

#### Scenario: Immutable Quay tags
- **WHEN** a release tag already exists on Quay
- **THEN** the promotion fails rather than overwriting the existing tag

### Requirement: Manual dispatch
The consumer workflow SHALL support manual triggering for re-publishing or testing.

#### Scenario: Manual GHCR publish
- **WHEN** the workflow is manually dispatched
- **THEN** the workflow publishes the complypack artifact to GHCR with the default or overridden tag

### Requirement: Workflow file naming correction
The misspelled promote workflow file SHALL be renamed from `resuable_publish_quay.yml` to `reusable_publish_quay.yml` with all in-repo references updated.

#### Scenario: Renamed file
- **WHEN** the rename is applied
- **THEN** the file exists at `.github/workflows/reusable_publish_quay.yml` and no file exists at the old path

#### Scenario: In-repo references updated
- **WHEN** the rename is applied
- **THEN** all references within org-infra (including README.md) use the corrected filename

#### Scenario: External SHA-pinned references unaffected
- **WHEN** external repositories reference the old filename pinned to a specific commit SHA
- **THEN** those references continue to resolve correctly at the pinned commit
