## Context

The compliance scan (`ci_compliance.yml` / `reusable_compliance.yml`) runs
daily against a static list of 7 repositories hardcoded in
`.complytime/complytime.yaml`. The organization's canonical repository
inventory lives in `peribolos.yaml` inside the `complytime/.github` public
repository. There is no automated link between the two, so new repositories
are silently excluded from compliance scanning until someone manually updates
the target list.

The sync script (`scripts/sync-org-repositories.py`) already fetches
`peribolos.yaml` via a shallow clone of `complytime/.github` and extracts
repo names from `orgs.<org>.repos`. See proposal.md for full motivation.

## Goals / Non-Goals

**Goals:**

- Detect when `complytime.yaml` targets drift from `peribolos.yaml` repos
- Generate an updated `complytime.yaml` preserving the `policies` and
  `complypacks` sections
- File a PR automatically when drift is detected

**Non-Goals:**

- No per-repo policy overrides
- No changes to `reusable_compliance.yml` or the scan process itself
- No reusable workflow -- this is org-infra-only
- This workflow MUST NOT be listed in `sync-config.yml`

## Decisions

### Decision 1: Separate Python script in `scripts/`

**Choice:** Implement comparison and generation logic in
`scripts/sync-compliance-targets.py`, invoked by the workflow. The new script
accepts pre-fetched file paths via CLI arguments (`--peribolos`, `--complytime`),
so it does not duplicate the clone logic in `sync-org-repositories.py`. Only the
YAML key extraction pattern (`orgs.<org>.repos`) overlaps, which is ~3 lines
of trivial dict navigation not worth abstracting into a shared module.

**Alternative considered:** Inline Python in the workflow `run:` block, as
done in `reusable_compliance.yml` (lines 150-241).

**Rationale:** The constitution requires all code to have tests. A standalone
script can be tested with pytest following the existing pattern
(`tests/test_sync_org_repositories.py`). Inline Python cannot be unit-tested.

### Decision 2: Org-infra-only workflow with `sync_` prefix

**Choice:** `sync_compliance_targets.yml` using the `sync_` prefix per the
constitution's org-infra-only naming convention. This workflow MUST NOT be
added to `sync-config.yml`.

**Alternative considered:** A reusable workflow (`reusable_`) callable by
other orgs with an abstracted repo-source input.

**Rationale:** The scope is deliberately limited to ComplyTime's peribolos
workflow. Other orgs can build their own discovery if needed. Keeping this
simple avoids premature abstraction.

### Decision 3: Read policies from existing `complytime.yaml`

**Choice:** The script reads the `policies` list from the current
`complytime.yaml` and applies those same policies to every generated target.
It does not hardcode policy IDs.

**Alternative considered:** Hardcoding `ampel-bp` in the script.

**Rationale:** If new policies are added to `complytime.yaml` in the future,
the sync script should pick them up automatically. Reading from the existing
file follows the Single Source of Truth principle.

### Decision 4: Target ID and URL convention

**Choice:** Target IDs are derived by prefixing `complytime-` to the repo
name, unless the repo name already starts with `complytime-` (to avoid
double-prefixing like `complytime-complytime-providers`). In that case, the
repo name is used as-is as the ID. URLs follow
`https://github.com/complytime/<repo-name>`. The spec value is always
`builtin:github/branch-rules.yaml`. These patterns are derived from the
existing `complytime.yaml` entries:

| Repo name | Target ID |
|-----------|-----------|
| `complyapi` | `complytime-complyapi` |
| `org-infra` | `complytime-org-infra` |
| `complytime-providers` | `complytime-providers` (no double prefix) |

**Alternative considered:** Making the org name and URL pattern configurable
via CLI arguments.

**Rationale:** This is an org-infra-only script, not a reusable tool. The
org name is already implied by the peribolos source. If genericity is needed
later, CLI arguments can be added.

### Decision 5: Deterministic branch name for PR deduplication

**Choice:** The workflow uses a fixed branch name
(`sync/compliance-targets`) so that repeated runs update the same PR
rather than creating duplicates. Pushing new commits to the branch
automatically updates any open PR pointing at it.

**Alternative considered:** Date-stamped branches
(e.g., `sync/compliance-targets-2026-09-03`).

**Rationale:** A fixed branch means the workflow is idempotent. If drift
persists across multiple days, the existing PR is updated with the latest
diff. This avoids PR spam. The workflow checks if a PR already exists for
the branch before calling `gh pr create`.

### Decision 6: `GITHUB_TOKEN` for both clone and PR

**Choice:** Use the default `GITHUB_TOKEN` for cloning `complytime/.github`
(public repo) and for creating the PR on org-infra.

**Alternative considered:** GitHub App token (as used by
`sync_org_repositories.yml`).

**Rationale:** The `.github` repo is public, so no special auth is needed
for the clone. `GITHUB_TOKEN` with `contents: write` and
`pull-requests: write` is sufficient for creating a PR on the same repo.
No App token overhead needed.

### Decision 7: Daily schedule offset from compliance scan

**Choice:** Schedule the sync workflow to run before the compliance scan
(e.g., `cron: "0 22 * * *"` vs the scan's `cron: "0 0 * * *"`).

**Alternative considered:** Running at the same time or on the same trigger.

**Rationale:** Running the sync first means the PR is available for
next-business-day review. The compliance scan continues with the existing
targets until the PR is merged. This separation keeps the two concerns
(drift detection vs. compliance scanning) independent.

### Decision 8: Output written to separate path

**Choice:** The script writes the updated `complytime.yaml` to a separate
output path (`--output` argument) rather than modifying the input file
in-place.

**Alternative considered:** In-place modification of `complytime.yaml`.

**Rationale:** Writing to a separate path ensures the original file is
preserved if the script fails mid-generation (disk full, YAML serialization
error). The workflow copies the output to the correct location only after
the script exits successfully.

### Decision 9: Explicit `--exclude` CLI argument

**Choice:** The script accepts `--exclude` as a comma-separated list of repo
names to remove from both the peribolos and complytime sets before comparison.
The workflow passes `--exclude ".github,complyscribe"` to skip repos that
should not have compliance targets.

**Alternative considered:** No exclusion mechanism (every repo in peribolos
gets a target).

**Rationale:** Some repos in peribolos are not suitable for branch protection
scanning: `.github` is the org-level config repo managed manually by design,
and `complyscribe` is archived. Without an exclusion mechanism the sync would
generate targets for these repos on every run, creating noise PRs that
maintainers would always reject. Keeping the list as an explicit CLI argument
in the workflow file (rather than a config file or auto-discovery) keeps it
simple and visible.

## Risks / Trade-offs

- **[Risk] Peribolos includes repos that should not be scanned** (e.g.,
  archived repos, special-purpose repos with no branches to protect) --
  Mitigation: The `--exclude` argument filters known exceptions. For unknown
  cases the PR goes through human review. Maintainers can add repos to the
  exclusion list or reject the PR.
- **[Risk] Shallow clone of `.github` fails** (network issues, repo
  renamed) -- Mitigation: The workflow step fails and the run is marked
  as failed. No PR is created. The daily schedule retries next day.
- **[Risk] `complytime.yaml` format changes upstream** (complyctl evolves
  the config schema) -- Mitigation: The script preserves `policies` and
  `complypacks` sections verbatim and only regenerates `targets`. Schema
  changes to those sections would not be affected.
- **[Risk] `complytime.yaml` does not yet exist** -- Mitigation: The script
  exits with status 1 and a clear error message. The workflow fails without
  creating a PR. This is expected: the compliance config must exist before
  sync can operate on it.
