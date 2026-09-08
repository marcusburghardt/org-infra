# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the reusable vulnerability scan workflow."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "reusable_vuln_scan.yml"
)
OSV_JOB_NAME = "call_ext_osv_scanner"
OSV_REUSABLE_WORKFLOW_PATTERN = re.compile(
    r"google/osv-scanner-action/\.github/workflows/"
    r"osv-scanner-reusable-pr\.yml@[0-9a-f]{40}"
)
YAML_BOOLEAN_TAG = "tag:yaml.org,2002:bool"
COMPLETE_RESULT_FILES = ("old-results.json", "new-results.json")


class GitHubActionsLoader(yaml.SafeLoader):
    """Load YAML booleans without treating the GitHub Actions ``on`` key as true."""


# PyYAML follows YAML 1.1, while GitHub Actions treats only true and false as booleans.
GitHubActionsLoader.yaml_implicit_resolvers = {
    first_character: [
        (tag, pattern)
        for tag, pattern in resolvers
        if tag != YAML_BOOLEAN_TAG
    ]
    for first_character, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
GitHubActionsLoader.add_implicit_resolver(
    YAML_BOOLEAN_TAG,
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


@pytest.fixture
def workflow() -> dict[str, Any]:
    """Parse the reusable vulnerability scan workflow using GitHub-compatible booleans."""
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.load(workflow_file, Loader=GitHubActionsLoader)


def test_osv_call_disables_exports_and_preserves_security_enforcement(
    workflow: dict[str, Any],
) -> None:
    """OSV must suppress complete outputs without weakening scan enforcement."""
    osv_inputs = workflow["jobs"][OSV_JOB_NAME]["with"]

    assert osv_inputs["export-results"] is False
    assert osv_inputs["upload-sarif"] is True
    assert osv_inputs["fail-on-vuln"] is True


def test_osv_call_preserves_pinned_upstream_artifact_integration(
    workflow: dict[str, Any],
) -> None:
    """OSV must continue using the full-SHA-pinned upstream artifact workflow."""
    osv_workflow_reference = workflow["jobs"][OSV_JOB_NAME]["uses"]

    assert OSV_REUSABLE_WORKFLOW_PATTERN.fullmatch(osv_workflow_reference)


def test_workflow_does_not_expose_complete_old_or_new_result_outputs(
    workflow: dict[str, Any],
) -> None:
    """Neither the wrapper nor its OSV job may expose complete JSON reports."""
    workflow_call = workflow["on"]["workflow_call"]
    osv_job = workflow["jobs"][OSV_JOB_NAME]

    assert "outputs" not in workflow_call, (
        f"workflow_call must not expose complete reports: {COMPLETE_RESULT_FILES}"
    )
    assert "outputs" not in osv_job, (
        f"OSV job must not expose complete reports: {COMPLETE_RESULT_FILES}"
    )


def test_osv_call_preserves_exact_least_privilege_permissions(
    workflow: dict[str, Any],
) -> None:
    """The workflow and OSV job must retain their minimal permission sets."""
    assert workflow["permissions"] == {
        "contents": "none",
        "security-events": "none",
        "actions": "none",
    }
    assert workflow["jobs"][OSV_JOB_NAME]["permissions"] == {
        "contents": "read",
        "actions": "read",
        "security-events": "write",
    }
