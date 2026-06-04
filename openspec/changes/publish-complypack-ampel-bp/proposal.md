## Why

The ampel granular policies at `compliance/ampel/branch-protection/` (5 JSON files) are manually staged during compliance scans via a TEMPORARY workaround in `reusable_compliance.yml:106-112`. With complyctl's complypack-pull feature (complytime/complyctl#536 merged), these policies can now be packaged and published as a complypack OCI artifact, enabling automated distribution via `complyctl get`.

Closes complytime/org-infra#306.

## Non-goals

- Modifying CEL expressions, predicate URLs, or assessment/error messages in the policy files.
- Changing the `complytime.yaml` structure or the `complyctl get` command.
- Removing the TEMPORARY staging step from `reusable_compliance.yml` (tracked separately as #307, depends on downstream provider changes).
- Publishing complypacks for other evaluators (OPA, etc.) from this repo.

## What Changes

- Add `reusable_publish_complypack.yml`: a new reusable workflow that packs a content directory into a complypack OCI artifact and pushes it to GHCR with SLSA provenance attestation. Uses the `complypack pack` CLI. Generic enough for any evaluator across the org.
- Add `ci_publish_complypack.yml`: a consumer workflow in org-infra that publishes the ampel branch-protection policies with a dual-registry strategy:
  - **Push to main** (policy file changes): publish to GHCR with `sha-<commit>` tag (dev/test).
  - **Release published**: promote from GHCR to Quay via the existing promote workflow with the semver release tag (production).
- Chain existing `reusable_sign_and_verify.yml` for keyless Sigstore signing on GHCR.
- Chain existing promote workflow for GHCR-to-Quay promotion on release, with source signature verification and immutable semver tags.
- **Rename** `resuable_publish_quay.yml` to `reusable_publish_quay.yml` (typo fix) and update all in-repo references. File a follow-up issue in `complytime-collector-components` for their SHA-pinned reference update.

## Capabilities

### New Capabilities

- `complypack-publish`: Reusable workflow for packing and publishing complypack OCI artifacts to GHCR with provenance attestation, plus a consumer workflow implementing the dual-registry strategy (GHCR for dev, Quay for production releases).

### Modified Capabilities

## Impact

- **`.github/workflows/`**: Three workflow files added (`reusable_publish_complypack.yml`, `ci_publish_complypack.yml`) and one renamed (`resuable_publish_quay.yml` to `reusable_publish_quay.yml`).
- **`README.md`**: Updated to reflect the renamed workflow file.
- **Secrets**: Quay credentials (`QUAY_USERNAME`, `QUAY_PASSWORD`) must be configured in org-infra repository secrets for release promotion.
- **Downstream**: `complytime-collector-components` references the misspelled workflow filename pinned to a SHA. A follow-up issue is needed for them to update the reference when they next bump their org-infra pin (no breakage until then).
- **Registry artifacts**: New OCI artifacts published to `ghcr.io/complytime/complypack-ampel-branch-protection` (on push) and `quay.io/complytime/complypack-ampel-branch-protection` (on release).
- **Sync impact**: `reusable_publish_complypack.yml` and `ci_publish_complypack.yml` are NOT in `sync-config.yml` (org-infra only). The renamed `reusable_publish_quay.yml` IS consumed cross-repo, but SHA pinning prevents breakage.
