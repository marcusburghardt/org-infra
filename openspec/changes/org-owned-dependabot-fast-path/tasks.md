# Tasks: org-owned-dependabot-fast-path

## 1. Org-Ownership Detection (reusable workflow)

- [x] 1.1 Add `is_org_owned` output to the `workflow_call` outputs block in `.github/workflows/reusable_dependabot_reviewer.yml`
- [x] 1.2 Add `REPO_OWNER: "${{ github.repository_owner }}"` to the step env of a new `Detect Org Ownership` step in `.github/workflows/reusable_dependabot_reviewer.yml`
- [x] 1.3 Add the `Detect Org Ownership` step (after `get_dep_info`) in `.github/workflows/reusable_dependabot_reviewer.yml` that extracts the first path segment of `DEP_NAME` via `cut -d'/' -f1`, compares it to `REPO_OWNER`, and outputs `is_org_owned` (`true`/`false`). Default to `false` when `DEP_NAME` is empty
- [x] 1.4 Wire the `is_org_owned` step output through the job outputs and `workflow_call` outputs in `.github/workflows/reusable_dependabot_reviewer.yml`

## 2. Approval Logic Changes (consumer workflow)

- [x] 2.1 Add `contents: write` permission to the `approve_dependabot_prs` job in `.github/workflows/ci_dependencies.yml` (alongside existing `pull-requests: write`)
- [x] 2.2 Add the `is_org_owned` output consumption from `call_dependabot_reviewer` in `.github/workflows/ci_dependencies.yml`
- [x] 2.3 Update approval condition in `ci_dependencies.yml` with compound OR:
  (a) third-party path (risk != high, review passes, age known, age >= 24h) or
  (b) org-owned path (risk != high, review passes, no age requirement)
- [x] 2.4 Update the approval review body message in the `actions/github-script` step to include the ownership signal (org-owned vs third-party) and indicate whether release age was checked or bypassed
- [x] 2.5 Add a new step `Enable Auto-merge for Org-owned` in the `approve_dependabot_prs` job in `.github/workflows/ci_dependencies.yml` that runs `gh pr merge --auto --squash` conditional on the auto-approve step succeeding (`steps.<approve-step-id>.outcome == 'success'`) AND `is_org_owned == 'true'`. Use `continue-on-error: true` and `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`

## 3. PR Comment Update (consumer workflow)

- [x] 3.1 Update the comment template in the `comment_on_dependabot_prs` job in `.github/workflows/ci_dependencies.yml` to add an `Ownership` row showing `org-owned` or `third-party`
- [x] 3.2 Update the `Auto-approval` line in the comment template in `.github/workflows/ci_dependencies.yml` to reflect the approval intent: auto-approved with auto-merge requested (org-owned), auto-approved (third-party), or manual review required. The comment reports intent based on conditions, not post-facto auto-merge outcome

## 4. Validation

- [x] 4.1 Run `make lint` to verify all YAML changes pass yamllint
- [x] 4.2 Verify all action `uses:` references in modified files remain SHA-pinned with inline version comments
- [x] 4.3 Review the complete diff to confirm: (a) third-party approval `if:` expression still contains `release_age_hours != '-1'` and `>= fromJSON(env.MIN_RELEASE_AGE_HOURS)`, (b) no permissions are broader than required, (c) workflow trigger remains `pull_request` (not `pull_request_target`)
- [x] 4.4 Document the `contents: write` permission addition and its sync impact in the PR description
<!-- spec-review: passed -->
<!-- code-review: passed -->
