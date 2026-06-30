# SPDX-License-Identifier: Apache-2.0

"""Tests for sync-org-repositories.py."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

sync_module = importlib.import_module("sync-org-repositories")

GITHUB_API = sync_module.GITHUB_API

# Valid 40-character hex SHA for use in transform_workflow_refs tests.
TEST_SHA = "a" * 40


class TestValidateGithubApiRequest:
    """Tests for validate_github_api_request."""

    def test_allowed_get_repo(self):
        assert (
            sync_module.validate_github_api_request(f"{GITHUB_API}/repos/org/repo", "GET") is True
        )

    def test_allowed_get_pulls(self):
        assert (
            sync_module.validate_github_api_request(f"{GITHUB_API}/repos/org/repo/pulls", "GET")
            is True
        )

    def test_allowed_post_pulls(self):
        assert (
            sync_module.validate_github_api_request(f"{GITHUB_API}/repos/org/repo/pulls", "POST")
            is True
        )

    def test_allowed_get_contents(self):
        assert (
            sync_module.validate_github_api_request(
                f"{GITHUB_API}/repos/org/repo/contents/.github/dependabot.yml",
                "GET",
            )
            is True
        )

    def test_allowed_get_contents_nested_path(self):
        assert (
            sync_module.validate_github_api_request(
                f"{GITHUB_API}/repos/org/repo/contents/a/b/c.yml", "GET"
            )
            is True
        )

    def test_disallowed_delete_repo(self):
        result = sync_module.validate_github_api_request(f"{GITHUB_API}/repos/org/repo", "DELETE")
        assert not result

    def test_disallowed_post_forks(self):
        result = sync_module.validate_github_api_request(
            f"{GITHUB_API}/repos/org/repo/forks", "POST"
        )
        assert not result

    def test_disallowed_arbitrary_endpoint(self):
        result = sync_module.validate_github_api_request(f"{GITHUB_API}/orgs/org/members", "GET")
        assert not result

    def test_disallowed_post_to_get_only_endpoint(self):
        result = sync_module.validate_github_api_request(f"{GITHUB_API}/repos/org/repo", "POST")
        assert not result

    def test_disallowed_delete_branch_ref(self):
        result = sync_module.validate_github_api_request(
            f"{GITHUB_API}/repos/org/repo/git/refs/heads/main", "DELETE"
        )
        assert not result

    def test_disallowed_get_user(self):
        result = sync_module.validate_github_api_request(f"{GITHUB_API}/user", "GET")
        assert not result

    def test_disallowed_get_app(self):
        result = sync_module.validate_github_api_request(f"{GITHUB_API}/app", "GET")
        assert not result

    def test_allowed_get_releases_latest(self):
        assert (
            sync_module.validate_github_api_request(
                f"{GITHUB_API}/repos/org/repo/releases/latest",
                "GET",
            )
            is True
        )

    def test_allowed_get_git_ref_tags(self):
        assert (
            sync_module.validate_github_api_request(
                f"{GITHUB_API}/repos/org/repo/git/ref/tags/v1.0.0",
                "GET",
            )
            is True
        )

    def test_allowed_get_git_tags_sha(self):
        assert (
            sync_module.validate_github_api_request(
                f"{GITHUB_API}/repos/org/repo/git/tags/abc123def456",
                "GET",
            )
            is True
        )


class TestValidateBranchName:
    """Tests for validate_branch_name."""

    def test_valid_prefix(self):
        assert sync_module.validate_branch_name("sync-repo-standards-20260416120000") is True

    def test_valid_prefix_minimal(self):
        assert sync_module.validate_branch_name("sync-repo-standards-x") is True

    def test_invalid_prefix(self):
        assert sync_module.validate_branch_name("feature/my-branch") is False

    def test_main_rejected(self):
        assert sync_module.validate_branch_name("main") is False

    def test_empty_string_rejected(self):
        assert sync_module.validate_branch_name("") is False

    def test_partial_prefix_rejected(self):
        assert sync_module.validate_branch_name("sync-repo-") is False


class TestGenerateDependabotConfig:
    """Tests for generate_dependabot_config."""

    def _make_config(self, common=None, overrides=None, exclude=None):
        """Build a minimal sync config with dependabot section."""
        dependabot = {}
        if common is not None:
            dependabot["common"] = common
        if overrides is not None:
            dependabot["overrides"] = overrides
        if exclude is not None:
            dependabot["exclude_repos"] = exclude
        return {"dependabot": dependabot}

    def test_common_only(self):
        common = [
            {"package-ecosystem": "github-actions", "directory": "/"},
            {"package-ecosystem": "pre-commit", "directory": "/"},
        ]
        config = self._make_config(common=common)
        result = sync_module.generate_dependabot_config("my-repo", config)
        assert len(result) == 2
        ecosystems = [e["package-ecosystem"] for e in result]
        assert "github-actions" in ecosystems
        assert "pre-commit" in ecosystems

    def test_override_adds_ecosystem(self):
        common = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        overrides = {
            "my-repo": [
                {"package-ecosystem": "gomod", "directory": "/"},
            ],
        }
        config = self._make_config(common=common, overrides=overrides)
        result = sync_module.generate_dependabot_config("my-repo", config)
        assert len(result) == 2
        ecosystems = [e["package-ecosystem"] for e in result]
        assert "github-actions" in ecosystems
        assert "gomod" in ecosystems

    def test_override_replaces_common_for_same_ecosystem(self):
        common = [
            {
                "package-ecosystem": "github-actions",
                "directory": "/",
                "schedule": {"interval": "daily"},
            },
        ]
        overrides = {
            "my-repo": [
                {
                    "package-ecosystem": "github-actions",
                    "directories": ["/", "/.github/actions/custom"],
                    "schedule": {"interval": "weekly"},
                },
            ],
        }
        config = self._make_config(common=common, overrides=overrides)
        result = sync_module.generate_dependabot_config("my-repo", config)
        assert len(result) == 1
        entry = result[0]
        assert entry["package-ecosystem"] == "github-actions"
        assert entry["directories"] == ["/", "/.github/actions/custom"]
        assert entry["schedule"]["interval"] == "weekly"

    def test_excluded_repo_returns_none(self):
        common = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        config = self._make_config(common=common, exclude=["excluded-repo"])
        result = sync_module.generate_dependabot_config("excluded-repo", config)
        assert result is None

    def test_no_override_for_repo(self):
        common = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        overrides = {
            "other-repo": [
                {"package-ecosystem": "gomod", "directory": "/"},
            ],
        }
        config = self._make_config(common=common, overrides=overrides)
        result = sync_module.generate_dependabot_config("my-repo", config)
        assert len(result) == 1
        assert result[0]["package-ecosystem"] == "github-actions"

    def test_no_dependabot_section_returns_none(self):
        config = {}
        result = sync_module.generate_dependabot_config("my-repo", config)
        assert result is None


class TestMergeDependabotEntries:
    """Tests for merge_dependabot_entries."""

    def test_no_existing_file(self, tmp_path):
        managed = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        nonexistent = str(tmp_path / "missing.yml")
        result = sync_module.merge_dependabot_entries(managed, nonexistent)
        parsed = yaml.safe_load(result)
        assert parsed["version"] == 2
        assert len(parsed["updates"]) == 1
        assert parsed["updates"][0]["package-ecosystem"] == "github-actions"

    def test_list_items_indented_under_parent(self, tmp_path):
        managed = [
            {
                "package-ecosystem": "github-actions",
                "directories": ["/", "/.github/actions/custom"],
                "schedule": {"interval": "daily"},
            },
        ]
        nonexistent = str(tmp_path / "missing.yml")
        result = sync_module.merge_dependabot_entries(managed, nonexistent)
        # Verify list items under 'updates:' are indented (not flush)
        for line in result.splitlines():
            if line.strip().startswith("- package-ecosystem"):
                assert line.startswith("  "), (
                    f"Sequence entry should be indented under parent: {line!r}"
                )
            if line.strip() == "- /":
                assert line.startswith("      "), f"Nested list item should be indented: {line!r}"

    def test_no_trailing_blank_line(self, tmp_path):
        managed = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        nonexistent = str(tmp_path / "missing.yml")
        result = sync_module.merge_dependabot_entries(managed, nonexistent)
        assert result.endswith("\n"), "File should end with a newline"
        assert not result.endswith("\n\n"), "File should not end with a double newline"

    def test_unmanaged_entries_preserved(self, tmp_path):
        managed = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        existing = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "github-actions", "directory": "/"},
                {"package-ecosystem": "docker", "directory": "/"},
            ],
        }
        existing_path = tmp_path / "dependabot.yml"
        existing_path.write_text(yaml.dump(existing))

        result = sync_module.merge_dependabot_entries(managed, str(existing_path))
        parsed = yaml.safe_load(result)
        assert len(parsed["updates"]) == 2
        ecosystems = [e["package-ecosystem"] for e in parsed["updates"]]
        assert "github-actions" in ecosystems
        assert "docker" in ecosystems

    def test_managed_replaces_existing(self, tmp_path):
        managed = [
            {
                "package-ecosystem": "gomod",
                "directories": ["/", "/submod"],
                "schedule": {"interval": "weekly"},
            },
        ]
        existing = {
            "version": 2,
            "updates": [
                {
                    "package-ecosystem": "gomod",
                    "directory": "/",
                    "schedule": {"interval": "daily"},
                },
            ],
        }
        existing_path = tmp_path / "dependabot.yml"
        existing_path.write_text(yaml.dump(existing))

        result = sync_module.merge_dependabot_entries(managed, str(existing_path))
        parsed = yaml.safe_load(result)
        assert len(parsed["updates"]) == 1
        entry = parsed["updates"][0]
        assert entry["directories"] == ["/", "/submod"]
        assert entry["schedule"]["interval"] == "weekly"

    def test_all_unmanaged_preserved_when_no_overlap(self, tmp_path):
        managed = [
            {"package-ecosystem": "github-actions", "directory": "/"},
        ]
        existing = {
            "version": 2,
            "updates": [
                {"package-ecosystem": "docker", "directory": "/"},
                {"package-ecosystem": "npm", "directory": "/frontend"},
            ],
        }
        existing_path = tmp_path / "dependabot.yml"
        existing_path.write_text(yaml.dump(existing))

        result = sync_module.merge_dependabot_entries(managed, str(existing_path))
        parsed = yaml.safe_load(result)
        assert len(parsed["updates"]) == 3
        ecosystems = [e["package-ecosystem"] for e in parsed["updates"]]
        assert ecosystems == ["github-actions", "docker", "npm"]


class TestCheckExistingSyncPr:
    """Tests for check_existing_sync_pr."""

    @patch.object(sync_module, "github_api_request")
    def test_no_existing_pr(self, mock_api):
        mock_api.return_value = (200, [])
        result = sync_module.check_existing_sync_pr("org", "repo")
        assert result is None

    @patch.object(sync_module, "github_api_request")
    def test_existing_pr_found(self, mock_api):
        mock_api.return_value = (
            200,
            [
                {
                    "title": "chore: sync repository standards",
                    "html_url": "https://github.com/org/repo/pull/42",
                    "head": {
                        "ref": "sync-repo-standards-20260416120000",
                    },
                },
            ],
        )
        result = sync_module.check_existing_sync_pr("org", "repo")
        assert result is not None
        assert result["url"] == "https://github.com/org/repo/pull/42"
        assert result["branch"] == "sync-repo-standards-20260416120000"

    @patch.object(sync_module, "github_api_request")
    def test_non_matching_pr_ignored(self, mock_api):
        mock_api.return_value = (
            200,
            [
                {
                    "title": "feat: add new feature",
                    "html_url": "https://github.com/org/repo/pull/1",
                    "head": {"ref": "feat/something"},
                },
            ],
        )
        result = sync_module.check_existing_sync_pr("org", "repo")
        assert result is None

    @patch.object(sync_module, "github_api_request")
    def test_api_failure_returns_error(self, mock_api):
        mock_api.return_value = (500, {"error": "internal"})
        result = sync_module.check_existing_sync_pr("org", "repo")
        assert result is not None
        assert "error" in result

    @patch.object(sync_module, "github_api_request")
    def test_uses_pagination(self, mock_api):
        mock_api.return_value = (200, [])
        sync_module.check_existing_sync_pr("org", "repo")
        _, kwargs = mock_api.call_args
        assert kwargs["params"]["per_page"] == 100


class TestCompareFiles:
    """Tests for compare_files."""

    def test_identical_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("hello")
        assert sync_module.compare_files(str(f1), str(f2)) is True

    def test_different_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert sync_module.compare_files(str(f1), str(f2)) is False

    def test_missing_dest_file(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        assert sync_module.compare_files(str(f1), str(tmp_path / "missing.txt")) is False


class TestSyncFile:
    """Tests for sync_file."""

    def test_copies_missing_file(self, tmp_path):
        src = tmp_path / "src" / "file.yml"
        src.parent.mkdir()
        src.write_text("content")
        dest = tmp_path / "dest" / "file.yml"
        result = sync_module.sync_file(str(src), str(dest), "file.yml")
        assert result is True
        assert dest.read_text() == "content"

    def test_skips_identical_file(self, tmp_path):
        src = tmp_path / "src.yml"
        dest = tmp_path / "dest.yml"
        src.write_text("same")
        dest.write_text("same")
        result = sync_module.sync_file(str(src), str(dest), "file.yml")
        assert result is False

    def test_updates_different_file(self, tmp_path):
        src = tmp_path / "src.yml"
        dest = tmp_path / "dest.yml"
        src.write_text("new")
        dest.write_text("old")
        result = sync_module.sync_file(str(src), str(dest), "file.yml")
        assert result is True
        assert dest.read_text() == "new"


class TestLoadSyncConfig:
    """Tests for load_sync_config."""

    def test_loads_valid_config(self):
        config = sync_module.load_sync_config("sync-config.yml")
        assert "files_to_sync" in config
        assert "exclude_repos" in config

    def test_exclude_repos_contains_org_infra(self):
        config = sync_module.load_sync_config("sync-config.yml")
        assert "org-infra" in config["exclude_repos"]

    def test_dependabot_section_present(self):
        config = sync_module.load_sync_config("sync-config.yml")
        assert "dependabot" in config
        dependabot = config["dependabot"]
        assert "common" in dependabot
        assert "overrides" in dependabot
        assert len(dependabot["common"]) > 0


class TestExtractRepositories:
    """Tests for extract_repositories."""

    def test_extracts_repos(self):
        data = {
            "orgs": {
                "testorg": {"repos": {"repo1": {}, "repo2": {}}},
            },
        }
        repos = sync_module.extract_repositories(data, "testorg")
        assert sorted(repos) == ["repo1", "repo2"]

    def test_empty_org(self):
        data = {"orgs": {"testorg": {}}}
        repos = sync_module.extract_repositories(data, "testorg")
        assert repos == []

    def test_missing_org(self):
        data = {"orgs": {"other": {"repos": {"repo1": {}}}}}
        repos = sync_module.extract_repositories(data, "testorg")
        assert repos == []


class TestResolveFileVars:
    """Tests for resolve_file_vars."""

    def test_repo_in_overrides_returns_override(self):
        file_config = {
            "source": "ci_security.yml",
            "vars": {
                "enable_trivy_source": {
                    "default": "false",
                    "repos": {"complyctl": "true"},
                },
            },
        }
        result = sync_module.resolve_file_vars(file_config, "complyctl")
        assert result == {"enable_trivy_source": "true"}

    def test_repo_not_in_overrides_returns_default(self):
        file_config = {
            "source": "ci_security.yml",
            "vars": {
                "enable_trivy_source": {
                    "default": "false",
                    "repos": {"complyctl": "true"},
                },
            },
        }
        result = sync_module.resolve_file_vars(file_config, "community")
        assert result == {"enable_trivy_source": "false"}

    def test_no_vars_key_returns_empty(self):
        file_config = {"source": "ci_security.yml"}
        result = sync_module.resolve_file_vars(file_config, "complyctl")
        assert result == {}

    def test_empty_vars_returns_empty(self):
        file_config = {"source": "ci_security.yml", "vars": {}}
        result = sync_module.resolve_file_vars(file_config, "complyctl")
        assert result == {}

    def test_multiple_vars_resolved(self):
        file_config = {
            "source": "workflow.yml",
            "vars": {
                "var_a": {"default": "off", "repos": {"repo1": "on"}},
                "var_b": {"default": "low", "repos": {"repo2": "high"}},
            },
        }
        result = sync_module.resolve_file_vars(file_config, "repo1")
        assert result == {"var_a": "on", "var_b": "low"}

    def test_no_repos_map_uses_default(self):
        file_config = {
            "source": "ci_security.yml",
            "vars": {
                "enable_trivy_source": {"default": "false"},
            },
        }
        result = sync_module.resolve_file_vars(file_config, "any-repo")
        assert result == {"enable_trivy_source": "false"}


class TestApplyFileVars:
    """Tests for apply_file_vars."""

    def test_substitution_replaces_value(self):
        content = "    with:\n      enable_trivy_source: true\n"
        result = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "false"},
        )
        assert "enable_trivy_source: false" in result

    def test_preserves_surrounding_content(self):
        content = (
            "# Comment line\n"
            "    uses: org/repo@abc123def456 # v1.0\n"
            "    with:\n"
            "      enable_trivy_source: true\n"
            "  other_job:\n"
            "    runs-on: ubuntu-latest\n"
        )
        result = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "false"},
        )
        assert "# Comment line" in result
        assert "@abc123def456 # v1.0" in result
        assert "runs-on: ubuntu-latest" in result
        assert "enable_trivy_source: false" in result

    def test_no_match_logs_warning(self, capsys):
        content = "    with:\n      some_other_input: true\n"
        result = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "false"},
        )
        captured = capsys.readouterr()
        assert "Warning: var 'enable_trivy_source' not found" in captured.out
        assert result == content

    def test_multiple_vars_applied(self):
        content = (
            "      enable_trivy_source: true\n"
            "      trivy_severity: HIGH,CRITICAL\n"
        )
        resolved = {
            "enable_trivy_source": "false",
            "trivy_severity": "CRITICAL",
        }
        result = sync_module.apply_file_vars(content, resolved)
        assert "enable_trivy_source: false" in result
        assert "trivy_severity: CRITICAL" in result
        assert "HIGH,CRITICAL" not in result

    def test_preserves_indentation(self):
        content = "      enable_trivy_source: true\n"
        result = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "false"},
        )
        assert result == "      enable_trivy_source: false\n"

    def test_empty_vars_returns_unchanged(self):
        content = "      enable_trivy_source: true\n"
        result = sync_module.apply_file_vars(content, {})
        assert result == content


class TestVarAwareFileComparison:
    """Integration tests for var-aware file sync comparison."""

    def test_resolved_matches_dest_no_update(self, tmp_path):
        """When resolved content matches dest, file is up to date."""
        source = tmp_path / "source.yml"
        dest = tmp_path / "dest.yml"
        # Source has true, but resolved will be false
        source.write_text("      enable_trivy_source: true\n")
        dest.write_text("      enable_trivy_source: false\n")

        source_content = source.read_text()
        resolved_vars = {"enable_trivy_source": "false"}
        resolved_content = sync_module.apply_file_vars(
            source_content, resolved_vars,
        )
        assert resolved_content == dest.read_text()

    def test_resolved_differs_from_dest_needs_update(self, tmp_path):
        """When resolved content differs from dest, update is needed."""
        source = tmp_path / "source.yml"
        dest = tmp_path / "dest.yml"
        source.write_text("      enable_trivy_source: true\n")
        # Dest still has old value
        dest.write_text("      enable_trivy_source: true\n")

        source_content = source.read_text()
        resolved_vars = {"enable_trivy_source": "false"}
        resolved_content = sync_module.apply_file_vars(
            source_content, resolved_vars,
        )
        assert resolved_content != dest.read_text()

    def test_resolved_matches_source_for_override_repo(self, tmp_path):
        """When repo is in overrides, resolved content keeps source value."""
        source = tmp_path / "source.yml"
        source.write_text("      enable_trivy_source: true\n")

        file_config = {
            "source": "ci_security.yml",
            "vars": {
                "enable_trivy_source": {
                    "default": "false",
                    "repos": {"complyctl": "true"},
                },
            },
        }
        resolved_vars = sync_module.resolve_file_vars(
            file_config, "complyctl",
        )
        resolved_content = sync_module.apply_file_vars(
            source.read_text(), resolved_vars,
        )
        assert resolved_content == source.read_text()


class TestTransformWorkflowRefs:
    """Tests for transform_workflow_refs."""

    def test_single_ref_transformed(self):
        content = (
            "    uses: ./.github/workflows/reusable_ci.yml\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "complytime", "org-infra",
            TEST_SHA, "v1.0.0",
        )
        expected = (
            "    uses: complytime/org-infra/"
            ".github/workflows/"
            f"reusable_ci.yml@{TEST_SHA} # v1.0.0\n"
        )
        assert result == expected

    def test_multiple_refs_transformed(self):
        content = (
            "    uses: ./.github/workflows/reusable_ci.yml\n"
            "    runs-on: ubuntu-latest\n"
            "    uses: ./.github/workflows/reusable_lint.yml\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "complytime", "org-infra",
            TEST_SHA, "v2.0.0",
        )
        assert f"reusable_ci.yml@{TEST_SHA} # v2.0.0" in result
        assert f"reusable_lint.yml@{TEST_SHA} # v2.0.0" in result
        assert "./.github/workflows/" not in result

    def test_no_refs_passthrough(self):
        content = (
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "complytime", "org-infra",
            TEST_SHA, "v1",
        )
        assert result == content

    def test_non_reusable_ref_not_transformed(self):
        content = (
            "    uses: ./.github/workflows/ci_checks.yml\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "complytime", "org-infra",
            TEST_SHA, "v1",
        )
        assert result == content

    def test_third_party_action_not_transformed(self):
        content = (
            "    uses: actions/checkout@abc123def456\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "complytime", "org-infra",
            TEST_SHA, "v1",
        )
        assert result == content

    def test_mixed_content(self):
        content = (
            "name: CI Pipeline\n"
            "jobs:\n"
            "  lint:\n"
            "    uses: ./.github/workflows/reusable_lint.yml\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "  deploy:\n"
            "    uses: ./.github/workflows/ci_deploy.yml\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "org", "repo", TEST_SHA, "v3.0.0",
        )
        # Reusable ref transformed
        assert (
            "uses: org/repo/.github/workflows/"
            f"reusable_lint.yml@{TEST_SHA} # v3.0.0" in result
        )
        # Third-party action untouched
        assert "uses: actions/checkout@v4" in result
        # Non-reusable local ref untouched
        assert (
            "uses: ./.github/workflows/ci_deploy.yml" in result
        )

    def test_preserves_indentation(self):
        content = (
            "  uses: ./.github/workflows/reusable_a.yml\n"
            "    uses: ./.github/workflows/reusable_b.yml\n"
            "      uses: ./.github/workflows/reusable_c.yml\n"
        )
        result = sync_module.transform_workflow_refs(
            content, "org", "repo", TEST_SHA, "v1",
        )
        lines = result.splitlines()
        assert lines[0].startswith("  uses:")
        assert lines[1].startswith("    uses:")
        assert lines[2].startswith("      uses:")

    def test_invalid_sha_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid SHA format"):
            sync_module.transform_workflow_refs(
                "uses: ./.github/workflows/reusable_ci.yml",
                "org", "repo", "not-a-valid-sha", "v1",
            )

    def test_short_sha_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid SHA format"):
            sync_module.transform_workflow_refs(
                "uses: ./.github/workflows/reusable_ci.yml",
                "org", "repo", "abc123", "v1",
            )


class TestGetLatestRelease:
    """Tests for get_latest_release."""

    @patch.object(sync_module, "github_api_request")
    def test_lightweight_tag_returns_commit_sha(self, mock_api):
        mock_api.side_effect = [
            (200, {"tag_name": "v1.0.0"}),
            (200, {"object": {"type": "commit", "sha": "abc123"}}),
        ]
        tag, sha = sync_module.get_latest_release("org", "repo")
        assert tag == "v1.0.0"
        assert sha == "abc123"

    @patch.object(sync_module, "github_api_request")
    def test_annotated_tag_dereferences_to_commit(self, mock_api):
        mock_api.side_effect = [
            (200, {"tag_name": "v1.0.0"}),
            (
                200,
                {"object": {"type": "tag", "sha": "tag_obj_sha"}},
            ),
            (200, {"object": {"sha": "real_commit_sha"}}),
        ]
        tag, sha = sync_module.get_latest_release("org", "repo")
        assert tag == "v1.0.0"
        assert sha == "real_commit_sha"

    @patch.object(sync_module, "github_api_request")
    def test_no_release_exits(self, mock_api):
        mock_api.return_value = (404, {"message": "Not Found"})
        with pytest.raises(SystemExit) as exc_info:
            sync_module.get_latest_release("org", "repo")
        assert exc_info.value.code == 1

    @patch.object(sync_module, "github_api_request")
    def test_tag_resolution_fails_exits(self, mock_api):
        mock_api.side_effect = [
            (200, {"tag_name": "v1.0.0"}),
            (404, {"message": "Not Found"}),
        ]
        with pytest.raises(SystemExit) as exc_info:
            sync_module.get_latest_release("org", "repo")
        assert exc_info.value.code == 1


class TestWorkflowRefTransformComposition:
    """Tests for composition of apply_file_vars and transform_workflow_refs."""

    def test_vars_and_refs_compose(self):
        content = (
            "jobs:\n"
            "  scan:\n"
            "    uses: ./.github/workflows/"
            "reusable_vuln_scan.yml\n"
            "    with:\n"
            "      enable_trivy_source: false\n"
        )
        # Apply vars first (change false to true)
        with_vars = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "true"},
        )
        # Then transform workflow refs
        result = sync_module.transform_workflow_refs(
            with_vars, "org", "repo", TEST_SHA, "v1.0.0",
        )
        assert "enable_trivy_source: true" in result
        assert (
            "uses: org/repo/.github/workflows/"
            f"reusable_vuln_scan.yml@{TEST_SHA} # v1.0.0"
            in result
        )
        assert "./.github/workflows/" not in result

    def test_vars_only_no_refs(self):
        content = (
            "jobs:\n"
            "  scan:\n"
            "    uses: actions/checkout@v4\n"
            "    with:\n"
            "      enable_trivy_source: false\n"
        )
        with_vars = sync_module.apply_file_vars(
            content, {"enable_trivy_source": "true"},
        )
        result = sync_module.transform_workflow_refs(
            with_vars, "org", "repo", TEST_SHA, "v1",
        )
        assert "enable_trivy_source: true" in result
        assert "uses: actions/checkout@v4" in result

    def test_refs_only_no_vars(self):
        content = (
            "jobs:\n"
            "  lint:\n"
            "    uses: ./.github/workflows/reusable_lint.yml\n"
            "    with:\n"
            "      some_input: value\n"
        )
        with_vars = sync_module.apply_file_vars(content, {})
        result = sync_module.transform_workflow_refs(
            with_vars, "org", "repo", TEST_SHA, "v1",
        )
        assert (
            "uses: org/repo/.github/workflows/"
            f"reusable_lint.yml@{TEST_SHA} # v1" in result
        )
        assert "some_input: value" in result


class TestWriteStepSummary:
    """Tests for write_step_summary."""

    def test_writes_pr_table(self, tmp_path):
        summary_file = tmp_path / "summary.md"
        results = [
            {
                "repo": "complyctl",
                "status": "created",
                "pr_url": "https://github.com/complytime/complyctl/pull/1",
                "error": None,
            },
            {
                "repo": "complyscribe",
                "status": "updated",
                "pr_url": "https://github.com/complytime/complyscribe/pull/5",
                "error": None,
            },
        ]
        with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            sync_module.write_step_summary(results, "complytime", False)

        content = summary_file.read_text()
        assert "## Sync Organization Repositories" in content
        assert "2/2" in content
        assert "### Pull Requests" in content
        assert "complyctl" in content
        assert "Created" in content
        assert "complyscribe" in content
        assert "Updated" in content
        assert "https://github.com/complytime/complyctl/pull/1" in content

    def test_writes_failure_table(self, tmp_path):
        summary_file = tmp_path / "summary.md"
        results = [
            {
                "repo": "failing-repo",
                "status": "failed",
                "pr_url": None,
                "error": "Git push rejected",
            },
        ]
        with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            sync_module.write_step_summary(results, "complytime", False)

        content = summary_file.read_text()
        assert "0/1" in content
        assert "### Failures" in content
        assert "failing-repo" in content
        assert "Git push rejected" in content

    def test_writes_up_to_date(self, tmp_path):
        summary_file = tmp_path / "summary.md"
        results = [
            {
                "repo": "stable-repo",
                "status": "up_to_date",
                "pr_url": None,
                "error": None,
            },
        ]
        with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            sync_module.write_step_summary(results, "complytime", False)

        content = summary_file.read_text()
        assert "1/1" in content
        assert "`stable-repo`" in content
        assert "Up to date" in content

    def test_writes_dry_run_repos(self, tmp_path):
        summary_file = tmp_path / "summary.md"
        results = [
            {
                "repo": "target-repo",
                "status": "dry_run",
                "pr_url": None,
                "error": None,
            },
        ]
        with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            sync_module.write_step_summary(results, "complytime", True)

        content = summary_file.read_text()
        assert "**Mode:** Dry run" in content
        assert "`target-repo`" in content
        assert "Would create PRs" in content

    def test_skips_when_env_not_set(self, tmp_path):
        results = [
            {
                "repo": "some-repo",
                "status": "created",
                "pr_url": "https://example.com/pr/1",
                "error": None,
            },
        ]
        with patch.dict("os.environ", {}, clear=True):
            # Should not raise, just silently skip
            sync_module.write_step_summary(results, "complytime", False)

    def test_mixed_results(self, tmp_path):
        summary_file = tmp_path / "summary.md"
        results = [
            {
                "repo": "repo-a",
                "status": "created",
                "pr_url": "https://github.com/org/repo-a/pull/10",
                "error": None,
            },
            {
                "repo": "repo-b",
                "status": "up_to_date",
                "pr_url": None,
                "error": None,
            },
            {
                "repo": "repo-c",
                "status": "failed",
                "pr_url": None,
                "error": "Permission denied",
            },
        ]
        with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            sync_module.write_step_summary(results, "myorg", False)

        content = summary_file.read_text()
        assert "2/3" in content
        assert "### Pull Requests" in content
        assert "repo-a" in content
        assert "`repo-b`" in content
        assert "### Failures" in content
        assert "repo-c" in content
        assert "Permission denied" in content
