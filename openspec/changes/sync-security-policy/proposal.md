## Why

The organization-wide `SECURITY.md` in the `community` repository contains a
placeholder email address (`complytime-security@example.com`) that prevents
valid vulnerability reporting via email. Additionally, `SECURITY.md` is not
included in the org-infra sync process, leaving individual repositories with
inconsistent or missing security policies. This fails the OSPS Baseline Level 1
requirement (OSPS-VM-02.01: documentation MUST contain security contacts) and
leaves the organization unprepared for future CRA (EU Cyber Resilience Act)
compliance.

## What Changes

- **Prerequisite** (separate change in `community` repo): Fix the security
  contact email in `community/SECURITY.md` from
  `complytime-security@example.com` to `complytime-security@redhat.com`.
- Refine the `org-infra/SECURITY.md` stub template to include the security
  contact email directly (for OSPS-VM-02.01 compliance in each repo) while
  linking to the canonical `community/SECURITY.md` for full policy details.
- Add `SECURITY.md` to `sync-config.yml` so the stub is synced to all org
  repositories, excluding `community` (which holds the canonical policy).
- Add a test for the new `SECURITY.md` sync entry to maintain existing test
  coverage standards.

## Non-goals

- Achieving OSPS Baseline Level 2 or Level 3 compliance (response timelines,
  CVD policy, end-of-life policy). These require team discussion on SLAs and
  will be addressed in a follow-up change.
- Modifying security policies in private repositories (`nunya`, `roadmap`).
- Adding repository-specific security exceptions or per-repo overrides.
- Changing the sync mechanism itself (the existing `sync-org-repositories.py`
  script handles this change without modification).

## Capabilities

### New Capabilities

- `security-policy-sync`: Sync a standardized `SECURITY.md` stub to all org
  repositories via the existing file sync mechanism, ensuring every public repo
  has a security policy that satisfies OSPS Baseline Level 1.

### Modified Capabilities

_None -- no existing capability specs are changing at the requirement level._

### Removed Capabilities

_None._

## Impact

- **community/SECURITY.md**: Email address fix (the canonical security policy).
  This is an external repository; the change should be coordinated separately.
- **org-infra/SECURITY.md**: Updated stub content (template for sync).
- **org-infra/sync-config.yml**: New entry in `files_to_sync`.
- **org-infra/tests/**: New or updated test coverage for the sync entry.
- **All org repos** (via sync PRs): Will receive a `SECURITY.md` stub on next
  sync cycle. Repos with existing custom `SECURITY.md` files (e.g., `complyctl`)
  will have them replaced by the standard stub.
- **complyctl**: Currently has a custom `SECURITY.md` with the correct email.
  The sync will replace it with the org-wide stub. This is intentional since the
  canonical policy lives in `community`.
- **Documentation**: No updates to `AGENTS.md` or `README.md` are required.
  The sync mechanism is already documented and directory listings use catch-all
  patterns. A `CHANGELOG.md` entry will be added.
