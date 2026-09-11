# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the reusable CodeQL analysis workflow.

Validates the structural contract (inputs, permissions, action pins, step
ordering, conditionals) by parsing the workflow YAML. Does NOT execute
CodeQL analysis -- runtime behavior is verified via downstream adoption.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "reusable_codeql.yml"
)
ANALYZE_JOB_NAME = "analyze"
YAML_BOOLEAN_TAG = "tag:yaml.org,2002:bool"


class GitHubActionsLoader(yaml.SafeLoader):
    """Load YAML without treating the GitHub Actions ``on`` key as true."""


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
    """Parse the reusable CodeQL workflow."""
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.load(workflow_file, Loader=GitHubActionsLoader)


@pytest.fixture
def inputs(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract workflow_call inputs."""
    return workflow["on"]["workflow_call"]["inputs"]


@pytest.fixture
def job(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract the analyze job."""
    return workflow["jobs"][ANALYZE_JOB_NAME]


@pytest.fixture
def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the analyze job steps."""
    return job["steps"]


def test_language_input_is_required_with_no_default(
    inputs: dict[str, Any],
) -> None:
    """The language input must be required without a default value."""
    language = inputs["language"]
    assert language["required"] is True
    assert "default" not in language, (
        "language must not have a default -- callers must explicitly specify it"
    )


def test_optional_inputs_have_correct_defaults(
    inputs: dict[str, Any],
) -> None:
    """Optional inputs must have the specified defaults from the spec."""
    assert inputs["go-version-file"]["default"] == "go.mod"
    assert inputs["build-command"]["default"] == ""
    assert inputs["query-suite"]["default"] == "default"
    assert inputs["fail-on-alert"]["default"] is False


def test_all_inputs_have_descriptions(
    inputs: dict[str, Any],
) -> None:
    """Every input must have a non-empty description field."""
    for name, config in inputs.items():
        assert "description" in config, f"Input '{name}' missing description"
        assert len(config["description"].strip()) > 0, (
            f"Input '{name}' has empty description"
        )


def test_workflow_level_permissions_deny_all(
    workflow: dict[str, Any],
) -> None:
    """Workflow-level permissions must deny all access."""
    assert workflow["permissions"] == {}


def test_job_level_permissions_are_least_privilege(
    job: dict[str, Any],
) -> None:
    """Job must have exactly contents:read, security-events:write, actions:read."""
    assert job["permissions"] == {
        "contents": "read",
        "security-events": "write",
        "actions": "read",
    }


def test_all_action_refs_are_sha_pinned(
    steps: list[dict[str, Any]],
) -> None:
    """Every uses: reference must be a 40-char SHA with version comment."""
    for step in steps:
        uses = step.get("uses")
        if uses is None:
            continue
        assert re.match(r"^[^@]+@[0-9a-f]{40}", uses), (
            f"Action ref not SHA-pinned: {uses}"
        )


def test_setup_go_appears_before_codeql_init(
    steps: list[dict[str, Any]],
) -> None:
    """setup-go must execute before codeql/init for correct Go tracer binding."""
    step_names = [s.get("name", "") for s in steps]
    setup_go_indices = [
        i for i, name in enumerate(step_names) if "Setup Go" in name
    ]
    init_indices = [
        i for i, name in enumerate(step_names) if "Initialize CodeQL" in name
    ]
    assert len(setup_go_indices) == 1, "Expected exactly one Setup Go step"
    assert len(init_indices) == 1, "Expected exactly one Initialize CodeQL step"
    assert setup_go_indices[0] < init_indices[0], (
        "setup-go must appear before codeql/init"
    )


def test_setup_go_is_conditional_on_go_language(
    steps: list[dict[str, Any]],
) -> None:
    """setup-go step must be conditioned on language == 'go'."""
    setup_go_steps = [s for s in steps if "Setup Go" in s.get("name", "")]
    assert len(setup_go_steps) == 1
    condition = setup_go_steps[0].get("if", "")
    assert "inputs.language" in condition, (
        f"setup-go must check inputs.language, got: {condition}"
    )
    assert "'go'" in condition or '"go"' in condition, (
        f"setup-go condition must compare to 'go', got: {condition}"
    )


def test_job_has_timeout_minutes(
    job: dict[str, Any],
) -> None:
    """The analyze job must set a timeout to prevent stuck runs."""
    assert "timeout-minutes" in job, (
        "Job must set timeout-minutes to prevent 6-hour default"
    )
    assert isinstance(job["timeout-minutes"], int)
    assert job["timeout-minutes"] > 0


def test_concurrency_block_exists(
    workflow: dict[str, Any],
) -> None:
    """The workflow must define a concurrency group with cancel-in-progress."""
    assert "concurrency" in workflow, "Workflow must define a concurrency block"
    concurrency = workflow["concurrency"]
    assert "group" in concurrency
    assert concurrency.get("cancel-in-progress") is True


def test_workflow_does_not_expose_outputs(
    workflow: dict[str, Any],
) -> None:
    """workflow_call must not expose outputs -- SARIF uploads directly."""
    workflow_call = workflow["on"]["workflow_call"]
    assert "outputs" not in workflow_call, (
        "Workflow must not expose outputs; SARIF is uploaded directly"
    )


def test_checkout_does_not_persist_credentials(
    steps: list[dict[str, Any]],
) -> None:
    """Checkout step must set persist-credentials: false."""
    checkout_steps = [
        s for s in steps if "checkout" in s.get("uses", "").lower()
    ]
    assert len(checkout_steps) == 1
    checkout_with = checkout_steps[0].get("with", {})
    assert checkout_with.get("persist-credentials") is False


def test_build_command_uses_env_var_not_inline(
    steps: list[dict[str, Any]],
) -> None:
    """Custom build step must use env var, not inline interpolation."""
    custom_build_steps = [
        s for s in steps if "Custom Build" in s.get("name", "")
    ]
    assert len(custom_build_steps) == 1
    step = custom_build_steps[0]
    env = step.get("env", {})
    assert "BUILD_COMMAND" in env, (
        "build-command must be passed via BUILD_COMMAND env var"
    )
    run_content = step.get("run", "")
    assert "${{ inputs.build-command }}" not in run_content, (
        "build-command must not be inline-interpolated in the run block"
    )
