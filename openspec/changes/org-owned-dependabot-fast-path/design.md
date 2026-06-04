# Design: org-owned-dependabot-fast-path

## Context

The Dependabot auto-approval pipeline (`ci_dependencies.yml` +
`reusable_dependabot_reviewer.yml` + `reusable_deps_reviewer.yml`) currently
applies a uniform policy to all dependency updates: patch/minor bumps with no
vulnerabilities and a release age of at least 24 hours receive one automated
approval. There is no distinction between third-party and org-owned
dependencies.

This change extends the pipeline established by
`specs/006-robust-dependabot-approval/`.

When org-infra cuts a release, the sync script updates SHA-pinned workflow
references across all consumer repos. Dependabot then creates PRs to bump
these references. Each PR bumps a workflow the organization authored
and released, yet the pipeline treats them identically to an update from
an external, untrusted source.

The current workflow architecture:

```text
ci_dependencies.yml (synced to all repos)
  ├── call_deps_reviewer       → reusable_deps_reviewer.yml (remote)
  ├── call_dependabot_reviewer → reusable_dependabot_reviewer.yml (remote)
  ├── comment_on_dependabot_prs  (parallel with approve job)
  └── approve_dependabot_prs    (parallel with comment job)
```

Key constraint: `ci_dependencies.yml` is synced via `sync-config.yml` to all
org repos except `community` (approximately 10 consumer repos). The reusable
workflows are called remotely at SHA-pinned refs. Changes to reusable workflows
take effect after a release and sync cycle (the sync script pins consumer
workflows to the release SHA). Changes to `ci_dependencies.yml` require the
same sync cycle.

**Note on job parallelism:** The `comment_on_dependabot_prs` and
`approve_dependabot_prs` jobs both depend on `[call_deps_reviewer,
call_dependabot_reviewer]` and execute in parallel. The comment job cannot
observe the outcome of the auto-merge step. The PR comment reports approval
*intent* (based on the same conditions), not post-facto auto-merge results.

## Goals / Non-Goals

**Goals:**

- Automatically detect org-owned dependencies at runtime without configuration.
- Skip the 24-hour release age cooling period for org-owned patch/minor updates
  that pass dependency review.
- Enable GitHub auto-merge on approved org-owned Dependabot PRs so they merge
  as soon as all branch protection rules are satisfied.
- Continue requiring full manual review for major version bumps of org-owned
  dependencies.

**Non-Goals:**

- Cross-organization trust (e.g., trusting `actions/*` or partner orgs).
- Bypassing branch protection rules or merging without approval.
- Changing behavior for third-party dependencies.
- Auto-enabling the "Allow auto-merge" repository setting (admin action).

## Decisions

### D1: Ownership detection via `github.repository_owner`

Compare the first path segment of the dependency name against
`github.repository_owner` (inherited from the caller in `workflow_call`).

```text
dep_name:  "complytime/org-infra/.github/workflows/reusable_security.yml"
dep_owner: "complytime"  (cut -d'/' -f1)
repo_owner: github.repository_owner  ("complytime")
match → org-owned
```

**Case sensitivity:** GitHub normalizes both `github.repository_owner` and
Dependabot's `dependency-name` metadata to lowercase. The comparison is
case-sensitive in bash, which is correct since both inputs are already
normalized by GitHub.

**Alternatives considered:**

- **Hardcoded org name**: Rejected. Breaks for forks, makes the reusable
  workflow non-generic, violates Convention Over Configuration.
- **Configurable allowlist (workflow input)**: Rejected. Adds configuration
  surface, can drift from reality, and creates a security risk if misconfigured.
  The user explicitly requested no configuration.
- **GitHub API org membership check**: Rejected. Over-engineered for this use
  case, adds API calls and latency, requires additional permissions.

**Rationale:** `github.repository_owner` is available in every workflow run,
requires no API calls, and is guaranteed to reflect the actual repository owner.
The comparison is a zero-cost string match.

### D2: Ownership check lives in the reusable workflow

The `is_org_owned` output is produced by `reusable_dependabot_reviewer.yml`,
not `ci_dependencies.yml`.

**Alternatives considered:**

- **Check in ci_dependencies.yml**: Rejected. Would duplicate logic in every
  consumer repo and couldn't be updated without a sync cycle. Placing it in the
  reusable workflow means all consumers get the signal after the next release
  and sync.

**Rationale:** Composability principle -- the reusable workflow already owns
dependency analysis. Adding ownership detection there keeps the signal close
to its source and available to all consumers via the existing sync mechanism.

### D3: Skip release age for org-owned, keep for third-party

For org-owned patch/minor dependencies, the auto-approval conditions are:
1. Risk is not `high` (patch or minor)
2. Dependency review passes
3. Dependency is org-owned

The 24-hour release age check is skipped entirely.

For third-party dependencies, the existing conditions remain unchanged (risk
not high + review passes + age known + age >= 24h).

**Alternatives considered:**

- **Reduced cooling period (e.g., 1 hour)**: Rejected. The cooling period
  exists to catch supply chain attacks on third-party packages. For org-owned
  deps, this threat model does not apply -- there is no meaningful difference
  between 0h and 1h when you control the release process.
- **Same conditions with auto-merge only**: Rejected. Still blocks auto-approval
  when release age detection fails (which was the original bug, now fixed
  separately).

