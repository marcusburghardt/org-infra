# SPDX-License-Identifier: Apache-2.0

"""Tests for sync-compliance-targets.py."""

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add scripts to path for import.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

sync_ct = importlib.import_module("sync-compliance-targets")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PERIBOLOS = {
    "orgs": {
        "complytime": {
            "repos": {
                "complyapi": {},
                "complyctl": {},
                "org-infra": {},
                "complytime-providers": {},
            },
        },
    },
}

SAMPLE_COMPLYTIME = {
    "policies": [
        {
            "url": "quay.io/complytime/policies-ampel-bp:latest",
            "id": "ampel-bp",
        },
    ],
    "complypacks": [
        {
            "url": "quay.io/complytime/complypack-ampel-bp:latest",
            "id": "ampel-bp-pack",
        },
    ],
    "targets": [
        {
            "id": "complytime-complyapi",
            "policies": ["ampel-bp"],
            "variables": {
                "url": "https://github.com/complytime/complyapi",
                "specs": "builtin:github/branch-rules.yaml",
            },
        },
        {
            "id": "complytime-complyctl",
            "policies": ["ampel-bp"],
            "variables": {
                "url": "https://github.com/complytime/complyctl",
                "specs": "builtin:github/branch-rules.yaml",
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# TestExtractPeribolosRepos
# ---------------------------------------------------------------------------


class TestExtractPeribolosRepos:
    """Tests for extract_peribolos_repos."""

    def test_extracts_repos(self):
        repos = sync_ct.extract_peribolos_repos(
            SAMPLE_PERIBOLOS, "complytime",
        )
        assert repos == {
            "complyapi", "complyctl", "org-infra",
            "complytime-providers",
        }

    def test_empty_org(self):
        data = {"orgs": {"complytime": {}}}
        repos = sync_ct.extract_peribolos_repos(data, "complytime")
        assert repos == set()

    def test_repos_none(self):
        data = {"orgs": {"complytime": {"repos": None}}}
        repos = sync_ct.extract_peribolos_repos(data, "complytime")
        assert repos == set()

    def test_missing_org_exits(self, capsys):
        data = {"orgs": {"other": {"repos": {"repo1": {}}}}}
        with pytest.raises(SystemExit) as exc_info:
            sync_ct.extract_peribolos_repos(data, "complytime")
        assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_invalid_repo_name_skipped(self, capsys):
        data = {
            "orgs": {
                "complytime": {
                    "repos": {
                        "valid-repo": {},
                        "invalid repo name!": {},
                    },
                },
            },
        }
        repos = sync_ct.extract_peribolos_repos(data, "complytime")
        assert repos == {"valid-repo"}
        captured = capsys.readouterr()
        assert "skipping invalid repo name" in captured.err


# ---------------------------------------------------------------------------
# TestExtractComplytimeRepos
# ---------------------------------------------------------------------------


class TestExtractComplytimeRepos:
    """Tests for extract_complytime_repos."""

    def test_extracts_repos_from_urls(self):
        repos = sync_ct.extract_complytime_repos(SAMPLE_COMPLYTIME)
        assert repos == {"complyapi", "complyctl"}

    def test_empty_targets(self):
        data = {"policies": [], "complypacks": [], "targets": []}
        repos = sync_ct.extract_complytime_repos(data)
        assert repos == set()

    def test_missing_targets_key(self):
        data = {"policies": [], "complypacks": []}
        repos = sync_ct.extract_complytime_repos(data)
        assert repos == set()

    def test_target_without_url(self):
        data = {
            "targets": [
                {"id": "test", "policies": [], "variables": {}},
            ],
        }
        repos = sync_ct.extract_complytime_repos(data)
        assert repos == set()

    def test_trailing_slash_in_url(self):
        data = {
            "targets": [
                {
                    "id": "test",
                    "policies": [],
                    "variables": {
                        "url": "https://github.com/complytime/repo/",
                    },
                },
            ],
        }
        repos = sync_ct.extract_complytime_repos(data)
        assert repos == {"repo"}


# ---------------------------------------------------------------------------
# TestComputeDrift
# ---------------------------------------------------------------------------


class TestComputeDrift:
    """Tests for compute_drift."""

    def test_no_drift(self):
        repos = {"complyapi", "complyctl"}
        added, removed = sync_ct.compute_drift(repos, repos)
        assert added == set()
        assert removed == set()

    def test_added_repos(self):
        peribolos = {"complyapi", "complyctl", "new-repo"}
        complytime = {"complyapi", "complyctl"}
        added, removed = sync_ct.compute_drift(peribolos, complytime)
        assert added == {"new-repo"}
        assert removed == set()

    def test_removed_repos(self):
        peribolos = {"complyapi"}
        complytime = {"complyapi", "complyctl"}
        added, removed = sync_ct.compute_drift(peribolos, complytime)
        assert added == set()
        assert removed == {"complyctl"}

    def test_mixed_drift(self):
        peribolos = {"complyapi", "new-repo"}
        complytime = {"complyapi", "old-repo"}
        added, removed = sync_ct.compute_drift(peribolos, complytime)
        assert added == {"new-repo"}
        assert removed == {"old-repo"}


# ---------------------------------------------------------------------------
# TestMakeTargetId
# ---------------------------------------------------------------------------


class TestMakeTargetId:
    """Tests for make_target_id."""

    def test_plain_repo_gets_prefix(self):
        assert sync_ct.make_target_id("complyapi") == "complytime-complyapi"

    def test_org_infra_gets_prefix(self):
        assert sync_ct.make_target_id("org-infra") == "complytime-org-infra"

    def test_already_prefixed_not_doubled(self):
        assert (
            sync_ct.make_target_id("complytime-providers")
            == "complytime-providers"
        )

    def test_already_prefixed_collector(self):
        assert (
            sync_ct.make_target_id("complytime-collector-components")
            == "complytime-collector-components"
        )


# ---------------------------------------------------------------------------
# TestGenerateComplytime
# ---------------------------------------------------------------------------


class TestGenerateComplytime:
    """Tests for generate_complytime."""

    def test_preserves_policies(self):
        repos = {"complyapi"}
        result = sync_ct.generate_complytime(
            SAMPLE_COMPLYTIME, repos, "complytime",
        )
        assert result["policies"] == SAMPLE_COMPLYTIME["policies"]

    def test_preserves_complypacks(self):
        repos = {"complyapi"}
        result = sync_ct.generate_complytime(
            SAMPLE_COMPLYTIME, repos, "complytime",
        )
        assert result["complypacks"] == SAMPLE_COMPLYTIME["complypacks"]

    def test_generates_correct_target(self):
        repos = {"complyapi"}
        result = sync_ct.generate_complytime(
            SAMPLE_COMPLYTIME, repos, "complytime",
        )
        assert len(result["targets"]) == 1
        target = result["targets"][0]
        assert target["id"] == "complytime-complyapi"
        assert target["policies"] == ["ampel-bp"]
        assert (
            target["variables"]["url"]
            == "https://github.com/complytime/complyapi"
        )
        assert (
            target["variables"]["specs"]
            == "builtin:github/branch-rules.yaml"
        )

    def test_already_prefixed_repo_target(self):
        repos = {"complytime-providers"}
        result = sync_ct.generate_complytime(
            SAMPLE_COMPLYTIME, repos, "complytime",
        )
        target = result["targets"][0]
        assert target["id"] == "complytime-providers"
        assert (
            target["variables"]["url"]
            == "https://github.com/complytime/complytime-providers"
        )

    def test_targets_sorted_by_id(self):
        repos = {"org-infra", "complyapi", "complytime-providers"}
        result = sync_ct.generate_complytime(
            SAMPLE_COMPLYTIME, repos, "complytime",
        )
        ids = [t["id"] for t in result["targets"]]
        assert ids == sorted(ids)

    def test_multiple_policies_applied(self):
        data = {
            "policies": [
                {"url": "policy-a:latest", "id": "pol-a"},
                {"url": "policy-b:latest", "id": "pol-b"},
            ],
            "complypacks": [],
            "targets": [],
        }
        repos = {"repo1"}
        result = sync_ct.generate_complytime(data, repos, "testorg")
        assert result["targets"][0]["policies"] == ["pol-a", "pol-b"]

    def test_policy_without_id_key_skipped(self):
        data = {
            "policies": [
                {"url": "policy-a:latest", "id": "pol-a"},
                {"url": "policy-orphan:latest"},
            ],
            "complypacks": [],
            "targets": [],
        }
        repos = {"repo1"}
        result = sync_ct.generate_complytime(data, repos, "testorg")
        assert result["targets"][0]["policies"] == ["pol-a"]

    def test_null_policies_treated_as_empty(self):
        data = {
            "policies": None,
            "complypacks": None,
            "targets": [],
        }
        repos = {"repo1"}
        result = sync_ct.generate_complytime(data, repos, "testorg")
        assert result["targets"][0]["policies"] == []
        assert result["policies"] == []
        assert result["complypacks"] == []


# ---------------------------------------------------------------------------
# TestLoadYamlFile
# ---------------------------------------------------------------------------


class TestLoadYamlFile:
    """Tests for load_yaml_file."""

    def test_loads_valid_yaml(self, tmp_path):
        path = tmp_path / "test.yaml"
        path.write_text("key: value\n")
        result = sync_ct.load_yaml_file(str(path), "test file")
        assert result == {"key": "value"}

    def test_missing_file_exits(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            sync_ct.load_yaml_file("/nonexistent/path.yaml", "test")
        assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_invalid_yaml_exits(self, tmp_path, capsys):
        path = tmp_path / "bad.yaml"
        path.write_text(":\n  - :\n    invalid: [")
        with pytest.raises(SystemExit) as exc_info:
            sync_ct.load_yaml_file(str(path), "test")
        assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "failed to parse" in captured.err

    def test_non_dict_yaml_exits(self, tmp_path, capsys):
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n")
        with pytest.raises(SystemExit) as exc_info:
            sync_ct.load_yaml_file(str(path), "test")
        assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "not a valid YAML mapping" in captured.err


# ---------------------------------------------------------------------------
# TestMainCLI
# ---------------------------------------------------------------------------


class TestMainCLI:
    """Tests for main() CLI behavior and exit codes."""

    def _write_fixtures(
        self, tmp_path, peribolos_data, complytime_data,
    ):
        """Write fixture YAML files and return their paths."""
        peribolos_path = tmp_path / "peribolos.yaml"
        complytime_path = tmp_path / "complytime.yaml"
        output_path = tmp_path / "output.yaml"

        peribolos_path.write_text(yaml.dump(peribolos_data))
        complytime_path.write_text(yaml.dump(complytime_data))

        return str(peribolos_path), str(complytime_path), str(output_path)

    def test_no_drift_exits_zero(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {"complyapi": {}, "complyctl": {}},
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            result = sync_ct.main()
        assert result == sync_ct.EXIT_OK
        assert not os.path.exists(o_path)

    def test_drift_exits_two(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {
                        "complyapi": {},
                        "complyctl": {},
                        "new-repo": {},
                    },
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            result = sync_ct.main()
        assert result == sync_ct.EXIT_DRIFT
        assert os.path.exists(o_path)

        with open(o_path) as f:
            output_data = yaml.safe_load(f)
        target_ids = [t["id"] for t in output_data["targets"]]
        assert "complytime-complyapi" in target_ids
        assert "complytime-complyctl" in target_ids
        assert "complytime-new-repo" in target_ids
        assert len(target_ids) == 3

    def test_missing_peribolos_exits_one(self, tmp_path, capsys):
        _, c_path, o_path = self._write_fixtures(
            tmp_path, {}, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", "/nonexistent/peribolos.yaml",
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                sync_ct.main()
            assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_missing_org_exits_one(self, tmp_path, capsys):
        peribolos = {"orgs": {"other-org": {"repos": {"repo1": {}}}}}
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                sync_ct.main()
            assert exc_info.value.code == sync_ct.EXIT_ERROR
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_output_preserves_policies_and_complypacks(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {"complyapi": {}, "new-repo": {}},
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            sync_ct.main()

        with open(o_path) as f:
            output_data = yaml.safe_load(f)
        assert output_data["policies"] == SAMPLE_COMPLYTIME["policies"]
        assert (
            output_data["complypacks"] == SAMPLE_COMPLYTIME["complypacks"]
        )

    def test_exclude_removes_repos_from_comparison(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {
                        "complyapi": {},
                        "complyctl": {},
                        ".github": {},
                        "complyscribe": {},
                    },
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
                "--exclude", ".github,complyscribe",
            ],
        ):
            result = sync_ct.main()
        assert result == sync_ct.EXIT_OK

    def test_exclude_does_not_add_excluded_repos(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {
                        "complyapi": {},
                        "complyctl": {},
                        "new-repo": {},
                        ".github": {},
                    },
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
                "--exclude", ".github",
            ],
        ):
            result = sync_ct.main()
        assert result == sync_ct.EXIT_DRIFT

        with open(o_path) as f:
            output_data = yaml.safe_load(f)
        target_ids = [t["id"] for t in output_data["targets"]]
        assert "complytime-new-repo" in target_ids
        assert "complytime-.github" not in target_ids

    def test_removal_drift_exits_two(self, tmp_path):
        peribolos = {
            "orgs": {
                "complytime": {
                    "repos": {"complyapi": {}},
                },
            },
        }
        p_path, c_path, o_path = self._write_fixtures(
            tmp_path, peribolos, SAMPLE_COMPLYTIME,
        )
        with patch(
            "sys.argv",
            [
                "sync-compliance-targets.py",
                "--peribolos", p_path,
                "--complytime", c_path,
                "--org", "complytime",
                "--output", o_path,
            ],
        ):
            result = sync_ct.main()
        assert result == sync_ct.EXIT_DRIFT

        with open(o_path) as f:
            output_data = yaml.safe_load(f)
        target_ids = [t["id"] for t in output_data["targets"]]
        assert "complytime-complyctl" not in target_ids
        assert "complytime-complyapi" in target_ids
