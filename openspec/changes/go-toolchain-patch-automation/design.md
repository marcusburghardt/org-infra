## Context

The complytime organization maintains multiple Go repositories
(complyctl, complytime, complytime-providers,
complytime-collector-components) whose Go toolchain versions must be
kept current for security. Dependabot does not support bumping the
`toolchain` directive in `go.mod` (upstream issue
[dependabot-core#13520](https://github.com/dependabot/dependabot-core/issues/13520),
open since Nov 2025).

The org-infra repository provides centralized CI/CD infrastructure
through reusable GitHub Actions workflows synced to consumer repos
via `sync-config.yml` and `sync_org_repositories.py`. A previous
custom workflow in complyctl (`vuln_check_fix.yml`) solved this
problem but was removed during the org-infra migration.

[Renovate](https://github.com/renovatebot/renovate) (AGPL-3.0,
21.8k stars, backed by Mend.io) has native first-class support for
Go toolchain bumping via its `gomod` manager. It distinguishes the
`toolchain` depType from `golang` (go directive) and supports
patch-only filtering via a three-rule preset pattern,
`postUpdateOptions: ["gomodTidy", "gomodVendor"]`, and
`separateMinorPatch` for independent patch/minor tracking. Running
Renovate via `renovatebot/github-action` in a centralized org-infra
workflow avoids the broad permissions of the Mend-hosted app while
delegating version detection, PR management, and idempotent updates
to a mature, actively maintained tool.

## Goals / Non-Goals

**Goals:**

- Automate Go toolchain patch updates for all Go repositories in the
  organization through a single org-infra change.
- Use Renovate via GitHub Actions with a dedicated GitHub App scoped
  to minimal permissions (`contents:write`, `pull-requests:write`).
- Require zero manual changes or config files in consumer
  repositories.
- Restrict automated updates to patch versions within the current
  minor series.
- Ensure PRs trigger CI automatically (App token, not
  `GITHUB_TOKEN`).

**Non-Goals:**

- Automating Go minor or major version bumps.
- Replacing Dependabot for Go module dependency management.
- Adopting the Mend-hosted Renovate App (broad permissions
  incompatible with org security posture).
- Enabling Renovate for non-Go dependency types (scoped to
  `gomod` manager, `toolchain` depType only).
- Detecting specific CVEs in Go patch releases (all patches in the
  minor series are applied).

## Decisions

### D1: Renovate via GitHub Action (centralized runner)

Run Renovate as a centralized scheduled workflow in org-infra using
`renovatebot/github-action`, rather than the Mend-hosted app or a
custom reusable workflow.

**Rationale:** Running Renovate via GitHub Actions provides the same
Go toolchain update capability as the hosted app, but authenticates
with a GitHub App you control -- scoped to only `contents:write` and
`pull-requests:write`. The hosted app requires 8 permission types
including `Workflows: Read & Write`, which would allow modification
of CI pipeline files and potential secret exfiltration via triggered
workflow runs. This is incompatible with the org's principle of least
privilege posture (e.g., `complytime-repo-sync[bot]` uses only 2
permissions).

**Alternative rejected:** Mend-hosted Renovate app. Permissions
cannot be scoped down -- you accept all 8 or none. The
`Workflows: RW` permission is a supply chain risk for repos that
store secrets (QUAY_PASSWORD, SYNC_APP_PRIVATE_KEY, OIDC tokens).

**Alternative rejected:** Custom reusable workflow with shell
scripting. Requires ~60 lines of custom version detection, `go.mod`
editing, vendor handling, and PR creation logic that Renovate handles
natively. Also requires a GitHub App for CI triggers regardless,
making Renovate's built-in PR management a net reduction in
maintained code.

### D2: Dedicated GitHub App with minimal permissions

Create `complytime-renovate[bot]` with only `contents:write` and
`pull-requests:write`, installed on the 4 Go repositories.

**Rationale:** A dedicated app follows the same pattern as
`complytime-repo-sync[bot]` (single purpose, minimal permissions).
App-created PRs trigger CI automatically, eliminating the
`GITHUB_TOKEN` limitation where maintainers must close/reopen PRs.
The app is installed only on repos that need it, limiting blast
radius.

**Alternative rejected:** Reusing the sync app
(`complytime-repo-sync[bot]`). The sync app has the right
permissions but serves a different purpose (cross-repo file sync).
Sharing credentials between two unrelated automation systems
violates the principle of single responsibility and widens the blast
radius if either system is compromised.

**Alternative rejected:** Org-level secrets for a shared app.
Would make app credentials accessible to any workflow in any org
repo, not just the Renovate runner.

### D3: Centralized runner in org-infra (not distributed)

Run Renovate from a single workflow in org-infra that targets all
Go repos, rather than syncing a Renovate workflow to each consumer
repo.

**Rationale:** Mirrors the `sync_org_repositories.yml` pattern --
a centralized workflow that operates on consumer repos. Config
changes happen in one place (org-infra). Adding a new Go repo
requires adding one line to `renovate-config.js`. Consumer repos
need zero files, zero secrets, zero configuration.

**Alternative rejected:** Syncing a Renovate workflow and config to
each consumer repo via sync-config. Would require syncing
`renovate.json` + a runner workflow to every Go repo, plus storing
App secrets as org-level secrets (broader exposure). More sync
surface for no benefit.

### D4: globalExtends for preset distribution

Use the self-hosted `globalExtends` option to force the shared
preset on all managed repos, rather than requiring a `renovate.json`
in each consumer repo.

**Rationale:** `globalExtends` is a self-hosted-only option that
applies presets regardless of whether the target repo has a local
`renovate.json`. Combined with `onboarding: false` and
`requireConfig: 'optional'`, consumer repos need zero Renovate
artifacts. The preset is defined once in org-infra
(`go-toolchain-patches.json`) and referenced by the global config.

**Alternative rejected:** Syncing `renovate.json` to consumer repos.
Adds sync complexity and creates a question of whether local config
can override the preset (with `globalExtends`, the answer is clear:
no, unless the repo uses `force`).

### D5: Explicit repository list (not autodiscover)

List target repositories explicitly in `renovate-config.js` rather
than using Renovate's `autodiscover` mode.

**Rationale:** Explicit listing matches the org's declarative
configuration style (sync-config.yml lists repos explicitly).
Autodiscover could pick up repos not intended for Go toolchain
management. Adding a new Go repo is a one-line change in the config.

**Alternative rejected:** `autodiscover: true` with
`autodiscoverFilter`. Could inadvertently target repos without
`go.mod`, non-Go repos with a `go.mod` in a subdirectory, or repos
still in early setup. Explicit listing is safer and more predictable.

## Risks / Trade-offs

**[Risk] Renovate is a new tool dependency** -- Introduces
`renovatebot/github-action` (AGPL-3.0) as a CI dependency.
Mitigation: Renovate runs as a service in GitHub Actions -- it is
not embedded in org code and does not affect the Apache-2.0 license
of managed repositories. The action reference is SHA-pinned per org
conventions. Renovate has 21.8k+ stars, 1.5k+ contributors, and
is backed by Mend.io (enterprise security vendor).

**[Risk] Self-hosted Renovate runner costs** -- The centralized
workflow consumes GitHub Actions runner minutes.
Mitigation: A single daily run scanning 4 repos for one dependency
type takes ~2-5 minutes. At ~150 minutes/month, this is negligible
relative to existing CI usage.

**[Risk] Renovate version updates** -- The `renovatebot/github-action`
reference must be kept current.
Mitigation: Dependabot already manages GitHub Actions pins in
org-infra. The Renovate action will be updated via the existing
dependabot workflow like any other action.

**[Risk] Vendor directory handling** -- 2 of 4 target repos
(`complyctl`, `complytime-providers`) use Go module vendoring with
`-mod=vendor` in their build and test commands. Renovate PRs that
update `go.mod` without regenerating `vendor/` would fail CI.
Mitigation: The shared preset includes `postUpdateOptions:
["gomodTidy", "gomodVendor"]`. The `gomodVendor` option runs
`go mod vendor` after updates, keeping the vendor directory in sync.
This only executes when there is an actual update and only affects
repos that have a `vendor/` directory. Dependabot already performs
the equivalent for its own `gomod` PRs.

**[Trade-off] Parallel dependency management** -- Renovate runs
alongside Dependabot, creating two systems for dependency updates.
Mitigation: Scoping Renovate to `enabledManagers: ["gomod"]` with
all depTypes disabled except `toolchain` patches ensures zero
overlap with Dependabot. Each system handles what the other cannot.

## Resolved Questions

- **Vendoring**: `complyctl` and `complytime-providers` use vendoring.
  `complytime` and `complytime-collector-components` do not. The
  preset includes `gomodVendor` in `postUpdateOptions` to ensure
  PRs pass CI on vendored repos. This is a fire-and-forget config
  option -- it only runs when there is an update and only affects
  repos with a `vendor/` directory.
- **Dependency Dashboard**: Disabled (`dependencyDashboard: false`).
  The Dashboard creates one permanently-open issue per repo showing
  pending update state. With exactly one narrow dependency type
  (toolchain patches) across 4 repos, it adds no value and creates
  noise. Approval workflows are not needed, and Renovate re-creates
  PRs for new versions on its regular schedule regardless.
- **Three-rule preset pattern**: The preset uses three package rules
  instead of one. A single rule combining `matchUpdateTypes: ["patch"]`
  with `enabled: true` fails because `matchUpdateTypes` requires a
  version lookup that only runs for enabled deps -- a chicken-and-egg
  problem. The three-rule pattern: (1) disable all gomod, (2) re-enable
  toolchain with `separateMinorPatch: true`, (3) disable minor/major
  toolchain updates. Validated via local dry-run: Renovate correctly
  proposes patch updates and suppresses minor/major.
- **Run report artifact**: Each workflow run generates a JSON report
  via `RENOVATE_REPORT_TYPE=file` and uploads it as a GitHub Actions
  artifact (30-day retention). The report contains dependency versions,
  update proposals, and branch/PR decisions -- no sensitive data.
- **Token permission scoping**: The `actions/create-github-app-token`
  step explicitly sets `permission-contents: write` and
  `permission-pull-requests: write`, matching the established
  `sync_org_repositories.yml` pattern. This ensures the token cannot
  silently inherit additional permissions if the App is modified later.
