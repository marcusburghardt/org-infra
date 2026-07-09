## 1. Create GitHub App

- [ ] 1.1 Create `complytime-renovate[bot]` GitHub App in org
  settings with repository permissions: `contents: write`,
  `pull-requests: write`. No organization permissions.
- [ ] 1.2 Install the app on: `complyctl`, `complytime`,
  `complytime-providers`, `complytime-collector-components`.
- [ ] 1.3 Add `RENOVATE_APP_CLIENT_ID` and `RENOVATE_APP_PRIVATE_KEY`
  as repository secrets in org-infra.

## 2. Create Shared Renovate Preset

- [x] 2.1 Create `go-toolchain-patches.json` in org-infra repo root
  with `enabledManagers: ["gomod"]` and a three-rule package rule
  pattern: (1) disable all gomod depTypes, (2) re-enable `toolchain`
  with `separateMinorPatch: true`, (3) disable minor/major toolchain
  updates. Include `postUpdateOptions: ["gomodTidy", "gomodVendor"]`,
  `labels: ["dependencies"]`, `commitMessagePrefix: "chore(deps):"`,
  and `dependencyDashboard: false`.

## 3. Create Self-Hosted Global Configuration

- [x] 3.1 Create `renovate-config.js` in org-infra repo root with
  `platform: 'github'`, `onboarding: false`,
  `requireConfig: 'optional'`, explicit `repositories` array
  listing the 4 Go repos, and `globalExtends` referencing
  `github>complytime/org-infra:go-toolchain-patches`.

## 4. Create Runner Workflow

- [x] 4.1 Create `.github/workflows/ci_renovate.yml` with daily
  `schedule` trigger and `workflow_dispatch` trigger (with `dry_run`
  string choice input: `"full"`, `"lookup"`, or `"none"` for normal
  operation). Set workflow-level `permissions: contents: read`.
  Generate JSON run report via `RENOVATE_REPORT_TYPE=file` and
  upload as artifact via `actions/upload-artifact`.
- [x] 4.2 Add checkout step using `actions/checkout` (SHA-pinned).
- [x] 4.3 Add `actions/create-github-app-token` step (SHA-pinned,
  same action already used in `sync_org_repositories.yml`) to
  generate an installation token from `RENOVATE_APP_CLIENT_ID` and
  `RENOVATE_APP_PRIVATE_KEY`.
- [x] 4.4 Add `renovatebot/github-action` step (SHA-pinned) with
  `configurationFile: renovate-config.js` and `token` from the
  app token step.

## 5. Validation

<!--
  Validation categories:
  - CI-automated (5.1-5.3): Run on every PR touching these files.
    yamllint is already in `make lint`. SHA-pin and JSON schema
    checks should be added as CI steps or pre-commit hooks.
  - Manual-integration (5.4-5.7): Run once during initial
    deployment and on significant config changes.
  - Delegated-to-Renovate: Version detection, PR deduplication,
    vendor handling, and patch-only filtering are Renovate's
    responsibility, verified through dry-run observation.
-->

- [x] 5.1 Run `yamllint` on `ci_renovate.yml` to verify YAML
  correctness (CI-automated via `make lint`).
- [x] 5.2 Verify all action `uses:` references in `ci_renovate.yml`
  are SHA-pinned with version comments (no mutable tags).
- [x] 5.3 Validate `go-toolchain-patches.json` against the Renovate
  JSON schema (via `npx --package renovate renovate-config-validator`).
- [ ] 5.4 Run the workflow via `workflow_dispatch` with `dry_run:
  full` and verify Renovate discovers the target repos, detects
  the `toolchain` directive in each `go.mod`, and reports the
  expected behavior (update or no-op) without creating PRs.
  Verify in the dry-run output:
  - Repos with current toolchain show "no updates" (covers:
    already-on-latest scenario).
  - Repos with outdated toolchain show proposed update within
    the same minor series (covers: patch-update scenario).
  - No minor/major version proposals appear (covers:
    patch-only filtering).
  - PR metadata shows conventional commit prefix and
    `dependencies` label (covers: PR metadata scenario).
- [ ] 5.5 Verify single-module discovery: confirm the dry-run output
  from task 5.4 shows Renovate discovering the `go.mod` file in
  `complytime-collector-components/proofwatch/` subdirectory.
- [ ] 5.6 Create a test fixture for live validation: a minimal
  repo (or fork) with an outdated `toolchain` directive in
  `go.mod`. Create two variants:
  - Standard module (no `vendor/` directory)
  - Vendored module (with `vendor/` directory and `-mod=vendor`
    in build commands)
  Temporarily add the test repo to `renovate-config.js`
  `repositories` array. Remove after validation.
- [ ] 5.7 Run the workflow without dry-run targeting the test
  fixture repo(s). Verify:
  - PR is created with correct title (`chore(deps): ...`),
    body (current and target versions), and `dependencies` label.
  - CI triggers automatically on the PR (actor is the App).
  - Vendored variant includes updated `vendor/` directory.
  Clean up: close the test PR, remove the test repo from
  `renovate-config.js`.

## 6. Documentation Updates

- [x] 6.1 Update `AGENTS.md` "Active Technologies" section to include
  `renovatebot/github-action` (SHA-pinned).
- [x] 6.2 Update `AGENTS.md` "Recent Changes" section with an entry
  for this change describing the new centralized Renovate runner
  for Go toolchain patch automation.
- [x] 6.3 Update `CLAUDE.md` "Recent Changes" section with an entry
  for this change.

<!-- spec-review: passed -->
<!-- code-review: passed -->
