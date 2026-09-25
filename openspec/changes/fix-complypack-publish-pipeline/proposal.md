# Proposal

## Why

The complypack publish pipeline for ampel branch-protection policies cannot
promote OCI artifacts to Quay.io, either automatically or manually. Four
compounding issues prevent both the release-triggered and manual promotion
flows from working: a `ref_protected` guard that silently skips publishing
from tags, a GITHUB_TOKEN limitation that prevents release events from
firing, a tag mismatch between GHCR images and promotion lookups, and an
attestation policy that disables SLSA/SBOM for tag-based builds. Meanwhile,
the same pattern works in `complytime-policies` because it uses a
single-phase publish model. This change fixes the org-infra pipeline while
preserving the intentional two-phase model (GHCR for testing, Quay on
release).

## What Changes

- **Restructure `ci_publish_complypack.yml`**: When promoting to Quay, the
  workflow now rebuilds the complypack from the release commit first
  (tagged with the release version), then signs, then promotes. Eliminates
  the mutual exclusion between publish and promote jobs.
- **Relax `ref_protected` guard in `reusable_publish_complypack.yml`**: Allow
  publishing from tags in addition to protected branches, enabling release
  builds. Tags are intentional release points and the calling workflow
  controls invocation.
- **Pin complypack CLI to v0.1.0**: The first formal release of complypack
  exists; pin for reproducibility instead of using `@latest`.
- **Differentiate complypack artifact version**: Use `0.0.0-dev` for
  development builds (push to main) and derive from the release tag for
  release builds.
- **Force attestations for release builds**: Pass
  `generate_attestations: "true"` for release builds since the `auto` policy
  disables attestations on tags (where `ref_protected` is false).
- **Remove stale root `complypack.yaml`**: The reusable workflow generates
  its own config at build time; the root file is unused and contradicts the
  workflow values.
- **Update `docs/COMPLYPACK_PUBLISH.md`**: Reflect the new rebuild-and-promote
  flow, simplified manual promotion steps, and updated troubleshooting.

## Non-goals

- Automating Quay promotion via App token in `release.yml`. This is a
  follow-up change; manual promotion is sufficient for now.
- Changing the `complytime-policies` publish workflow. That pipeline uses a
  different model (`gemara-publish-action`, single-phase) and works correctly.
- Changing the `reusable_publish_quay.yml` promote workflow itself. The
  promotion logic is correct; the issue is upstream (no GHCR image to
  promote).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `complypack-publish`: The release-gated Quay promotion requirement changes
  from "find an existing GHCR image by commit SHA" to "rebuild from the
  release commit with the release tag, then promote." The manual dispatch
  requirement changes to support a unified publish-then-promote flow when
  dispatched from a tag. The attestation requirement is tightened to force
  attestations on release builds regardless of ref protection status.

## Impact

- **Workflows**: `ci_publish_complypack.yml` (major restructure),
  `reusable_publish_complypack.yml` (guard relaxation + CLI pin update).
- **Documentation**: `docs/COMPLYPACK_PUBLISH.md` (flow diagrams, manual
  promotion steps, troubleshooting).
- **Files removed**: Root `complypack.yaml` (stale, unused).
- **Downstream consumers of `reusable_publish_complypack.yml`**: The
  `ref_protected` relaxation allows tag-based publishing. This is additive
  and non-breaking; existing consumers on protected branches are unaffected.
- **Downstream consumers of Quay artifacts**: No change to artifact format or
  registry location. Consumers referencing Quay tags continue to work.
