## 0. Prerequisites

- [ ] 0.1 Verify that `community/SECURITY.md` has been updated to replace
  `complytime-security@example.com` with `complytime-security@redhat.com`.
  This is a separate change in the `community` repository and MUST be merged
  before running the sync.

## 1. Update SECURITY.md Stub Template

- [x] 1.1 Update `SECURITY.md` in org-infra with the security contact email
  (`complytime-security@redhat.com`), GitHub Private Vulnerability Reporting
  instructions, a warning against public issue disclosure, and a link to the
  full policy in `community/SECURITY.md`.

## 2. Add SECURITY.md to Sync Configuration

- [x] 2.1 Add a `SECURITY.md` entry to `files_to_sync` in `sync-config.yml`
  with `source: SECURITY.md`, `destination: SECURITY.md`, and `exclude_repos`
  containing `community`.

## 3. Test Coverage

- [x] 3.1 Add a test in `tests/test_sync_org_repositories.py` that validates
  the `SECURITY.md` entry exists in the loaded `sync-config.yml`
  `files_to_sync` with the correct source path and matching destination path.
- [x] 3.2 Add a test that validates the `SECURITY.md` entry's `exclude_repos`
  list contains `community`.
- [x] 3.3 Add a test that reads `SECURITY.md` and asserts the security contact
  email (`complytime-security@redhat.com`) is present in the file content.
- [x] 3.4 Add a test that reads `SECURITY.md` and asserts the file contains a
  warning against opening public GitHub issues for security vulnerabilities
  and a link to `community/SECURITY.md`.

## 4. Validation

- [x] 4.1 Run `make lint` to verify `SECURITY.md` and `sync-config.yml` pass
  yamllint and ruff checks.
- [x] 4.2 Run `make test` to verify all tests pass including the new ones.
- [ ] 4.3 Run `make sync-dry-run` to verify `SECURITY.md` appears in the
  sync output for expected repositories (e.g., `complyctl`, `.github`,
  `website`) and is skipped for `community`.
  NOTE: Requires GITHUB_TOKEN -- must be verified in CI or with credentials.

## 5. Documentation

- [x] 5.1 Add an entry to `CHANGELOG.md` under `## Unreleased` / `### Added`
  documenting the `SECURITY.md` sync entry.
<!-- spec-review: passed -->
<!-- code-review: passed -->
