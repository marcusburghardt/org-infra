## Context

The ComplyTime and Unbound Force organizations maintain 7 Go repositories with
GoReleaser-based binary release workflows and 3 repositories with container-only release
pipelines. Each binary release repo independently implements preflight validation, Go
setup, supply chain tooling installation, and GoReleaser execution. This has led to:

- **Action version drift**: checkout ranges from v4.2.2 to v7.0.0, setup-go from v5.6.0
  to v6.5.0, goreleaser-action from v7.2.2 to v7.2.3 across repos.
- **Inconsistent supply chain**: 3 of 7 GoReleaser repos (uf-gaze, uf-dewey,
  uf-replicator) lack cosign signing and SBOM generation entirely.
- **Hardcoded CI check names**: Each preflight hardcodes repository-specific check names
  (e.g., `"unit-test"`, `"Build and test"`, `"Unit + Integration Tests (Go 1.24)"`).
  Renaming a CI workflow job silently breaks the release without clear feedback.
- **Two functional bugs** in complyctl's preflight (complytime/complyctl#654):
  tag uniqueness check blocks re-runs; `sort -V` inverts pre-release semver ordering.
- **No preflight for container repos**: Container-only repos (complypack, complybeacon,
  gemara-content-service) have no release validation gates.

The existing org-infra reusable workflow inventory covers container publishing, image
scanning, signing/verification, and registry promotion. The release pipeline (preflight
+ GoReleaser) is the remaining gap.

### Current State Across Repos

| Repository | Trigger | Preflight | Supply Chain | CI Discovery |
|---|---|---|---|---|
| complyctl | dispatch | Yes (buggy) | cosign + syft | Hardcoded 3 checks |
| complytime-providers | dispatch | Yes (smart re-run) | cosign + syft | Hardcoded 2 checks |
| uf-unbound-force | dispatch | Yes (+ security gate) | cosign + syft | Hardcoded 2+2 checks |
| uf-gaze | dispatch | Yes | None | Hardcoded 3 checks |
| uf-dewey | tag push | None | None | None |
| uf-replicator | tag push | None | None | None |
| c2p-go | tag push + dispatch | None | cosign (different format) | None |

## Goals / Non-Goals

**Goals:**

- Provide a single reusable preflight workflow that any Go project (binary, container, or
  library) can call with minimal configuration.
- Enforce supply chain artifacts (cosign signatures, syft SBOMs) as non-negotiable
  defaults in the GoReleaser workflow.
- Eliminate hardcoded CI check names via file-based auto-discovery from the repo's own
  workflow files.
- Fix the two known preflight bugs (re-run blocking, pre-release ordering).
- Provide adoption documentation that allows maintainers to migrate gradually.
- Keep the workflows org-agnostic so both ComplyTime and Unbound Force repos can use them.

**Non-Goals:**

- macOS code signing and notarization (stays in UF repos).
- GoReleaser configuration templating or enforcement.
- Automated migration of existing release workflows in consuming repos.
- Reusable workflow for GitHub Release creation without GoReleaser.

## Decisions

### Decision 1: File-based CI check discovery (not branch protection API)

The preflight discovers required CI checks by reading workflow files from the checkout:
`ci_local.yml`, `ci_checks.yml`, and `ci_security.yml`.

**Alternatives considered:**

- **Branch protection API** (`GET .../branches/main/protection/required_status_checks`):
  Elegant and zero-config, but requires `administration: read` permission. This broadens
  the permission scope beyond what current release workflows need. Also fails silently if
  branch protection is not configured (newer repos, forks).
- **Hardcoded check names as input**: The current approach in all repos. Requires
  maintenance when CI workflows are renamed. Every repo must know its own check names.
- **Convention-based pattern matching** (e.g., all checks containing "test"): Fragile.
  Does not capture the team's actual intent about which checks are release gates.

**Rationale:** File-based discovery requires no additional permissions, adapts
automatically when `ci_local.yml` job names change, and leverages the fact that
`ci_checks.yml` and `ci_security.yml` are synced from org-infra with predictable
structure. For repos with non-standard test workflows, an explicit `ci_checks` input
override provides an escape hatch.

