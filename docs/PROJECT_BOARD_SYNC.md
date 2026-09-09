# Compliance Automation Project Board Sync

Automates keeping the private
[Compliance Automation planning](https://github.com/orgs/complytime/projects/14)
board populated with open issues and pull requests from:

| Organization | Selection |
|---|---|
| `Agentic-SSDLC` | All repositories |
| `complytime` | All repositories **except** `roadmap` and `complytime` |
| `unbound-force` | All repositories |

Archived repositories are skipped by default.

## What the automation does

On a 5-minute schedule (GitHub Actions' shortest interval; 1-minute cron is
not honored) and via manual `workflow_dispatch`. Scheduled runs can still be
delayed under GitHub load:

1. Discovers repositories from `project-sync-config.yml`
2. Links same-org repositories to project `#14` (idempotent). Cross-org repos
   cannot be linked (GitHub restriction) but their issues/PRs still sync.
3. Collects open issues and open PRs
4. Adds any missing items to the board with **Status = Backlog** and
   **Organization** set from the source GitHub org (`Agentic-SSDLC`,
   `complytime`, or `unbound-force`). Organization updates are best-effort:
   a field-write failure does not undo the board add.
5. Backfills **Organization** on existing board items that are unset or
   incorrect (for example items added manually). Default `--backfill-org auto`
   skips that extra board listing when this tick already set Organization on
   newly added items. Quiet ticks still backfill. Pass `--backfill-org always`
   (or the workflow input) to force a full walk.
6. Copies **Priority** (and empty **Review priority**) onto PRs from linked
   issues (`Fixes` / `Closes` / Development sidebar). Uses the issue's project
   Priority; if several issues are linked, the highest rank wins
   (Urgent > High > Medium > Low). If the same issue appears twice on the
   board, the highest Priority is kept. Warns when a PR has more closing
   issues than one GraphQL page. PRs with no linked issue, or whose issues
   have no Priority, stay unset — there is no default. Values already set on
   the PR are left alone.
7. Moves items in **Ready for Review** to **In Review** when a non-author
   human comments on the issue/PR, or submits a PR review, at or after the
   Status last changed. The since-boundary is the Status field's `updatedAt`
   (when this item's Status option last changed, not other board metadata).
   Author comments, bots (`[bot]`, `authorAssociation: BOT`), and
   unsubmitted (`PENDING`) reviews are ignored. Detected on the same
   5-minute tick as the rest of the sync.

The workflow lives only in `org-infra` (it is **not** synced out to consumer repos).
A new PR is picked up on the next 5-minute tick (GitHub does not let this
org-infra workflow subscribe to `pull_request` events in other repositories).

| File | Role |
|---|---|
| `project-sync-config.yml` | Orgs, exclusions, and project target |
| `scripts/sync-project-board.py` | Discovery + GraphQL mutations |
| `scripts/lib/github_client.py` | Shared REST/GraphQL client |
| `.github/workflows/sync_project_board.yml` | Schedule + manual trigger |
| `scripts/report-sprint-velocity.py` | End-of-sprint velocity averages |
| `.github/workflows/report_sprint_velocity.yml` | Manual velocity report |

See [Sprint velocity report](SPRINT_VELOCITY.md) for completed-sprint averages
(size, organization, milestone). That report is read-only and is meant to be
run after a sprint closes; it is useful to run now so the pipeline is in place
before history exists.

## Why a PAT (not the sync GitHub App)

GitHub App installation tokens are scoped to a **single** organization.
Adding an issue from `Agentic-SSDLC` or `unbound-force` onto a project owned
by `complytime` requires a credential that can see all three orgs and write
to the project. Use a fine-grained or classic personal access token (or a
machine-user token) stored as `PROJECT_SYNC_TOKEN`.

## One-time setup

### 1. Create the token

**Fine-grained PAT** (preferred — least privilege):

- Resource owner / repository access covering the three orgs (or all repos the
  bot can see)
- Repository permissions: **Issues** (read), **Pull requests** (read),
  **Metadata** (read)
- Organization permission for `complytime`: **Projects = Read and write**
- The token owner must be able to access private repos in all three orgs and
  edit project `#14`

**Classic PAT** (fallback when fine-grained multi-org access is impractical):

- Prefer `public_repo` instead of `repo` if every target repository is public
- Otherwise scopes: `repo`, `read:org`, `project`
- Note: classic `repo` grants full read/write to all private repos the token
  owner can access — broader than this sync needs

### 2. Add the repository secret

In `complytime/org-infra` → Settings → Secrets and variables → Actions:

- Name: `PROJECT_SYNC_TOKEN`
- Value: the PAT from step 1

### 3. Run an initial backfill

Actions → **Sync Compliance Automation Project Board** → Run workflow

- Leave `dry_run` checked first to validate discovery
- Re-run with `dry_run` unchecked to add items

Optional: set `orgs` to a single org (for example `complytime`) to stage the rollout.

## Local dry-run

```bash
export GITHUB_TOKEN="$(gh auth token)"   # needs project write for apply mode
pip install -r requirements.txt
python scripts/sync-project-board.py --config project-sync-config.yml --dry-run
python scripts/sync-project-board.py --config project-sync-config.yml --backfill-org always
```

## Changing scope

Edit `project-sync-config.yml`:

- Add/remove orgs under `organizations`
- Adjust `exclude_repos`
- Toggle `sync.issues` / `sync.pull_requests`
- Change `project.default_status` (must match a Status option on the board)
- Change `project.ready_for_review_status` / `project.in_review_status`
  (prefixes of the Status options used for the review-activity transition)
