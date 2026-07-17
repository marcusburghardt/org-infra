## 1. Update SECURITY.md Stub Template

- [ ] 1.1 Update `SECURITY.md` in org-infra with the security contact email
  (`complytime-security@redhat.com`), GitHub Private Vulnerability Reporting
  instructions, a warning against public issue disclosure, and a link to the
  full policy in `community/SECURITY.md`.

## 2. Add SECURITY.md to Sync Configuration

- [ ] 2.1 Add a `SECURITY.md` entry to `files_to_sync` in `sync-config.yml`
  with `source: SECURITY.md`, `destination: SECURITY.md`, and `exclude_repos`
  containing `community`.

## 3. Test Coverage

- [ ] 3.1 Add a test in `tests/test_sync_org_repositories.py` that validates
  the `SECURITY.md` entry exists in the loaded `sync-config.yml`
  `files_to_sync` with the correct source path.
- [ ] 3.2 Add a test that validates the `SECURITY.md` entry's `exclude_repos`
  list contains `community`.

## 4. Validation

- [ ] 4.1 Run `make lint` to verify `SECURITY.md` and `sync-config.yml` pass
  yamllint and ruff checks.
- [ ] 4.2 Run `make test` to verify all tests pass including the new ones.
- [ ] 4.3 Run `make sync-dry-run` to verify `SECURITY.md` appears in the
  sync output for expected repositories and is skipped for `community`.