### Decision 2: Three-file discovery convention (ci_local, ci_checks, ci_security)

The auto-discovery reads exactly three workflow files:

| File | Source | Check name construction |
|---|---|---|
| `ci_checks.yml` | Synced from org-infra | Known by convention: `CI / Standardized CI / Run linters` |
| `ci_security.yml` | Synced from org-infra | Pattern match: at least one `Security Checks / OSV-Scanner / *` must pass |
| `ci_local.yml` | Repo-specific | Parsed with `yq`: `<workflow name> / <job name>` for each job |

**Alternatives considered:**

- **Scan all `ci_*.yml` files**: Too broad. Would include `ci_dependencies.yml`,
  `ci_crapload.yml`, `ci_scheduled.yml` -- checks that are informational or PR-only and
  should not gate releases.
- **Single file with a "release-gate" marker**: Requires repos to annotate their
  workflows with custom metadata. Convention-breaking and adoption friction.
- **Discover from branch protection + supplement with file scan**: Combines two
  mechanisms. More complex, still needs `administration: read`.

**Rationale:** The three files represent the three concerns that should gate a release:
tests pass (ci_local), code quality is clean (ci_checks), and no known vulnerabilities
(ci_security). Synced files have predictable check names. Repo-specific files are parsed
dynamically. If a file is absent, its gate is skipped gracefully.

### Decision 3: Semver-aware comparator for pre-release ordering

Replace `sort -V` with a Python-based semver comparator when either the new tag or the
latest existing tag contains a pre-release suffix.

**Alternatives considered:**

- **Keep `sort -V` and reject pre-release tags**: Simple, but complyctl already uses
  pre-release tags (`v1.0.0-beta.0`, `v1.0.0-alpha.0`) and the `allow_prerelease` input
  exists to support this. Rejecting pre-releases would be a regression.
- **Node.js `npx semver`**: Correct implementation, but adds ~2s download latency per
  run and introduces a runtime dependency on npm registry availability.
- **Go `golang.org/x/mod/semver`**: Gold standard for Go projects, but Go is not
  installed in the preflight job (it is set up in the GoReleaser job). Installing Go
  just for one comparison is disproportionate.
- **Bash function**: Zero dependencies but ~20 lines of string parsing with edge case
  risk. Pre-release comparison rules (dot-separated identifiers, numeric vs alphanumeric
  precedence) are non-trivial.

**Rationale:** Python 3 is pre-installed on all GitHub-hosted runners. A ~15-line inline
script can implement semver comparison correctly using only stdlib. The hybrid approach
(use `sort -V` for the common X.Y.Z case, invoke Python only when pre-release suffixes
are present) minimizes overhead.

### Decision 4: Smart tag uniqueness with re-run resilience

Adopt the complytime-providers pattern: dereference annotated tags to check if an
existing tag points at HEAD (re-run) vs. a different commit (genuine conflict).

**Alternatives considered:**

- **Simple uniqueness check** (complyctl pattern): `exit 1` if tag exists. Blocks
  legitimate re-runs after partial failures. The tag creation step's idempotency guard
  becomes dead code.
- **Remove uniqueness check entirely**: Relies on `git push` rejection for duplicates.
  Loses the clear error message explaining why the release failed. Also allows tagging a
  different commit with the same version.
- **Always delete and recreate the tag**: Destructive. Violates tag immutability
  expectations and could confuse downstream consumers who fetched the original tag.

**Rationale:** The complytime-providers approach is both safe and ergonomic. Re-runs
after GoReleaser failure just work. Genuine conflicts (same tag on a different commit)
are caught with a clear error. The steps that become redundant on re-run (ordering
verification, unreleased commits check) are skipped via the `tag_exists_at_head` output.

### Decision 5: Supply chain enforced by default in GoReleaser workflow

The `reusable_release_goreleaser.yml` workflow always installs cosign and syft,
regardless of whether the repo's `.goreleaser.yaml` uses them.

**Alternatives considered:**

