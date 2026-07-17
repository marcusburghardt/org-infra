## Context

The ComplyTime organization uses `community/SECURITY.md` as the canonical
security policy for all repositories. Individual repositories are expected to
link to it, but this is not enforced. The `org-infra` sync mechanism
(`sync-org-repositories.py`) already syncs workflows, lint configs, templates,
and AI tooling to all org repos via `sync-config.yml`, but `SECURITY.md` is not
included.

Current state:

- `community/SECURITY.md`: Full policy, but contains a placeholder email
  (`complytime-security@example.com`).
- `org-infra/SECURITY.md`: Stub linking to community. Not synced.
- `complyctl/SECURITY.md`: Custom file with the correct email
  (`complytime-security@redhat.com`).
- `.github/SECURITY.md`: Does not exist.
- Other repos: Inconsistent coverage.

OSPS Baseline Level 1 requires security contacts in documentation
(OSPS-VM-02.01). The placeholder email in community fails this requirement.

## Goals / Non-Goals

**Goals:**

- Achieve OSPS Baseline Level 1 compliance for `SECURITY.md` across all public
  org repositories.
- Establish `community/SECURITY.md` as the single source of truth for security
  policy, with a synced stub in every other repo that links to it.
- Include `SECURITY.md` in the existing sync mechanism with appropriate
  exclusions.

**Non-Goals:**

- OSPS Level 2/3 compliance (response SLAs, CVD timelines, EOL policy).
- Modifying `sync-org-repositories.py` (the existing sync logic handles this
  change without code changes).
- Adding per-repo security policy overrides or merge strategies.
- Covering private repositories (`nunya`, `roadmap`).

## Decisions

### Decision 1: Stub with inline email vs. link-only stub

**Chosen**: Stub includes the security contact email directly, plus a link to
the full policy in community.

**Alternative considered**: Link-only stub (current pattern) -- just a URL to
`community/SECURITY.md` with no inline contact info.

**Rationale**: OSPS-VM-02.01 requires security contacts in the documentation.
A link-only stub means scanners (OpenSSF Scorecard, OSPS Baseline checkers)
would need to follow the link to find contacts, which most automated tools do
not do. Including the email directly in each repo's `SECURITY.md` satisfies the
check without requiring link traversal. The sync mechanism ensures the email
stays consistent if it ever changes.

### Decision 2: community excluded, .github included in sync

**Chosen**: Exclude only `community` from the `SECURITY.md` sync entry. Include
`.github` (it receives the stub like all other repos).

**Alternative considered**: Exclude `.github` and rely on GitHub's default
community health file mechanism.

**Rationale**: GitHub's default community health file fallback (from the
`.github` repo) only surfaces in the GitHub UI; it does not create actual files
in repo clones. Automated scanners clone repos and check for `SECURITY.md` in
the file tree. Since `.github` is itself an org repository, it should also have
a `SECURITY.md`. The stub is lightweight and harmless.

### Decision 3: community/SECURITY.md email fix is out of scope for sync

**Chosen**: The `community/SECURITY.md` email fix is documented as a
prerequisite but is not part of the sync-config change itself. It is a separate
change in the `community` repository.

**Alternative considered**: Bundling the community fix into this change.

**Rationale**: `community` is a separate repository. The sync mechanism operates
on files within `org-infra`. The email fix in `community` is an independent
change that should be tracked and reviewed in its own repository. This change
ensures the synced stub is correct; the canonical policy fix is a coordination
item.

### Decision 4: complyctl's custom SECURITY.md will be replaced

**Chosen**: Accept that the sync will propose replacing `complyctl`'s custom
`SECURITY.md` with the org-wide stub.

**Alternative considered**: Adding `complyctl` to the `exclude_repos` list for
`SECURITY.md` to preserve its custom file.

**Rationale**: The entire point of this change is standardization. The custom
`complyctl` file duplicates information that should live in `community`. The
sync PR will make this change visible for review. No information is lost because
the canonical policy in `community` already covers what `complyctl`'s custom
file contains.

## Risks / Trade-offs

- **[Risk] community email not fixed before sync runs**: If `community/
  SECURITY.md` still has `@example.com` when the sync creates PRs, the stubs
  will link to a policy with a broken email. **Mitigation**: Fix the community
  email first. Document this as a prerequisite in tasks.
- **[Risk] complyctl team pushback on losing custom SECURITY.md**: The team may
  prefer keeping their own file. **Mitigation**: The sync PR will be visible.
  Team can discuss during PR review. If truly needed, `complyctl` can be added
  to `exclude_repos` later.
- **[Trade-off] Email duplication**: The security email appears in both the stub
  (synced to all repos) and the canonical policy (community). If the email
  changes, both need updating. **Mitigation**: The stub is synced from
  `org-infra`, so updating `org-infra/SECURITY.md` and running sync handles all
  repos. Only `community/SECURITY.md` requires a separate update, which is
  manageable for a single file.
