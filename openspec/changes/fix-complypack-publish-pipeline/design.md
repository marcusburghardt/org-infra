# Design

## Context

See `proposal.md` for motivation. The current pipeline has four compounding
failures documented there.

Key files:

| File | Role |
|---|---|
| `.github/workflows/reusable_publish_complypack.yml` | Reusable: pack + push to GHCR |
| `.github/workflows/reusable_publish_quay.yml` | Reusable: promote GHCR to Quay |
| `.github/workflows/reusable_sign_and_verify.yml` | Reusable: Sigstore signing |
| `.github/workflows/ci_publish_complypack.yml` | Consumer: orchestrates the above |
| `docs/COMPLYPACK_PUBLISH.md` | Operational guide |
| `complypack.yaml` | Stale root config (unused) |

The `reusable_publish_complypack.yml` is consumed by org-infra today but
designed for any repository publishing complypacks. Changes to it must remain
safe for all consumers.

The complypack CLI released v0.1.0 on 2026-09-25. The workflow currently
installs `@latest` (latest commit on main) per a comment noting "complypack
has no formal releases yet."

## Goals / Non-Goals

**Goals:**

- Make manual Quay promotion work reliably after a release is cut
- Ensure release artifacts have SLSA provenance and SBOM attestations
- Pin complypack CLI to a release tag for reproducibility
- Align complypack artifact version with the org-infra release tag
- Remove stale files that cause confusion

**Non-Goals:**

- Automating Quay promotion via App token in `release.yml` (follow-up)
- Changing `complytime-policies` publish workflow
- Changing `reusable_publish_quay.yml` promote logic
- Adding new registries or artifact types

## Decisions

### D1: Rebuild from release commit instead of finding existing image

**Decision**: When promoting to Quay, rebuild the complypack from the
release commit with the release tag, then promote the freshly published
GHCR image.

**Alternatives considered**:

- *Tag the existing `:latest` GHCR image with the release version*:
  Rejected. `:latest` may not correspond to the release commit if policy
  files changed after the release was cut but before promotion. Does not
  guarantee the promoted content matches the released code.

- *Track GHCR digests across runs (state-based)*: Rejected. Requires
  persistent state (cache, artifact, or external store) to map commits to
  digests. Adds complexity and failure modes for a rarely-changing artifact.

**Rationale**: Rebuilding from the release commit is deterministic, requires
no state tracking, and guarantees the Quay artifact reflects the exact
source code at the release tag. The policy file content is identical to
what was tested on GHCR (policy files are stable JSON, rarely changed).

### D2: Relax ref_protected guard with tag allowance

**Decision**: Change the reusable workflow's publish guard from
`if: github.ref_protected` to
`if: github.ref_protected || github.ref_type == 'tag'`.

**Alternatives considered**:

- *Add an input parameter to opt out of the guard*: Rejected. Consumers
  could accidentally set it to `false` without understanding the
  implications. The guard's purpose is preventing publishes from
  unprotected feature branches, not from tags.

- *Remove the guard entirely*: Rejected. Feature-branch publishes should
  remain blocked as a defense-in-depth measure.

**Rationale**: Tags represent intentional release points. The calling
workflow already controls when to invoke the reusable workflow. Allowing
tags is a minimal, safe relaxation that serves the release use case without
weakening protection against accidental feature-branch publishes.

### D3: Force attestations for release builds

**Decision**: The consumer workflow passes `generate_attestations: "true"`
when publishing for release promotion.

**Alternatives considered**:

- *Change the `auto` policy to also enable attestations on tags*: Rejected.
  This would change behavior for all consumers of the reusable workflow.
  Some consumers may intentionally skip attestations for tag-based test
  builds. The consumer should control this explicitly.

- *Add a new attestation policy value (e.g., `auto-with-tags`)*: Rejected.
  Adds complexity to the reusable interface for a single use case. The
  existing `true` value already handles this.