- **Make cosign/syft installation optional via inputs**: Allows repos to opt out of
  supply chain artifacts. Contradicts the constitution's requirement that all release
  artifacts include SLSA provenance and SBOMs.
- **Validate `.goreleaser.yaml` for supply chain sections**: Would require parsing the
  GoReleaser config in the workflow. Complex and brittle.

**Rationale:** Installing cosign and syft is cheap (~5s combined). If a
`.goreleaser.yaml` does not reference them, they are simply unused. If it does, they are
available. This makes supply chain the path of least resistance: repos that adopt the
reusable workflow and follow the documented GoReleaser config standards automatically
get full supply chain coverage.

### Decision 6: API error handling separated from check-not-found

The CI verification step separates API call errors from check filtering, using
`--paginate` for repos with many checks and surfacing rate limit or network errors
explicitly.

**Alternatives considered:**

- **Keep `2>/dev/null` pattern**: Current approach. Masks API failures as "check not
  found". A rate-limited release attempt produces a misleading error.
- **Retry on API failure**: More robust but adds complexity (backoff logic, retry
  limits). Overkill for a release workflow that runs infrequently.

**Rationale:** Separating the API call from the jq filtering is a minimal change that
eliminates the most common source of confusion. Pagination (`--paginate`) handles repos
with 30+ check runs that the current `head -1` approach could silently miss.

### Decision 7: Adoption documentation as a first-class deliverable

A `docs/RELEASE_WORKFLOWS.md` file provides per-repo-type adoption guides, consumer
workflow templates, and a migration checklist.

**Alternatives considered:**

- **Inline documentation in the workflow files**: YAML comments are limited. Cannot
  include diagrams, tables, or step-by-step procedures.
- **README section**: The README is already dense. A dedicated doc follows the existing
  pattern (`COMPLYPACK_PUBLISH.md`, `RENOVATE_GO_TOOLCHAIN.md`).
- **External wiki or Confluence**: Breaks the "docs live with code" principle. Not
  version-controlled with the workflows.

**Rationale:** The existing org-infra documentation pattern uses dedicated Markdown files
in `docs/` for each major workflow or infrastructure feature. The adoption guide follows
this established convention and provides copy-pasteable consumer workflow templates that
maintainers can use directly.

### Decision 8: Two-document split -- adoption guide vs. release process runbook

The documentation is split into two complementary documents:

- `docs/RELEASE_WORKFLOWS.md` -- **Adoption guide**: How to set up the reusable
  workflows in your repo (one-time migration, aimed at workflow maintainers).
- `docs/RELEASE_PROCESS.md` -- **Release process runbook**: How to perform a release
  using the standard process (ongoing operations, aimed at release operators).

The release process doc captures the generic, repo-agnostic release flow (trigger the
workflow, verify preflight, check artifacts, verify supply chain). Each repository
extends this locally with repo-specific procedures (Fedora packaging for complyctl,
Quay promotion for complybeacon, Homebrew tap for UF tools).

**Alternatives considered:**

- **Single document combining both**: Mixes setup instructions with operational
  procedures. Operators performing releases do not need adoption instructions; maintainers
  setting up workflows do not need the release runbook. A combined doc serves neither
  audience well.
- **Release process in each repo only, no org-wide standard**: The current state.
  complyctl has a detailed release process doc; most other repos have none. Leads to
  inconsistent operator experience and undocumented procedures.
- **Sync the release process doc to all repos**: Would overwrite repo-specific sections.
  The release process doc is a reference, not a template to be synced. Repos reference
  the org-infra canonical doc and maintain their own extensions.

**Rationale:** The two-doc split follows the same pattern as the constitution: an
org-wide canonical document in org-infra that repos extend locally without conflicting.
The release process doc covers the common flow; each repo adds repo-specific sections
(Fedora packaging, container promotion, Homebrew, etc.) in its own
`docs/RELEASE_PROCESS.md` that references the org-infra doc as the base authority.

## Risks / Trade-offs

