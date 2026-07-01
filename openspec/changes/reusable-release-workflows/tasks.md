## 1. Scaffold reusable preflight workflow

- [ ] 1.1 Create `.github/workflows/reusable_release_preflight.yml` with workflow header
  comment, `workflow_call` trigger, inputs (`tag`, `allow_prerelease`, `ci_checks`,
  `default_branch`), outputs (`tag`, `tag_created`), and workflow-level `permissions: {}`
- [ ] 1.2 Add preflight job scaffold with `runs-on: ubuntu-latest`, job-level
  permissions (`contents: write`, `checks: read`), `timeout-minutes`, concurrency group,
  and `env:` block routing `tag` input through environment variable
- [ ] 1.3 Add checkout step to `reusable_release_preflight.yml` pinned to SHA with
  `fetch-depth: 0` for full tag history, `persist-credentials: false`, and explicit
  token-based push authentication in the tag creation step

## 2. Implement preflight validation steps

- [ ] 2.1 Add tag format validation step to `reusable_release_preflight.yml` with
  configurable regex based on `allow_prerelease` input (strict `vX.Y.Z` when false,
  `vX.Y.Z[-prerelease]` when true)
- [ ] 2.2 Add smart tag uniqueness step to `reusable_release_preflight.yml` that
  dereferences annotated tags to detect re-runs (tag at HEAD) vs. conflicts (tag at
  different commit), outputting `tag_exists_at_head` for downstream step conditionals
- [ ] 2.3 Add semver ordering verification step to `reusable_release_preflight.yml` with
  `sort -V` fast path for strict semver and Python inline comparator for pre-release
  tags; skip on re-run via `tag_exists_at_head` output
- [ ] 2.4 Add CI check discovery step to `reusable_release_preflight.yml` that reads
  `ci_checks.yml`, `ci_security.yml`, and `ci_local.yml` from the checkout; constructs
  expected check names using `yq` for `ci_local.yml` parsing; falls back to explicit
  `ci_checks` input when provided
- [ ] 2.5 Add CI check verification step to `reusable_release_preflight.yml` with
  paginated `gh api` calls, separated API error handling (no `2>/dev/null`), and
  at-least-one security scan gate when `ci_security.yml` is present
- [ ] 2.6 Add unreleased commits verification step to `reusable_release_preflight.yml`
  using `git rev-list --count`; skip on re-run
- [ ] 2.7 Add idempotent annotated tag creation step to
  `reusable_release_preflight.yml` using `github-actions[bot]` identity; skip when tag
  already exists at HEAD

## 3. Scaffold reusable GoReleaser workflow

- [ ] 3.1 Create `.github/workflows/reusable_release_goreleaser.yml` with workflow
  header comment, `workflow_call` trigger, inputs (`tag`, `goreleaser_version`,
  `goreleaser_args`), and workflow-level `permissions: {}`
- [ ] 3.2 Add release job scaffold with `runs-on: ubuntu-latest`, job-level permissions
  (`contents: write`, `id-token: write`), `timeout-minutes`, and `env:` block routing
  `tag` input through environment variable

## 4. Implement GoReleaser execution steps

- [ ] 4.1 Add checkout step to `reusable_release_goreleaser.yml` pinned to SHA with
  `fetch-depth: 0`, `ref` from tag input, and `persist-credentials: false`
- [ ] 4.2 Add setup-go step to `reusable_release_goreleaser.yml` pinned to SHA with
  `go-version-file: go.mod` and `cache: false`
- [ ] 4.3 Add cosign-installer step to `reusable_release_goreleaser.yml` pinned to SHA
- [ ] 4.4 Add sbom-action/download-syft step to `reusable_release_goreleaser.yml` pinned
  to SHA
- [ ] 4.5 Add goreleaser-action step to `reusable_release_goreleaser.yml` pinned to SHA
  with configurable version and args inputs, `GORELEASER_CURRENT_TAG` and
  `GITHUB_TOKEN` environment variables

## 5. Write adoption documentation

- [ ] 5.1 Create `docs/RELEASE_WORKFLOWS.md` with overview section including ASCII
  architecture diagram showing the two new reusable workflows and their composition with
  existing publishing workflows
- [ ] 5.2 Add prerequisites section to `docs/RELEASE_WORKFLOWS.md` listing required and
  recommended setup items
- [ ] 5.3 Add per-repo-type adoption instructions to `docs/RELEASE_WORKFLOWS.md` with
  step-by-step migration guides and copy-pasteable consumer workflow YAML templates for
  CLI/binary, container service, library, and hybrid repos
- [ ] 5.4 Add CI check auto-discovery explanation section to `docs/RELEASE_WORKFLOWS.md`
  covering the three-file convention, check name construction, and when to use the
  explicit `ci_checks` override
