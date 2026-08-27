# SPDX-License-Identifier: Apache-2.0

"""Tests for sync-project-board.py."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
import requests
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

sync = importlib.import_module("sync-project-board")


def _minimal_config(**overrides: Any) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "project": {"owner": "complytime", "number": 14, "default_status": "Backlog"},
        "sync": {
            "issues": True,
            "pull_requests": True,
            "skip_archived": True,
            "link_repositories": True,
        },
        "organizations": [
            {"name": "complytime", "exclude_repos": ["roadmap", "complytime"]},
            {"name": "Agentic-SSDLC"},
        ],
    }
    config.update(overrides)
    return config


def _org_fields(**overrides: Any) -> sync.ProjectFields:
    fields = sync.ProjectFields(
        project_id="PROJECT",
        status_field_id="STATUS_FIELD",
        status_options={"Backlog": "OPT"},
        organization_field_id="ORG_FIELD",
        organization_options={
            "Agentic-SSDLC": "ORG_A",
            "complytime": "ORG_C",
            "unbound-force": "ORG_U",
        },
    )
    for key, value in overrides.items():
        setattr(fields, key, value)
    return fields


def _priority_fields() -> sync.ProjectFields:
    return _org_fields(
        priority_field_id="PRI_FIELD",
        priority_options={
            "Urgent": "PRI_U",
            "High": "PRI_H",
            "Medium": "PRI_M",
            "Low": "PRI_L",
        },
        review_priority_field_id="REV_FIELD",
        review_priority_options={
            "Urgent": "REV_U",
            "High": "REV_H",
            "Medium": "REV_M",
            "Low": "REV_L",
        },
    )


class TestLoadAndValidateConfig:
    def test_load_config_reads_yaml(self, tmp_path: Path):
        path = tmp_path / "cfg.yml"
        path.write_text(yaml.safe_dump(_minimal_config()), encoding="utf-8")
        loaded = sync.load_config(path)
        assert loaded["project"]["owner"] == "complytime"
        assert loaded["organizations"][0]["exclude_repos"] == ["roadmap", "complytime"]

    def test_validate_config_accepts_minimal(self):
        assert sync.validate_config(_minimal_config())["project"]["number"] == 14

    @pytest.mark.parametrize(
        "bad",
        [
            None,
            [],
            {"project": {"owner": "x"}},  # missing number + orgs
            {"project": {"owner": "x", "number": 1}, "organizations": []},
            {
                "project": {"owner": "x", "number": 1},
                "organizations": [{"exclude_repos": ["a"]}],
            },
        ],
    )
    def test_validate_config_rejects_invalid(self, bad: Any):
        with pytest.raises(ValueError):
            sync.validate_config(bad)


class TestListOrgRepos:
    def test_filters_exclude_and_archived(self):
        client = MagicMock()
        client.rest_paginate.return_value = [
            {"name": "keep", "archived": False},
            {"name": "roadmap", "archived": False},
            {"name": "old", "archived": True},
        ]
        repos = sync.list_org_repos(
            client, "complytime", exclude={"roadmap"}, skip_archived=True
        )
        assert [r["name"] for r in repos] == ["keep"]
        client.rest_paginate.assert_called_once_with(
            "/orgs/complytime/repos", {"type": "all", "sort": "full_name"}
        )

    def test_includes_archived_when_not_skipped(self):
        client = MagicMock()
        client.rest_paginate.return_value = [
            {"name": "keep", "archived": False},
            {"name": "old", "archived": True},
        ]
        repos = sync.list_org_repos(
            client, "complytime", exclude=set(), skip_archived=False
        )
        assert [r["name"] for r in repos] == ["keep", "old"]


class TestListOpenItems:
    def test_filters_issues_vs_prs(self):
        client = MagicMock()
        client.rest_paginate.return_value = [
            {"number": 1, "title": "issue", "node_id": "I_1"},
            {"number": 2, "title": "pr", "node_id": "PR_2", "pull_request": {}},
        ]
        issues_only = sync.list_open_items(
            client, "org/repo", include_issues=True, include_prs=False
        )
        prs_only = sync.list_open_items(
            client, "org/repo", include_issues=False, include_prs=True
        )
        both = sync.list_open_items(
            client, "org/repo", include_issues=True, include_prs=True
        )
        assert [i["number"] for i in issues_only] == [1]
        assert [i["number"] for i in prs_only] == [2]
        assert [i["number"] for i in both] == [1, 2]


class TestExistingContentIds:
    def test_paginates_until_exhausted(self):
        client = MagicMock()
        client.graphql.side_effect = [
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [
                            {"content": {"id": "I_1"}},
                            {"content": None},
                            {"content": {"id": "PR_2"}},
                        ],
                    }
                }
            },
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                        "nodes": [{"content": {"id": "I_3"}}],
                    }
                }
            },
        ]
        ids = sync.existing_content_ids(client, "PROJECT_ID")
        assert ids == {"I_1", "PR_2", "I_3"}
        assert client.graphql.call_count == 2
        assert client.graphql.call_args_list[1].args[1]["cursor"] == "c1"


class TestFormatAndWriteSummary:
    def test_format_summary_includes_counts_and_errors(self):
        stats = sync.SyncStats(
            repos_considered=3,
            repos_linked=1,
            repos_link_skipped=2,
            items_seen=10,
            items_already_on_board=4,
            items_added=5,
            items_failed=1,
            errors=["boom"],
        )
        text = sync.format_summary(stats, dry_run=True)
        assert "dry-run" in text
        assert "**3**" in text
        assert "skipped/already linked: 2" in text
        assert "**5**" in text
        assert "`boom`" in text
        assert "Organization set/updated" in text
        assert "Priority copied from linked issues" in text
        assert "Priority option unmapped" in text
        assert "Ready for Review advanced to In Review" in text

    def test_write_summary_appends_step_summary(self, tmp_path: Path, monkeypatch):
        summary_path = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
        stats = sync.SyncStats(repos_considered=1, items_added=2)
        sync.write_summary(stats, dry_run=False)
        written = summary_path.read_text(encoding="utf-8")
        assert "Compliance Automation project sync" in written
        assert "Added: **2**" in written


class TestGitHubClientImport:
    def test_reexports_shared_client(self):
        from lib.github_client import GitHubClient

        assert sync.GitHubClient is GitHubClient


class TestSyncErrorHandling:
    def _project_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sync, "get_project", lambda *_a, **_k: _org_fields())
        monkeypatch.setattr(sync, "existing_content_ids", lambda *_a, **_k: set())
        monkeypatch.setattr(sync, "ensure_organizations", lambda *_a, **_k: None)
        monkeypatch.setattr(
            sync, "ensure_pr_priority_from_issues", lambda *_a, **_k: None
        )
        monkeypatch.setattr(sync, "advance_ready_for_review", lambda *_a, **_k: None)

    def test_per_org_request_errors_are_recorded(self, monkeypatch: pytest.MonkeyPatch):
        self._project_mocks(monkeypatch)
        client = MagicMock()
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(side_effect=requests.Timeout("slow")),
        )
        stats = sync.sync(_minimal_config(), client, org_filter=set())
        assert stats.errors
        assert "Failed listing repos for" in stats.errors[0]

    def test_programming_errors_are_not_swallowed(self, monkeypatch: pytest.MonkeyPatch):
        self._project_mocks(monkeypatch)
        client = MagicMock()
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(side_effect=TypeError("bug")),
        )
        with pytest.raises(TypeError, match="bug"):
            sync.sync(_minimal_config(), client, org_filter={"complytime"})

    def test_add_item_runtime_error_counts_as_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._project_mocks(monkeypatch)
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(
                return_value=[
                    {
                        "name": "demo",
                        "full_name": "complytime/demo",
                        "node_id": "R_1",
                        "archived": False,
                    }
                ]
            ),
        )
        monkeypatch.setattr(sync, "link_repository", MagicMock(return_value=True))
        monkeypatch.setattr(
            sync,
            "list_open_items",
            MagicMock(
                return_value=[
                    {"number": 7, "title": "work", "node_id": "I_7"},
                ]
            ),
        )
        monkeypatch.setattr(
            sync,
            "add_item",
            MagicMock(side_effect=RuntimeError("GraphQL errors: boom")),
        )
        stats = sync.sync(
            _minimal_config(),
            client,
            org_filter={"complytime"},
        )
        assert stats.items_failed == 1
        assert stats.items_added == 0
        assert any("Failed adding" in err for err in stats.errors)

    def test_cross_org_repo_link_is_skipped_without_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._project_mocks(monkeypatch)
        client = MagicMock(dry_run=False)
        link = MagicMock(return_value=True)
        monkeypatch.setattr(sync, "link_repository", link)
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(
                return_value=[
                    {
                        "name": "website",
                        "full_name": "unbound-force/website",
                        "node_id": "R_WEB",
                        "archived": False,
                    }
                ]
            ),
        )
        monkeypatch.setattr(sync, "list_open_items", MagicMock(return_value=[]))
        config = _minimal_config(
            organizations=[{"name": "unbound-force"}],
        )
        stats = sync.sync(config, client, org_filter={"unbound-force"})
        link.assert_not_called()
        assert stats.repos_link_skipped == 1
        assert stats.repos_linked == 0
        assert stats.errors == []

    def test_same_org_link_failure_is_best_effort(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        self._project_mocks(monkeypatch)
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "link_repository",
            MagicMock(
                side_effect=RuntimeError(
                    "beatrizmcouto does not have the correct permissions "
                    "to execute `LinkProjectV2ToRepository`"
                )
            ),
        )
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(
                return_value=[
                    {
                        "name": "complyapi",
                        "full_name": "complytime/complyapi",
                        "node_id": "R_API",
                        "archived": False,
                    }
                ]
            ),
        )
        monkeypatch.setattr(sync, "list_open_items", MagicMock(return_value=[]))
        stats = sync.sync(_minimal_config(), client, org_filter={"complytime"})
        captured = capsys.readouterr()
        assert stats.repos_link_skipped == 1
        assert stats.repos_linked == 0
        assert stats.errors == []
        assert stats.items_failed == 0
        assert "skip repo link for complytime/complyapi" in captured.out


class TestLinkRepository:
    def test_dry_run_does_not_call_graphql(self):
        client = MagicMock(dry_run=True)
        assert sync.link_repository(client, "P", "R") is True
        client.graphql.assert_not_called()

    def test_already_linked_is_idempotent(self):
        client = MagicMock(dry_run=False)
        client.graphql.side_effect = RuntimeError("already linked to project")
        assert sync.link_repository(client, "P", "R") is False


class TestSetSingleSelect:
    def test_set_single_select_calls_graphql_with_correct_variables(self):
        client = MagicMock(dry_run=False)
        sync.set_single_select(client, "PROJECT", "ITEM", "FIELD", "OPT")
        client.graphql.assert_called_once()
        _query, variables = client.graphql.call_args.args
        assert variables == {
            "projectId": "PROJECT",
            "itemId": "ITEM",
            "fieldId": "FIELD",
            "optionId": "OPT",
        }

    def test_set_single_select_dry_run_skips_mutation(self):
        client = MagicMock(dry_run=True)
        sync.set_single_select(client, "PROJECT", "ITEM", "FIELD", "OPT")
        client.graphql.assert_not_called()


class TestOrganizationMapping:
    def test_organization_option_for_owner_maps_known_orgs(self):
        options = {
            "Agentic-SSDLC": "A",
            "complytime": "C",
            "unbound-force": "U",
        }
        assert sync.organization_option_for_owner("complytime", options) == (
            "complytime",
            "C",
        )
        assert sync.organization_option_for_owner("complytime-labs", options) == (
            "complytime",
            "C",
        )
        assert sync.organization_option_for_owner("unknown", options) is None

    def test_add_item_sets_status_and_organization(self):
        client = MagicMock(dry_run=False)
        client.graphql.side_effect = [
            {"addProjectV2ItemById": {"item": {"id": "ITEM_1"}}},
            {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM_1"}}},
            {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM_1"}}},
        ]
        result = sync.add_item(
            client,
            "PROJECT",
            "CONTENT",
            "STATUS_FIELD",
            "STATUS_OPT",
            "ORG_FIELD",
            "ORG_OPT",
        )
        assert result.item_id == "ITEM_1"
        assert result.organization_set is True
        assert result.organization_error is None
        assert client.graphql.call_count == 3
        # Second call sets Status; third sets Organization
        status_vars = client.graphql.call_args_list[1].args[1]
        org_vars = client.graphql.call_args_list[2].args[1]
        assert status_vars["fieldId"] == "STATUS_FIELD"
        assert status_vars["optionId"] == "STATUS_OPT"
        assert org_vars["fieldId"] == "ORG_FIELD"
        assert org_vars["optionId"] == "ORG_OPT"

    def test_add_item_org_failure_is_best_effort(self):
        client = MagicMock(dry_run=False)
        client.graphql.side_effect = [
            {"addProjectV2ItemById": {"item": {"id": "ITEM_1"}}},
            {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM_1"}}},
            RuntimeError("INSUFFICIENT_SCOPES"),
        ]
        result = sync.add_item(
            client,
            "PROJECT",
            "CONTENT",
            "STATUS_FIELD",
            "STATUS_OPT",
            "ORG_FIELD",
            "ORG_OPT",
        )
        assert result.item_id == "ITEM_1"
        assert result.organization_set is False
        assert result.organization_error == "INSUFFICIENT_SCOPES"

    def test_add_item_dry_run_returns_no_item_id(self):
        client = MagicMock(dry_run=True)
        result = sync.add_item(
            client,
            "PROJECT",
            "CONTENT",
            "STATUS_FIELD",
            "STATUS_OPT",
            "ORG_FIELD",
            "ORG_OPT",
        )
        assert result.item_id is None
        assert result.organization_set is True
        client.graphql.assert_not_called()

    def test_ensure_organizations_updates_missing_values(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        fields = _org_fields()
        monkeypatch.setattr(
            sync,
            "list_board_items_with_org_metadata",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_1",
                    "organization": None,
                    "content": {
                        "id": "I_1",
                        "repository": {
                            "nameWithOwner": "complytime/demo",
                            "owner": {"login": "complytime"},
                        },
                    },
                },
                {
                    "id": "PVTI_2",
                    "organization": {"name": "unbound-force"},
                    "content": {
                        "id": "I_2",
                        "repository": {
                            "nameWithOwner": "unbound-force/gaze",
                            "owner": {"login": "unbound-force"},
                        },
                    },
                },
            ],
        )
        set_calls = []

        def _set(*args, **kwargs):
            set_calls.append((args, kwargs))

        monkeypatch.setattr(sync, "set_single_select", _set)
        stats = sync.SyncStats()
        sync.ensure_organizations(client, fields, stats)
        assert stats.organization_set == 1
        assert len(set_calls) == 1
        assert set_calls[0][0][2] == "PVTI_1"
        assert set_calls[0][0][4] == "ORG_C"

    def test_list_board_items_with_org_metadata_paginates(self):
        client = MagicMock()
        client.graphql.side_effect = [
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [{"id": "PVTI_1", "organization": None, "content": {}}],
                    }
                }
            },
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                        "nodes": [{"id": "PVTI_2", "organization": None, "content": {}}],
                    }
                }
            },
        ]
        items = sync.list_board_items_with_org_metadata(client, "PROJECT_ID")
        assert [node["id"] for node in items] == ["PVTI_1", "PVTI_2"]
        assert client.graphql.call_count == 2
        assert client.graphql.call_args_list[1].args[1]["cursor"] == "c1"

    @pytest.mark.parametrize(
        "mode,items_added,organization_failed,expected",
        [
            ("always", 3, 0, True),
            ("never", 0, 1, False),
            ("auto", 0, 0, True),
            ("auto", 2, 0, False),
            ("auto", 2, 1, True),
        ],
    )
    def test_should_run_organization_backfill(
        self,
        mode: str,
        items_added: int,
        organization_failed: int,
        expected: bool,
    ):
        stats = sync.SyncStats(
            items_added=items_added, organization_failed=organization_failed
        )
        assert sync.should_run_organization_backfill(mode, stats) is expected


class TestSyncOrganizationStats:
    def _project_mocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            sync,
            "get_project",
            lambda *_a, **_k: _org_fields(
                organization_options={"complytime": "ORG_C"}
            ),
        )
        monkeypatch.setattr(sync, "existing_content_ids", lambda *_a, **_k: set())
        monkeypatch.setattr(sync, "link_repository", MagicMock(return_value=True))
        monkeypatch.setattr(
            sync, "ensure_pr_priority_from_issues", lambda *_a, **_k: None
        )
        monkeypatch.setattr(sync, "advance_ready_for_review", lambda *_a, **_k: None)
        monkeypatch.setattr(
            sync,
            "list_org_repos",
            MagicMock(
                return_value=[
                    {
                        "name": "demo",
                        "full_name": "complytime/demo",
                        "node_id": "R_1",
                        "archived": False,
                    }
                ]
            ),
        )

    def test_org_set_failure_still_counts_item_as_added(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._project_mocks(monkeypatch)
        ensure = MagicMock()
        monkeypatch.setattr(sync, "ensure_organizations", ensure)
        monkeypatch.setattr(
            sync,
            "list_open_items",
            MagicMock(
                return_value=[{"number": 7, "title": "work", "node_id": "I_7"}]
            ),
        )
        monkeypatch.setattr(
            sync,
            "add_item",
            MagicMock(
                return_value=sync.AddItemResult(
                    item_id="PVTI_7",
                    organization_set=False,
                    organization_error="INSUFFICIENT_SCOPES",
                )
            ),
        )
        stats = sync.sync(
            _minimal_config(),
            MagicMock(dry_run=False),
            org_filter={"complytime"},
            backfill_org="never",
        )
        assert stats.items_added == 1
        assert stats.items_failed == 0
        assert stats.organization_set == 0
        assert stats.organization_failed == 1
        assert any("Failed setting Organization" in err for err in stats.errors)
        ensure.assert_not_called()

    def test_auto_backfill_skipped_when_new_items_have_org(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._project_mocks(monkeypatch)
        ensure = MagicMock()
        monkeypatch.setattr(sync, "ensure_organizations", ensure)
        monkeypatch.setattr(
            sync,
            "list_open_items",
            MagicMock(
                return_value=[{"number": 8, "title": "more", "node_id": "I_8"}]
            ),
        )
        monkeypatch.setattr(
            sync,
            "add_item",
            MagicMock(
                return_value=sync.AddItemResult(
                    item_id="PVTI_8", organization_set=True
                )
            ),
        )
        stats = sync.sync(
            _minimal_config(),
            MagicMock(dry_run=False),
            org_filter={"complytime"},
        )
        assert stats.items_added == 1
        assert stats.organization_set == 1
        assert stats.organization_failed == 0
        ensure.assert_not_called()

    def test_auto_backfill_runs_when_no_items_added(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._project_mocks(monkeypatch)
        ensure = MagicMock()
        monkeypatch.setattr(sync, "ensure_organizations", ensure)
        monkeypatch.setattr(sync, "list_open_items", MagicMock(return_value=[]))
        sync.sync(
            _minimal_config(),
            MagicMock(dry_run=False),
            org_filter={"complytime"},
        )
        ensure.assert_called_once()


class TestListBoardPriorityItems:
    def test_paginates_multiple_pages(self):
        client = MagicMock()
        client.graphql.side_effect = [
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "priority": {"name": "High"},
                                "reviewPriority": None,
                                "content": {"__typename": "Issue", "id": "I_1"},
                            }
                        ],
                    }
                }
            },
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                        "nodes": [
                            {
                                "id": "PVTI_2",
                                "priority": None,
                                "reviewPriority": {"name": "Low"},
                                "content": {
                                    "__typename": "PullRequest",
                                    "id": "PR_1",
                                    "closingIssuesReferences": {
                                        "nodes": [{"id": "I_1"}]
                                    },
                                },
                            }
                        ],
                    }
                }
            },
        ]
        items = sync.list_board_priority_items(client, "PROJECT_ID")
        assert [item["id"] for item in items] == ["PVTI_1", "PVTI_2"]
        assert client.graphql.call_count == 2
        assert client.graphql.call_args_list[0].args[1]["cursor"] is None
        assert client.graphql.call_args_list[1].args[1]["cursor"] == "c1"
        query = client.graphql.call_args_list[0].args[0]
        assert f"first: {sync.CLOSING_ISSUES_PAGE_SIZE}" in query
        assert "pageInfo { hasNextPage }" in query

    def test_empty_board_returns_no_items(self):
        client = MagicMock()
        client.graphql.return_value = {
            "node": {
                "items": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [],
                }
            }
        }
        assert sync.list_board_priority_items(client, "PROJECT_ID") == []

    def test_extracts_priority_fields_and_closing_issues(self):
        client = MagicMock()
        client.graphql.return_value = {
            "node": {
                "items": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "PVTI_ISSUE",
                            "priority": {"name": "Urgent"},
                            "reviewPriority": None,
                            "content": {"__typename": "Issue", "id": "I_1"},
                        },
                        {
                            "id": "PVTI_PR",
                            "priority": None,
                            "reviewPriority": {"name": "High"},
                            "content": {
                                "__typename": "PullRequest",
                                "id": "PR_1",
                                "closingIssuesReferences": {
                                    "nodes": [{"id": "I_1"}, {"id": "I_2"}]
                                },
                            },
                        },
                    ],
                }
            }
        }
        items = sync.list_board_priority_items(client, "PROJECT_ID")
        assert items[0]["priority"]["name"] == "Urgent"
        assert items[1]["reviewPriority"]["name"] == "High"
        assert [
            node["id"]
            for node in items[1]["content"]["closingIssuesReferences"]["nodes"]
        ] == ["I_1", "I_2"]


class TestPriorityInherit:
    def test_highest_priority_picks_urgent_over_low(self):
        assert sync.highest_priority(["Low", "Urgent", None, "Medium"]) == "Urgent"

    def test_highest_priority_empty_when_no_known_values(self):
        assert sync.highest_priority([]) is None
        assert sync.highest_priority([None, "unknown"]) is None

    def test_highest_priority_ignores_unknown_in_mixed_list(self):
        assert sync.highest_priority(["NotReal", "Low"]) == "Low"

    def test_copies_issue_priority_onto_empty_pr_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "High"},
                    "reviewPriority": None,
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        set_calls = []

        def _set(*args, **_kwargs):
            set_calls.append(args)

        monkeypatch.setattr(sync, "set_single_select", _set)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        assert stats.priority_set == 2
        assert stats.priority_failed == 0
        field_ids = {call[3] for call in set_calls}
        option_ids = {call[4] for call in set_calls}
        assert field_ids == {"PRI_FIELD", "REV_FIELD"}
        assert option_ids == {"PRI_H", "REV_H"}

    def test_does_not_overwrite_existing_pr_priority(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "High"},
                    "reviewPriority": None,
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": {"name": "Medium"},
                    "reviewPriority": {"name": "Medium"},
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        set_mock.assert_not_called()
        assert stats.priority_set == 0

    def test_skips_pr_with_no_linked_issue_priority(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
                {
                    "id": "PVTI_ORPHAN",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_2",
                        "closingIssuesReferences": {"nodes": []},
                    },
                },
            ],
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        set_mock.assert_not_called()
        assert stats.priority_set == 0

    def test_skips_when_linked_issue_is_not_on_board(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {"nodes": [{"id": "I_OFFBOARD"}]},
                    },
                },
            ],
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        set_mock.assert_not_called()
        assert stats.priority_set == 0

    def test_uses_highest_priority_when_multiple_issues_linked(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_A",
                    "priority": {"name": "Low"},
                    "content": {"__typename": "Issue", "id": "I_A"},
                },
                {
                    "id": "PVTI_B",
                    "priority": {"name": "Urgent"},
                    "content": {"__typename": "Issue", "id": "I_B"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {
                            "nodes": [{"id": "I_A"}, {"id": "I_B"}]
                        },
                    },
                },
            ],
        )
        set_calls = []
        monkeypatch.setattr(
            sync, "set_single_select", lambda *args, **_k: set_calls.append(args)
        )
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        assert {call[4] for call in set_calls} == {"PRI_U", "REV_U"}

    def test_field_write_failure_is_best_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "Medium"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": {"name": "Medium"},
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        monkeypatch.setattr(
            sync,
            "set_single_select",
            MagicMock(side_effect=RuntimeError("INSUFFICIENT_SCOPES")),
        )
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        assert stats.priority_set == 0
        assert stats.priority_failed == 1
        assert any("Failed copying Priority" in err for err in stats.errors)

    def test_remember_highest_priority_keeps_max_rank_on_duplicates(self):
        store: dict[str, str] = {}
        sync.remember_highest_priority(store, "I_1", "Low")
        sync.remember_highest_priority(store, "I_1", "Urgent")
        sync.remember_highest_priority(store, "I_1", "Medium")
        assert store["I_1"] == "Urgent"

    def test_uses_highest_when_issue_appears_twice(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_I1_LOW",
                    "priority": {"name": "Low"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_I1_HIGH",
                    "priority": {"name": "High"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "number": 4,
                        "repository": {"nameWithOwner": "complytime/demo"},
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        set_calls = []
        monkeypatch.setattr(
            sync, "set_single_select", lambda *args, **_k: set_calls.append(args)
        )
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        assert {call[4] for call in set_calls} == {"PRI_H", "REV_H"}

    def test_logs_unmapped_option(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "High"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "number": 5,
                        "repository": {"nameWithOwner": "complytime/demo"},
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        fields = _priority_fields()
        fields.priority_options = {"Low": "PRI_L"}
        fields.review_priority_options = {"Low": "REV_L"}
        set_fn = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_fn)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, fields, stats)
        set_fn.assert_not_called()
        assert stats.priority_unmapped == 2
        assert stats.priority_set == 0
        captured = capsys.readouterr()
        assert "no option named 'High'" in captured.out

    def test_warns_when_closing_issues_truncated(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "Medium"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "number": 6,
                        "repository": {"nameWithOwner": "complytime/demo"},
                        "closingIssuesReferences": {
                            "pageInfo": {"hasNextPage": True},
                            "nodes": [{"id": "I_1"}],
                        },
                    },
                },
            ],
        )
        monkeypatch.setattr(sync, "set_single_select", lambda *_a, **_k: None)
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        captured = capsys.readouterr()
        assert "closing issues truncated" in captured.out
        assert stats.priority_set == 2

    def test_dry_run_does_not_write(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        client = MagicMock(dry_run=True)
        monkeypatch.setattr(
            sync,
            "list_board_priority_items",
            lambda *_a, **_k: [
                {
                    "id": "PVTI_ISSUE",
                    "priority": {"name": "High"},
                    "content": {"__typename": "Issue", "id": "I_1"},
                },
                {
                    "id": "PVTI_PR",
                    "priority": None,
                    "reviewPriority": None,
                    "content": {
                        "__typename": "PullRequest",
                        "id": "PR_1",
                        "number": 11,
                        "repository": {"nameWithOwner": "complytime/demo"},
                        "closingIssuesReferences": {"nodes": [{"id": "I_1"}]},
                    },
                },
            ],
        )
        stats = sync.SyncStats()
        sync.ensure_pr_priority_from_issues(client, _priority_fields(), stats)
        client.graphql.assert_not_called()
        assert stats.priority_set == 2
        captured = capsys.readouterr()
        assert "[dry-run] would set field" in captured.out


READY_STATUS = "Ready for Review  👀"
IN_REVIEW_STATUS = "In Review 🏁"
STATUS_SINCE = "2026-08-25T10:00:00Z"
ACTIVITY_BEFORE = "2026-08-25T09:00:00Z"
ACTIVITY_AFTER = "2026-08-25T11:00:00Z"


def _review_fields() -> sync.ProjectFields:
    return _org_fields(
        status_options={
            "Backlog": "ST_BACKLOG",
            READY_STATUS: "ST_READY",
            IN_REVIEW_STATUS: "ST_IN_REVIEW",
        }
    )


def _comment(
    login: str,
    created_at: str,
    association: str = "MEMBER",
) -> Dict[str, Any]:
    return {
        "createdAt": created_at,
        "author": {"login": login},
        "authorAssociation": association,
    }


def _review(
    login: str,
    submitted_at: Optional[str],
    state: str,
    association: str = "MEMBER",
) -> Dict[str, Any]:
    return {
        "submittedAt": submitted_at,
        "state": state,
        "author": {"login": login},
        "authorAssociation": association,
    }


def _ready_board_item(
    *,
    item_id: str = "PVTI_1",
    content_id: str = "I_1",
    typename: str = "Issue",
    status_name: str = READY_STATUS,
    updated_at: str = STATUS_SINCE,
    author: str = "alice",
    repo: str = "complytime/demo",
    number: int = 7,
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "status": {"name": status_name, "updatedAt": updated_at},
        "content": {
            "__typename": typename,
            "id": content_id,
            "number": number,
            "title": "work",
            "author": {"login": author},
            "repository": {"nameWithOwner": repo},
        },
    }


class TestReviewStatusPrefixes:
    def test_defaults_when_keys_omitted(self):
        assert sync.review_status_prefixes(_minimal_config()) == (
            sync.DEFAULT_READY_FOR_REVIEW_STATUS,
            sync.DEFAULT_IN_REVIEW_STATUS,
        )

    def test_reads_configured_prefixes(self):
        config = _minimal_config()
        config["project"]["ready_for_review_status"] = " Waiting "
        config["project"]["in_review_status"] = " Looking "
        assert sync.review_status_prefixes(config) == ("Waiting", "Looking")

    def test_blank_values_fall_back_to_defaults(self):
        config = _minimal_config()
        config["project"]["ready_for_review_status"] = "   "
        config["project"]["in_review_status"] = None
        assert sync.review_status_prefixes(config) == (
            sync.DEFAULT_READY_FOR_REVIEW_STATUS,
            sync.DEFAULT_IN_REVIEW_STATUS,
        )


class TestStatusOptionForPrefix:
    def test_matches_emoji_option_by_prefix(self):
        options = {
            "Ready 🚀": "A",
            READY_STATUS: "B",
            IN_REVIEW_STATUS: "C",
        }
        assert sync.status_option_for_prefix(options, "Ready for Review") == (
            READY_STATUS,
            "B",
        )
        assert sync.status_option_for_prefix(options, "In Review") == (
            IN_REVIEW_STATUS,
            "C",
        )

    def test_prefers_exact_match(self):
        options = {"Ready": "EXACT", "Ready for Review  👀": "EMOJI"}
        assert sync.status_option_for_prefix(options, "Ready") == ("Ready", "EXACT")

    def test_ambiguous_prefix_returns_none(self):
        options = {"Ready 🚀": "A", "Ready for Review  👀": "B"}
        assert sync.status_option_for_prefix(options, "Ready") is None

    def test_missing_prefix_returns_none(self):
        assert sync.status_option_for_prefix({"Backlog": "X"}, "In Review") is None
        assert sync.status_option_for_prefix({"Backlog": "X"}, "") is None


class TestReviewerActivityDetection:
    def _since(self):
        parsed = sync.parse_github_datetime(STATUS_SINCE)
        assert parsed is not None
        return parsed

    def test_parse_github_datetime_accepts_z_and_rejects_garbage(self):
        parsed = sync.parse_github_datetime("2026-08-25T10:00:00Z")
        assert parsed is not None
        assert parsed.year == 2026
        assert sync.parse_github_datetime(None) is None
        assert sync.parse_github_datetime("not-a-date") is None

    def test_issue_comment_from_other_human_after_status_counts(self):
        content = {
            "__typename": "Issue",
            "author": {"login": "alice"},
            "comments": {
                "nodes": [_comment("bob", ACTIVITY_AFTER)],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is True

    def test_author_comment_does_not_count(self):
        content = {
            "__typename": "Issue",
            "author": {"login": "alice"},
            "comments": {
                "nodes": [_comment("alice", ACTIVITY_AFTER)],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is False

    def test_bot_comment_does_not_count(self):
        content = {
            "__typename": "Issue",
            "author": {"login": "alice"},
            "comments": {
                "nodes": [
                    _comment("github-actions[bot]", ACTIVITY_AFTER, "BOT"),
                    _comment("renovate[bot]", ACTIVITY_AFTER),
                ]
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is False

    def test_comment_before_status_change_does_not_count(self):
        content = {
            "__typename": "Issue",
            "author": {"login": "alice"},
            "comments": {
                "nodes": [_comment("bob", ACTIVITY_BEFORE)],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is False

    def test_pr_submitted_review_counts(self):
        content = {
            "__typename": "PullRequest",
            "author": {"login": "alice"},
            "comments": {"nodes": []},
            "reviews": {
                "nodes": [_review("bob", ACTIVITY_AFTER, "CHANGES_REQUESTED")],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is True

    def test_pending_review_does_not_count(self):
        content = {
            "__typename": "PullRequest",
            "author": {"login": "alice"},
            "comments": {"nodes": []},
            "reviews": {
                "nodes": [_review("bob", None, "PENDING")],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is False

    def test_author_review_does_not_count(self):
        content = {
            "__typename": "PullRequest",
            "author": {"login": "alice"},
            "comments": {"nodes": []},
            "reviews": {
                "nodes": [_review("alice", ACTIVITY_AFTER, "COMMENTED")],
            },
        }
        assert sync.content_has_reviewer_activity(content, self._since()) is False


def _issue_activity(*comments: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "__typename": "Issue",
        "author": {"login": "alice"},
        "comments": {"nodes": list(comments)},
    }


class TestAdvanceReadyForReview:
    def test_moves_issue_after_reviewer_comment(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [_ready_board_item()],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            lambda *_a, **_k: {
                "I_1": _issue_activity(_comment("bob", ACTIVITY_AFTER)),
            },
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        set_mock.assert_called_once_with(
            client, "PROJECT", "PVTI_1", "STATUS_FIELD", "ST_IN_REVIEW"
        )
        assert stats.review_status_set == 1
        assert stats.review_status_failed == 0

    def test_dry_run_calls_set_single_select_and_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=True)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [_ready_board_item()],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            lambda *_a, **_k: {
                "I_1": _issue_activity(_comment("bob", ACTIVITY_AFTER)),
            },
        )
        real_set = sync.set_single_select
        set_spy = MagicMock(side_effect=real_set)
        monkeypatch.setattr(sync, "set_single_select", set_spy)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        set_spy.assert_called_once_with(
            client, "PROJECT", "PVTI_1", "STATUS_FIELD", "ST_IN_REVIEW"
        )
        assert stats.review_status_set == 1
        client.graphql.assert_not_called()

    def test_moves_pr_after_submitted_review(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [
                _ready_board_item(
                    item_id="PVTI_PR",
                    content_id="PR_1",
                    typename="PullRequest",
                )
            ],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            lambda *_a, **_k: {
                "PR_1": {
                    "__typename": "PullRequest",
                    "author": {"login": "alice"},
                    "comments": {"nodes": []},
                    "reviews": {
                        "nodes": [_review("bob", ACTIVITY_AFTER, "APPROVED")],
                    },
                }
            },
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        set_mock.assert_called_once()
        assert stats.review_status_set == 1

    def test_leaves_item_when_only_author_commented(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [_ready_board_item()],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            lambda *_a, **_k: {
                "I_1": _issue_activity(_comment("alice", ACTIVITY_AFTER)),
            },
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        set_mock.assert_not_called()
        assert stats.review_status_set == 0

    def test_skips_other_statuses(self, monkeypatch: pytest.MonkeyPatch):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [
                _ready_board_item(status_name="In progress 📋"),
                _ready_board_item(
                    item_id="PVTI_2",
                    status_name=IN_REVIEW_STATUS,
                ),
            ],
        )
        fetch_mock = MagicMock()
        monkeypatch.setattr(sync, "fetch_contents_review_activity", fetch_mock)
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        fetch_mock.assert_not_called()
        set_mock.assert_not_called()

    def test_skips_when_status_options_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        list_mock = MagicMock()
        monkeypatch.setattr(sync, "list_board_status_items", list_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _org_fields(), stats)
        list_mock.assert_not_called()
        assert stats.review_status_set == 0

    def test_records_field_write_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [_ready_board_item()],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            lambda *_a, **_k: {
                "I_1": _issue_activity(_comment("bob", ACTIVITY_AFTER)),
            },
        )
        monkeypatch.setattr(
            sync,
            "set_single_select",
            MagicMock(side_effect=RuntimeError("INSUFFICIENT_SCOPES")),
        )
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        assert stats.review_status_set == 0
        assert stats.review_status_failed == 1
        assert any("Failed advancing" in err for err in stats.errors)

    def test_records_batch_fetch_failure(self, monkeypatch: pytest.MonkeyPatch):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [
                _ready_board_item(item_id="PVTI_1", content_id="I_1"),
                _ready_board_item(item_id="PVTI_2", content_id="I_2", number=2),
            ],
        )
        monkeypatch.setattr(
            sync,
            "fetch_contents_review_activity",
            MagicMock(side_effect=RuntimeError("GraphQL errors")),
        )
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        set_mock.assert_not_called()
        assert stats.review_status_set == 0
        assert stats.review_status_failed == 2
        assert len(stats.errors) == 2

    def test_fetches_ready_items_in_one_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        client = MagicMock(dry_run=False)
        monkeypatch.setattr(
            sync,
            "list_board_status_items",
            lambda *_a, **_k: [
                _ready_board_item(item_id="PVTI_1", content_id="I_1", number=1),
                _ready_board_item(item_id="PVTI_2", content_id="I_2", number=2),
            ],
        )
        client.graphql.return_value = {
            "nodes": [
                {
                    "id": "I_1",
                    **_issue_activity(_comment("bob", ACTIVITY_AFTER)),
                },
                {
                    "id": "I_2",
                    **_issue_activity(),
                },
            ]
        }
        set_mock = MagicMock()
        monkeypatch.setattr(sync, "set_single_select", set_mock)
        stats = sync.SyncStats()
        sync.advance_ready_for_review(client, _review_fields(), stats)
        client.graphql.assert_called_once()
        query, variables = client.graphql.call_args.args
        assert "$pageSize: Int!" in query
        assert "last: $pageSize" in query
        assert "reviews(last: $pageSize)" in query
        assert variables == {
            "ids": ["I_1", "I_2"],
            "pageSize": sync.REVIEW_ACTIVITY_PAGE_SIZE,
        }
        set_mock.assert_called_once_with(
            client, "PROJECT", "PVTI_1", "STATUS_FIELD", "ST_IN_REVIEW"
        )
        assert stats.review_status_set == 1

    def test_fetch_query_passes_page_size_as_variable(self):
        client = MagicMock()
        client.graphql.return_value = {"nodes": [{"id": "I_1"}]}
        result = sync.fetch_contents_review_activity(client, ["I_1"])
        query, variables = client.graphql.call_args.args
        assert "$ids: [ID!]!" in query
        assert "$pageSize: Int!" in query
        assert "last: $pageSize" in query
        assert "reviews(last: $pageSize)" in query
        assert variables["ids"] == ["I_1"]
        assert variables["pageSize"] == sync.REVIEW_ACTIVITY_PAGE_SIZE
        assert result == {"I_1": {"id": "I_1"}}

    def test_fetch_skips_graphql_when_ids_empty(self):
        client = MagicMock()
        assert sync.fetch_contents_review_activity(client, []) == {}
        client.graphql.assert_not_called()

    def test_fetch_splits_into_configured_batches(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sync, "REVIEW_ACTIVITY_BATCH_SIZE", 2)
        client = MagicMock()
        client.graphql.side_effect = [
            {"nodes": [{"id": "I_1"}, {"id": "I_2"}]},
            {"nodes": [None, {"id": "I_3"}]},
        ]
        result = sync.fetch_contents_review_activity(
            client, ["I_1", "I_2", "I_3"]
        )
        assert client.graphql.call_count == 2
        assert client.graphql.call_args_list[0].args[1]["ids"] == ["I_1", "I_2"]
        assert client.graphql.call_args_list[1].args[1]["ids"] == ["I_3"]
        assert set(result) == {"I_1", "I_2", "I_3"}

    def test_sync_passes_configured_status_prefixes(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sync, "get_project", lambda *_a, **_k: _org_fields())
        monkeypatch.setattr(sync, "existing_content_ids", lambda *_a, **_k: set())
        monkeypatch.setattr(sync, "ensure_organizations", lambda *_a, **_k: None)
        monkeypatch.setattr(
            sync, "ensure_pr_priority_from_issues", lambda *_a, **_k: None
        )
        monkeypatch.setattr(
            sync, "list_org_repos", MagicMock(return_value=[])
        )
        captured: Dict[str, str] = {}

        def fake_advance(_client, _fields, _stats, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(sync, "advance_ready_for_review", fake_advance)
        config = _minimal_config()
        config["project"]["ready_for_review_status"] = "Ready for Review"
        config["project"]["in_review_status"] = "In Review"
        sync.sync(config, MagicMock(), org_filter={"complytime"})
        assert captured["ready_prefix"] == "Ready for Review"
        assert captured["in_review_prefix"] == "In Review"