**Rationale**: Release artifacts going to Quay must have supply chain
attestations per the constitution. The `auto` policy uses `ref_protected`
which is `false` for tags. Forcing `true` in the consumer is the simplest
fix that doesn't change reusable workflow semantics for other callers.

### D4: Derive release tag from github.ref_name

**Decision**: When dispatched from a tag ref, derive the release tag and
complypack version from `github.ref_name` (e.g., `v0.8.0`). The complypack
version strips the `v` prefix (e.g., `0.8.0`).

**Alternatives considered**:

- *Require the user to manually type the release tag*: Rejected. Redundant
  and error-prone when the user already selected the tag in the dispatch UI.

- *Use a fixed mapping or lookup table*: Rejected. Over-engineered for a
  value that's directly available from the GitHub context.

**Rationale**: Simplifies the user experience for the most common promotion
path. The user dispatches from the release tag and the workflow derives
everything else. The `release_tag` input remains available as an override
for edge cases.

### D5: Remove root complypack.yaml

**Decision**: Delete the root `complypack.yaml` file.

**Alternatives considered**:

- *Keep as documentation*: Rejected. It has `version: 0.1.0-test` while the
  workflow uses `0.1.0-dev` — it's already contradictory. The reusable
  workflow generates its own config at build time (design decision D3 from
  the original complypack-publish change). The local testing section in
  `docs/COMPLYPACK_PUBLISH.md` already documents the expected config
  format. Keeping a stale root file adds confusion.

**Rationale**: The file is unused by any workflow, Makefile, test, or script.
The design decision to generate config at workflow time explicitly chose
this over checked-in config. Removing it eliminates a source of confusion.

### D6: Pin complypack CLI to v0.1.0

**Decision**: Set `complypack_cli_ref: "v0.1.0"` in the consumer workflow.
The reusable workflow's default remains `"latest"` for flexibility.

**Alternatives considered**:

- *Change the reusable default to `v0.1.0`*: Rejected. Other consumers may
  want `latest` during early development. The reusable should stay
  flexible; the consumer pins.

- *Use `stable` or `latest` tag*: Rejected. `latest` installs from HEAD
  of main, not the latest release. No `stable` tag exists.

**Rationale**: v0.1.0 is the first formal release. Pinning ensures
reproducible builds. The reusable workflow comment noting "complypack has
no formal releases yet" should be updated to reflect this.

### D7: Use 0.0.0-dev for development builds

**Decision**: Use `0.0.0-dev` as the fixed complypack artifact version for
development builds (push to main). Release builds use the version derived
from the tag (D4).

**Alternatives considered**:

- *Keep `0.1.0-dev`*: Rejected. With release versions now derived from
  org-infra tags (e.g., `0.8.0`, `0.9.0`), a fixed `0.1.0-dev` could be
  confused with a pre-release of `0.1.0`.

- *Use `sha-<commit>` as the version*: Rejected. The complypack version
  field expects semver format.

**Rationale**: `0.0.0-dev` is clearly a non-release artifact. It's valid
semver with a pre-release identifier and cannot be confused with any
release version.

## Risks / Trade-offs

**Rebuilding produces a different OCI digest than the tested artifact**:
The GHCR image published during the release flow has a different digest
from the `:latest` image that engineers tested. The policy file content is
identical (same JSON files at the same commit), but OCI metadata
(timestamps, layer digests from tar+gzip) may differ.
Mitigation: engineers can verify the GHCR `vX.Y.Z` image
after the release publish step. The complypack artifact type is opaque
content (tar+gzip of JSON files) — content correctness depends on the
source files, not the OCI metadata.

**Go version drift**: The consumer pins `go_version: "1.26.4"` but
complypack v0.1.0 uses Go 1.26.8 in its go.mod. `go install` should work
with any recent Go version, but a mismatch could cause unexpected behavior.
Mitigation: update `go_version` to `"stable"` or match complypack's
go.mod version.

**Tag protection rules**: If the org later enables tag protection rules in
GitHub, `ref_protected` would become `true` for protected tags, making the
`|| github.ref_type == 'tag'` clause redundant but harmless.