- [ ] 5.5 Add GoReleaser configuration standards section to `docs/RELEASE_WORKFLOWS.md`
  with copy-pasteable `sboms:` and `signs:` YAML blocks for supply chain compliance
- [ ] 5.6 Add workflow inputs reference tables to `docs/RELEASE_WORKFLOWS.md` for both
  `reusable_release_preflight.yml` and `reusable_release_goreleaser.yml`
- [ ] 5.7 Add migration checklist to `docs/RELEASE_WORKFLOWS.md` with per-item
  verification criteria
- [ ] 5.8 Add troubleshooting section to `docs/RELEASE_WORKFLOWS.md` covering common
  adoption issues (no checks discovered, check name mismatch, re-run behavior, sort -V
  pre-release ordering)
- [ ] 5.9 Add repo adoption status table to `docs/RELEASE_WORKFLOWS.md` listing each
  organization repository with release type, ci_local presence, supply chain status,
  and adoption readiness
- [ ] 5.10 Add cross-reference from `docs/RELEASE_WORKFLOWS.md` to
  `docs/RELEASE_PROCESS.md` clarifying the distinction between adoption (one-time setup)
  and operations (ongoing releases)

## 6. Write release process runbook

- [ ] 6.1 Create `docs/RELEASE_PROCESS.md` with release philosophy statement (simplicity,
  automation, predictability) and overview of the standard release flow
- [ ] 6.2 Add standard release flow section to `docs/RELEASE_PROCESS.md` describing the
  end-to-end process: triggering `workflow_dispatch` with a tag, preflight validation
  phases (tag format, CI gates, security scan, semver ordering, tag creation), build and
  artifact generation, and GitHub Release publication
- [ ] 6.3 Add supply chain expectations section to `docs/RELEASE_PROCESS.md` describing
  the artifacts every release produces (checksums, cosign Sigstore signatures, SBOMs) and
  post-release verification commands (`cosign verify-blob`, SBOM inspection)
- [ ] 6.4 Add release verification steps section to `docs/RELEASE_PROCESS.md` with a
  post-release checklist (GitHub Release page, artifact completeness, signature
  validation)
- [ ] 6.5 Add failure recovery section to `docs/RELEASE_PROCESS.md` covering GoReleaser
  failure after tag creation (safe re-run), preflight validation failures (fix and
  re-trigger), and partial release cleanup
- [ ] 6.6 Add release cadence guidance section to `docs/RELEASE_PROCESS.md` noting that
  cadence is repository-dependent and agreed upon by project maintainers
- [ ] 6.7 Add pre-release and release candidate section to `docs/RELEASE_PROCESS.md`
  covering the `allow_prerelease` input, expected progression (alpha, beta, RC, GA), and
  semver ordering behavior for pre-release tags
- [ ] 6.8 Add roles and responsibilities section to `docs/RELEASE_PROCESS.md` identifying
  who can trigger releases and required permissions
- [ ] 6.9 Add extension points section to `docs/RELEASE_PROCESS.md` listing common
  repo-specific procedures (Fedora packaging, container promotion, Homebrew tap, registry
  mirroring) and guidance on structuring a repo-level release process document that
  references the org-wide standard

## 7. Validation

- [ ] 7.1 Run `yamllint` on `reusable_release_preflight.yml` and
  `reusable_release_goreleaser.yml` per `.yamllint.yml` configuration
- [ ] 7.2 Verify all `uses:` action references in both workflow files are pinned to full
  40-character commit SHAs with inline version comments
- [ ] 7.3 Verify all `run:` steps that reference inputs use `env:` block indirection
  (no direct `${{ inputs.* }}` in run script bodies)
- [ ] 7.4 Verify `docs/RELEASE_WORKFLOWS.md` and `docs/RELEASE_PROCESS.md` follow the
  established org-infra documentation style (ASCII diagrams, input tables, step-by-step
  procedures, troubleshooting)
- [ ] 7.5 Run `make lint` to verify no lint regressions across the repository
- [ ] 7.6 Extract the Python semver comparator into a standalone script
  (`scripts/semver_compare.py`) and test it against the full edge case suite from
  design.md: v1.0.0-alpha < v1.0.0-alpha.1 < v1.0.0-alpha.beta < v1.0.0-beta <
  v1.0.0-beta.2 < v1.0.0-beta.11 < v1.0.0-rc.1 < v1.0.0
- [ ] 7.7 Create representative test workflow fixtures (ci_local.yml with multi-job
  structure, absent files) and verify the CI check discovery step produces expected
  check name lists for each case
- [ ] 7.8 Extract embedded YAML consumer workflow templates from
  `docs/RELEASE_WORKFLOWS.md` and validate with `yamllint`

## 8. Post-Merge

- [ ] 8.1 Tag an org-infra release following the established versioning convention to
  make the reusable workflows available to consumer repos via pinned references

<!-- spec-review: passed -->