- **[Risk] `yq` availability on GitHub runners** -- The `ci_local.yml` parsing depends on
  `yq` (mikefarah version) being pre-installed on `ubuntu-latest` runners. GitHub has
  included it since late 2022, but runner image changes could remove it.
  Mitigation: Add a `yq` installation step as a fallback if the binary is not found.
  Alternatively, use `python3 -c "import yaml; ..."` (stdlib `yaml` is not available, but
  `pip install pyyaml` is trivial). Monitor GitHub runner release notes.

- **[Risk] Synced workflow structure changes** -- The auto-discovery assumes
  `ci_checks.yml` produces the check name `CI / Standardized CI / Run linters`. If the
  synced workflow's `name:` field or job names change, the preflight would look for the
  wrong check name.
  Mitigation: Both the synced workflows and the reusable preflight live in org-infra.
  Changes to `ci_checks.yml` or `ci_security.yml` structure would be made in the same
  repo and can be coordinated in the same PR.

- **[Risk] Repos without ci_local.yml get no test gate** -- Repos that use custom test
  workflow names (e.g., complyctl with `unit_test.yml`, `e2e_test.yml`,
  `integration_test.yml`) would have no auto-discovered test checks unless they provide
  the `ci_checks` override input.
  Mitigation: The adoption guide documents this clearly and recommends either using the
  override or consolidating into `ci_local.yml`. The preflight warns (does not fail) when
  zero checks are discovered.

- **[Risk] Pre-release semver comparison edge cases** -- The Python comparator must
  handle all semver pre-release ordering rules (dot-separated identifiers, numeric vs.
  alphanumeric precedence per spec section 11). A naive implementation could miss edge
  cases.
  Mitigation: Implement the full semver 2.0.0 comparison algorithm. Add test cases for
  known edge cases (`v1.0.0-alpha < v1.0.0-alpha.1 < v1.0.0-alpha.beta < v1.0.0-beta <
  v1.0.0-beta.2 < v1.0.0-beta.11 < v1.0.0-rc.1 < v1.0.0`).

- **[Trade-off] Two reusable workflows vs. one** -- Splitting preflight and GoReleaser
  into separate workflows adds a `needs:` dependency in consumer workflows but allows
  container-only and library repos to use the preflight without the GoReleaser job. The
  composability benefit outweighs the minor complexity of chaining two workflow calls.

## Migration Plan

Adoption is incremental and per-repo. No repo is forced to migrate.

### Phase 1: Ship the reusable workflows (this change)

Create `reusable_release_preflight.yml`, `reusable_release_goreleaser.yml`,
`docs/RELEASE_WORKFLOWS.md`, and `docs/RELEASE_PROCESS.md` in org-infra. Tag an
org-infra release so consuming repos can pin to a specific version.

### Phase 2: Early adopters

Repos with `ci_local.yml` already in place (complytime-providers, uf-unbound-force) can
adopt immediately with zero configuration. Replace their inline preflight + release jobs
with two reusable workflow calls.

### Phase 3: Override adopters

Repos with custom test workflows (complyctl) adopt using the `ci_checks` input override
while planning a migration to `ci_local.yml`.

### Phase 4: Container and library repos

Container-only repos (complypack, complybeacon, gemara-content-service) add the
preflight before their existing container pipeline. Library repos (oscal-sdk-go) add the
preflight before a simple GitHub Release step.

### Phase 5: Convention convergence

Remaining repos consolidate test workflows into `ci_local.yml`, enabling full
auto-discovery and dropping the `ci_checks` override.

### Rollback

Each consuming repo controls its own `release.yml`. Rolling back is a single-commit
revert that restores the inline preflight and release jobs. The reusable workflows in
org-infra have no side effects when not called.

## Resolved Questions

- **Step summary report**: DEFERRED. A step summary with a human-readable gate report
  would improve operator experience but adds scope. This will be addressed as a
  follow-up enhancement after the core workflows are validated in production.
- **`pre_build_commands` input**: REJECTED. GoReleaser's `before.hooks` in
  `.goreleaser.yaml` already handles pre-build steps (e.g., `go mod tidy`,
  `go mod vendor`, `make build-plugins`). Adding a workflow-level input would duplicate
  this capability and create confusion about which mechanism takes precedence.