### D4: Auto-merge via `gh pr merge --auto --squash`

After auto-approving an org-owned Dependabot PR, enable GitHub auto-merge using
the `gh` CLI.

**Alternatives considered:**

- **GraphQL `enablePullRequestAutoMerge` mutation via actions/github-script**:
  Viable but requires determining the PR node ID and adds complexity. The `gh`
  CLI is pre-installed on runners and handles this transparently.
- **Direct merge (skip auto-merge, merge immediately)**: Rejected. This would
  bypass branch protection rules. Auto-merge respects all protection rules and
  waits for required status checks and reviews.
- **`gh pr merge --auto` without specifying merge method**: Considered. This
  would inherit the repository's default merge method. However, `--squash` is
  chosen explicitly because Dependabot PRs are single-commit updates and squash
  produces a clean history. If a repository has disabled squash merges, the
  step fails gracefully via `continue-on-error: true` (same as when auto-merge
  is disabled entirely).

**Failure handling:** If auto-merge cannot be enabled (repo setting disabled,
merge method not allowed, insufficient permissions), the `gh` command fails
with a non-zero exit code. This is handled with `continue-on-error: true` so
the approval still stands. The step outcome is visible in the workflow run logs
but is not propagated to the PR comment (see Context note on job parallelism).

### D5: Auto-merge in the existing approval job with `contents: write`

Auto-merge is performed in the existing `approve_dependabot_prs` job, which
gains `contents: write` permission alongside the existing `pull-requests: write`.

**Blast radius:** `ci_dependencies.yml` is synced to approximately 10 consumer
repos. The `contents: write` permission is scoped to a single job
(`approve_dependabot_prs`) which only runs when `github.actor ==
'dependabot[bot]'` and only enables auto-merge when all conditions are met
(org-owned + patch/minor + review passes). This is the minimum permission
required for `gh pr merge --auto`.

**Alternatives considered:**

- **New dedicated job**: Would add workflow complexity and a parallel execution
  branch. Since auto-merge logically follows auto-approval in the same decision
  flow, keeping them together is simpler.
- **Reuse the comment job**: Rejected. The comment job has different permission
  needs (`issues: read`, `pull-requests: write`). Mixing merge permissions with
  the comment job would over-permission that job.

**Security note:** The consumer workflow MUST trigger on `pull_request`, not
`pull_request_target`. The `pull_request_target` trigger runs in the base
branch context with elevated secrets and permissions, which would make
`contents: write` exploitable by any fork.

## Risks / Trade-offs

- **[Risk] `contents: write` propagated to all repos via sync** --
  Mitigation: The permission is scoped to a job that only runs for
  `dependabot[bot]` PRs and only triggers auto-merge under strict conditions
  (org-owned + patch/minor + review passes). The permission scope is the minimum
  required. Downstream repo maintainers are notified via the sync PR
  description.

- **[Risk] Repo does not have "Allow auto-merge" enabled** --
  Mitigation: `gh pr merge --auto` fails gracefully when the setting is
  disabled. The step uses `continue-on-error: true`. The approval still stands.
  Repos can enable "Allow auto-merge" in Settings > General at any time.

- **[Risk] `github.repository_owner` changes if a repo is transferred** --
  Mitigation: This is correct behavior. If a repo is transferred to a different
  org, the ownership check should reflect the new owner. No special handling
  needed.

- **[Risk] Squash merge method not allowed in a repo** --
  Mitigation: `gh pr merge --auto --squash` fails gracefully via
  `continue-on-error: true`. The approval still stands. If this becomes a
  widespread issue, the merge method can be parameterized in a future iteration.

- **[Trade-off] `continue-on-error: true` masks auto-merge failure details** --
  The workflow run shows the step as green even when auto-merge failed.
  Diagnostic information is available in the step logs but not surfaced in the
  PR comment or workflow summary. This is acceptable because auto-merge is a
  convenience optimization, not a critical path.

## Migration Plan

1. Implement changes in both `reusable_dependabot_reviewer.yml` and
   `ci_dependencies.yml`.
2. Cut an org-infra release.
3. Run `sync-org-repositories.py` to push the updated `ci_dependencies.yml`
   to all consumer repos. The sync script pins consumer workflows to the
   release SHA.

**Intermediate state:** Between release and sync completion, the reusable
workflow emits `is_org_owned` but consumer repos still run the old
`ci_dependencies.yml` that does not consume this output. Existing behavior is
preserved during this window. If the sync fails partway, affected repos
continue with old behavior. Re-running the sync is safe (idempotent).

4. Verify "Allow auto-merge" is enabled in target repos (admin action, outside
   this change scope). Use `gh api repos/{owner}/{repo} --jq .allow_auto_merge`
   to audit.
5. Next Dependabot PR wave for org-infra workflow bumps should auto-approve
   and auto-merge where conditions are met.

**Rollback:** Revert changes in order:
1. If the defect is in `reusable_dependabot_reviewer.yml` (detection logic):
   revert and release to take immediate effect via remote call.
2. Revert `ci_dependencies.yml` changes and re-sync to all consumer repos.
3. The `is_org_owned` output becomes unused but harmless.
4. Note: rollback does not retroactively disable auto-merge on PRs where it
   was already enabled. Maintainers would need to manually disable auto-merge
   on in-flight PRs if needed.

## Open Questions

*(none -- all decisions resolved during exploration)*
