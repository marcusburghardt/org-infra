#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Sync open issues/PRs from configured orgs into a GitHub Project (v2).

Discovers repositories across one or more organizations, optionally links
them to the target project, and adds any open issues/PRs that are not
already on the board. Newly added items (and any existing items missing a
value) get Organization set from the source GitHub org. PRs inherit Priority
from linked issues when that field is empty. Items in Ready for Review move
to In Review when a non-author human comments or submits a PR review.
Designed for cross-org boards where a single GitHub App installation token
is insufficient (use a PAT with multi-org access).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from lib.github_client import GitHubClient
from lib.project_config import load_config, parse_project_target

DEFAULT_CONFIG = "project-sync-config.yml"

# Map GitHub repository owner login → Organization single-select option name
# on the Compliance Automation planning board.
OWNER_TO_ORGANIZATION = {
    "Agentic-SSDLC": "Agentic-SSDLC",
    "complytime": "complytime",
    # Not in project-sync-config.yml yet; maps to complytime when labs repos
    # land on the board (manual add or future sync scope).
    "complytime-labs": "complytime",
    "unbound-force": "unbound-force",
}

# Expected failure modes while iterating orgs/repos (HTTP + explicit RuntimeError).
# Keeps programming bugs (TypeError, KeyError, …) from being swallowed per item.
SYNC_EXCEPTIONS = (requests.RequestException, RuntimeError)

# Project Priority / Review priority option names, highest first.
PRIORITY_RANK = {"Urgent": 4, "High": 3, "Medium": 2, "Low": 1}

# Status prefixes on the planning board. Option names include emojis
# ("Ready for Review  👀", "In Review 🏁"); matching is by prefix.
DEFAULT_READY_FOR_REVIEW_STATUS = "Ready for Review"
DEFAULT_IN_REVIEW_STATUS = "In Review"

# How many recent comments/reviews to inspect per Ready for Review item.
REVIEW_ACTIVITY_PAGE_SIZE = 30
# GitHub nodes(ids:) accepts at most 100 IDs; keep batches smaller so
# comments(last:) + reviews(last:) stay within query complexity limits.
REVIEW_ACTIVITY_BATCH_SIZE = 50

# Submitted review states. PENDING is an unsubmitted draft and is ignored.
COUNTABLE_REVIEW_STATES = frozenset(
    {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}
)


@dataclass
class SyncStats:
    """Counters written to the job summary."""

    repos_considered: int = 0
    repos_linked: int = 0
    repos_link_skipped: int = 0
    items_seen: int = 0
    items_already_on_board: int = 0
    items_added: int = 0
    items_failed: int = 0
    organization_set: int = 0
    organization_failed: int = 0
    priority_set: int = 0
    priority_failed: int = 0
    priority_unmapped: int = 0
    review_status_set: int = 0
    review_status_failed: int = 0
    errors: List[str] = field(default_factory=list)


# How many closing-issue refs to fetch per PR. Warn when GitHub has more.
CLOSING_ISSUES_PAGE_SIZE = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Path to sync config (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover work and report actions without mutating the project",
    )
    parser.add_argument(
        "--orgs",
        default="",
        help="Optional space-separated org filter (defaults to all configured orgs)",
    )
    parser.add_argument(
        "--backfill-org",
        choices=("auto", "always", "never"),
        default="auto",
        help=(
            "When to walk existing board items to fix Organization. "
            "auto skips that extra listing when this tick already set "
            "Organization on newly added items (default: auto)"
        ),
    )
    return parser.parse_args()


def validate_config(config: Any) -> Dict[str, Any]:
    """Validate required sync config shape; return the config on success."""
    parse_project_target(config)
    organizations = config.get("organizations")
    if not isinstance(organizations, list) or not organizations:
        raise ValueError("Config requires a non-empty 'organizations' list")
    for org in organizations:
        if not isinstance(org, dict) or not org.get("name"):
            raise ValueError("Each organization requires a 'name'")
    return config


def list_org_repos(
    client: GitHubClient,
    org: str,
    *,
    exclude: Set[str],
    skip_archived: bool,
) -> List[Dict[str, Any]]:
    repos = client.rest_paginate(f"/orgs/{org}/repos", {"type": "all", "sort": "full_name"})
    selected = []
    for repo in repos:
        name = repo["name"]
        if name in exclude:
            continue
        if skip_archived and repo.get("archived"):
            continue
        selected.append(repo)
    return selected


@dataclass
class ProjectFields:
    """Resolved project id plus single-select field metadata."""

    project_id: str
    status_field_id: Optional[str]
    status_options: Dict[str, str]
    organization_field_id: Optional[str]
    organization_options: Dict[str, str]
    priority_field_id: Optional[str] = None
    priority_options: Dict[str, str] = field(default_factory=dict)
    review_priority_field_id: Optional[str] = None
    review_priority_options: Dict[str, str] = field(default_factory=dict)


@dataclass
class AddItemResult:
    """Outcome of adding a project item and optionally setting Organization.

    ``item_id`` is None in dry-run mode (no mutation, so no board item id).
    Organization field updates are best-effort: a failure is recorded on this
    result instead of raising, so the caller can still treat the add as success.
    """

    item_id: Optional[str]
    organization_set: bool = False
    organization_error: Optional[str] = None


def get_project(client: GitHubClient, owner: str, number: int) -> ProjectFields:
    """Return project id and Status / Organization / Priority field metadata."""
    data = client.graphql(
        """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              fields(first: 50) {
                nodes {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    options { id name }
                  }
                }
              }
            }
          }
        }
        """,
        {"owner": owner, "number": number},
    )
    project = data["organization"]["projectV2"]
    if not project:
        raise RuntimeError(f"Project #{number} not found in org {owner}")

    fields = ProjectFields(
        project_id=project["id"],
        status_field_id=None,
        status_options={},
        organization_field_id=None,
        organization_options={},
    )
    for node in project["fields"]["nodes"]:
        if not node:
            continue
        name = node.get("name")
        options = {opt["name"]: opt["id"] for opt in node.get("options", [])}
        if name == "Status":
            fields.status_field_id = node["id"]
            fields.status_options = options
        elif name == "Organization":
            fields.organization_field_id = node["id"]
            fields.organization_options = options
        elif name == "Priority":
            fields.priority_field_id = node["id"]
            fields.priority_options = options
        elif name == "Review priority":
            fields.review_priority_field_id = node["id"]
            fields.review_priority_options = options
    return fields


def _paginate_project_item_nodes(
    client: GitHubClient, project_id: str, query: str
) -> List[Dict[str, Any]]:
    """Walk ProjectV2 item pages until exhausted."""
    collected: List[Dict[str, Any]] = []
    cursor = None
    while True:
        data = client.graphql(query, {"projectId": project_id, "cursor": cursor})
        items = data["node"]["items"]
        collected.extend(items["nodes"])
        if not items["pageInfo"]["hasNextPage"]:
            break
        cursor = items["pageInfo"]["endCursor"]
    return collected


def existing_content_ids(client: GitHubClient, project_id: str) -> Set[str]:
    """Return node IDs of issues/PRs already on the project."""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              content {
                ... on Issue { id }
                ... on PullRequest { id }
              }
            }
          }
        }
      }
    }
    """
    ids: Set[str] = set()
    for node in _paginate_project_item_nodes(client, project_id, query):
        content = node.get("content") or {}
        content_id = content.get("id")
        if content_id:
            ids.add(content_id)
    return ids


def link_repository(client: GitHubClient, project_id: str, repository_id: str) -> bool:
    """Link a repository to the project. Returns True if a link was created."""
    if client.dry_run:
        print(f"  [dry-run] would link repository {repository_id}")
        return True
    try:
        client.graphql(
            """
            mutation($projectId: ID!, $repositoryId: ID!) {
              linkProjectV2ToRepository(input: {
                projectId: $projectId
                repositoryId: $repositoryId
              }) {
                repository { id nameWithOwner }
              }
            }
            """,
            {"projectId": project_id, "repositoryId": repository_id},
        )
        return True
    except RuntimeError as exc:
        message = str(exc)
        # Already linked is not a failure for idempotent syncs.
        if "already linked" in message.lower() or "already exists" in message.lower():
            return False
        raise


def list_open_items(
    client: GitHubClient,
    full_name: str,
    *,
    include_issues: bool,
    include_prs: bool,
) -> List[Dict[str, Any]]:
    """List open issues and/or PRs for a repository via REST."""
    items: List[Dict[str, Any]] = []
    # /issues returns issues + PRs; filter client-side.
    raw = client.rest_paginate(
        f"/repos/{full_name}/issues",
        {"state": "open", "direction": "asc"},
    )
    for entry in raw:
        is_pr = "pull_request" in entry
        if is_pr and not include_prs:
            continue
        if (not is_pr) and not include_issues:
            continue
        items.append(entry)
    return items


def set_single_select(
    client: GitHubClient,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
) -> None:
    """Set a project single-select field value."""
    if client.dry_run:
        print(f"  [dry-run] would set field {field_id}={option_id} on {item_id}")
        return
    client.graphql(
        """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { singleSelectOptionId: $optionId }
          }) {
            projectV2Item { id }
          }
        }
        """,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": option_id,
        },
    )


def organization_option_for_owner(
    owner_login: str, organization_options: Dict[str, str]
) -> Optional[Tuple[str, str]]:
    """Return (option_name, option_id) for a repository owner, if mapped."""
    option_name = OWNER_TO_ORGANIZATION.get(owner_login)
    if not option_name:
        return None
    option_id = organization_options.get(option_name)
    if not option_id:
        return None
    return option_name, option_id


def add_item(
    client: GitHubClient,
    project_id: str,
    content_id: str,
    status_field_id: Optional[str],
    status_option_id: Optional[str],
    organization_field_id: Optional[str] = None,
    organization_option_id: Optional[str] = None,
) -> AddItemResult:
    """Add content to the project and set Status / Organization.

    Returns an ``AddItemResult``. In dry-run mode ``item_id`` is None.
    Organization updates are best-effort: if ``set_single_select`` fails after
    the item was added, the result still includes the item id so the caller
    can record a successful add.
    """
    if client.dry_run:
        print(f"  [dry-run] would add {content_id}")
        return AddItemResult(
            item_id=None,
            organization_set=bool(organization_field_id and organization_option_id),
        )

    data = client.graphql(
        """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        """,
        {"projectId": project_id, "contentId": content_id},
    )
    item_id = data["addProjectV2ItemById"]["item"]["id"]

    if status_field_id and status_option_id:
        set_single_select(
            client, project_id, item_id, status_field_id, status_option_id
        )

    organization_set = False
    organization_error: Optional[str] = None
    if organization_field_id and organization_option_id:
        try:
            set_single_select(
                client,
                project_id,
                item_id,
                organization_field_id,
                organization_option_id,
            )
            organization_set = True
        except SYNC_EXCEPTIONS as exc:
            organization_error = str(exc)

    return AddItemResult(
        item_id=item_id,
        organization_set=organization_set,
        organization_error=organization_error,
    )


def list_board_items_with_org_metadata(
    client: GitHubClient, project_id: str
) -> List[Dict[str, Any]]:
    """Return all board items with Organization value and content repository owner."""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              organization: fieldValueByName(name: "Organization") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
              content {
                ... on Issue {
                  id
                  repository { owner { login } nameWithOwner }
                }
                ... on PullRequest {
                  id
                  repository { owner { login } nameWithOwner }
                }
              }
            }
          }
        }
      }
    }
    """
    return _paginate_project_item_nodes(client, project_id, query)


def ensure_organizations(
    client: GitHubClient,
    fields: ProjectFields,
    stats: SyncStats,
) -> None:
    """Set Organization on board items that are missing or incorrect."""
    if not fields.organization_field_id or not fields.organization_options:
        print("Organization field missing on project; skipping organization sync")
        return

    print("\n=== Ensuring Organization on existing board items ===")
    for node in list_board_items_with_org_metadata(client, fields.project_id):
        content = node.get("content") or {}
        repo = content.get("repository") or {}
        owner_login = (repo.get("owner") or {}).get("login")
        if not owner_login:
            continue
        mapped = organization_option_for_owner(owner_login, fields.organization_options)
        if not mapped:
            continue
        option_name, option_id = mapped
        current = (node.get("organization") or {}).get("name")
        if current == option_name:
            continue
        item_id = node["id"]
        label = repo.get("nameWithOwner") or owner_login
        try:
            set_single_select(
                client,
                fields.project_id,
                item_id,
                fields.organization_field_id,
                option_id,
            )
            stats.organization_set += 1
            print(f"  org {label} -> {option_name}")
        except SYNC_EXCEPTIONS as exc:
            stats.organization_failed += 1
            msg = f"Failed setting Organization on {label}: {exc}"
            print(f"  ! {msg}")
            stats.errors.append(msg)


def should_run_organization_backfill(backfill_org: str, stats: SyncStats) -> bool:
    """Decide whether to paginate the board to fix Organization values.

    ``auto`` skips the extra listing when this tick already added items and no
    add-time Organization update failed. Quiet ticks still backfill so
    manually added items are corrected within one schedule interval.
    """
    if backfill_org == "always":
        return True
    if backfill_org == "never":
        return False
    return stats.items_added == 0 or stats.organization_failed > 0


def highest_priority(names: List[Optional[str]]) -> Optional[str]:
    """Return the highest named Priority among known options, if any."""
    ranked = [name for name in names if name in PRIORITY_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda name: PRIORITY_RANK[name])


def remember_highest_priority(
    store: Dict[str, str], issue_id: str, priority_name: str
) -> None:
    """Keep the highest-ranked Priority if the same issue is seen twice."""
    winner = highest_priority([store.get(issue_id), priority_name])
    if winner:
        store[issue_id] = winner


def list_board_priority_items(
    client: GitHubClient, project_id: str
) -> List[Dict[str, Any]]:
    """Return board items with Priority, Review priority, and linked issues."""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              priority: fieldValueByName(name: "Priority") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
              reviewPriority: fieldValueByName(name: "Review priority") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
              content {
                __typename
                ... on Issue { id }
                ... on PullRequest {
                  id
                  number
                  repository { nameWithOwner }
                  closingIssuesReferences(first: __CLOSING_LIMIT__) {
                    pageInfo { hasNextPage }
                    nodes { id }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    query = query.replace("__CLOSING_LIMIT__", str(CLOSING_ISSUES_PAGE_SIZE))
    return _paginate_project_item_nodes(client, project_id, query)


def _copy_priority_field(
    client: GitHubClient,
    project_id: str,
    item_id: str,
    option_name: str,
    field_id: Optional[str],
    options: Dict[str, str],
    stats: SyncStats,
    label: str,
) -> None:
    """Copy a named priority onto one single-select field when it is mapped."""
    if not field_id:
        return
    option_id = options.get(option_name)
    if not option_id:
        stats.priority_unmapped += 1
        print(f"  skip {label}: no option named '{option_name}'")
        return
    try:
        set_single_select(client, project_id, item_id, field_id, option_id)
        stats.priority_set += 1
        print(f"  priority {label} -> {option_name}")
    except SYNC_EXCEPTIONS as exc:
        stats.priority_failed += 1
        msg = f"Failed copying Priority onto {label}: {exc}"
        print(f"  ! {msg}")
        stats.errors.append(msg)


def ensure_pr_priority_from_issues(
    client: GitHubClient,
    fields: ProjectFields,
    stats: SyncStats,
) -> None:
    """Set empty PR Priority / Review priority from linked issues.

    Uses ``closingIssuesReferences`` (Fixes/Closes and Development links).
    Does not default a value when there is no linked issue, or when linked
    issues have no Priority. Does not overwrite a value already set on the PR.
    If several linked issues have Priority, the highest rank wins.
    """
    if not fields.priority_field_id and not fields.review_priority_field_id:
        print("Priority fields missing on project; skipping PR priority copy")
        return

    print("\n=== Copying Priority from linked issues onto PRs ===")
    issue_priority: Dict[str, str] = {}
    pr_nodes: List[Dict[str, Any]] = []
    for node in list_board_priority_items(client, fields.project_id):
        content = node.get("content") or {}
        content_id = content.get("id")
        if not content_id:
            continue
        current = (node.get("priority") or {}).get("name")
        typename = content.get("__typename")
        if typename == "Issue":
            if current:
                remember_highest_priority(issue_priority, content_id, current)
            continue
        if typename == "PullRequest":
            pr_nodes.append(node)

    for node in pr_nodes:
        content = node.get("content") or {}
        linked = content.get("closingIssuesReferences") or {}
        repo = (content.get("repository") or {}).get("nameWithOwner") or "unknown"
        number = content.get("number")
        label = f"{repo}#{number}" if number is not None else repo
        if (linked.get("pageInfo") or {}).get("hasNextPage"):
            print(
                f"  warning: closing issues truncated at "
                f"{CLOSING_ISSUES_PAGE_SIZE} for {label}"
            )
        linked_ids = [item.get("id") for item in linked.get("nodes") or []]
        wanted = highest_priority([issue_priority.get(cid) for cid in linked_ids])
        if not wanted:
            continue
        item_id = node["id"]
        current_priority = (node.get("priority") or {}).get("name")
        current_review = (node.get("reviewPriority") or {}).get("name")
        if not current_priority:
            _copy_priority_field(
                client,
                fields.project_id,
                item_id,
                wanted,
                fields.priority_field_id,
                fields.priority_options,
                stats,
                f"Priority {label}",
            )
        if not current_review:
            _copy_priority_field(
                client,
                fields.project_id,
                item_id,
                wanted,
                fields.review_priority_field_id,
                fields.review_priority_options,
                stats,
                f"Review priority {label}",
            )


def review_status_prefixes(config: Dict[str, Any]) -> Tuple[str, str]:
    """Return (ready_for_review, in_review) Status prefixes from config."""
    project = config.get("project") or {}
    ready = project.get("ready_for_review_status") or DEFAULT_READY_FOR_REVIEW_STATUS
    in_review = project.get("in_review_status") or DEFAULT_IN_REVIEW_STATUS
    if not isinstance(ready, str) or not ready.strip():
        ready = DEFAULT_READY_FOR_REVIEW_STATUS
    if not isinstance(in_review, str) or not in_review.strip():
        in_review = DEFAULT_IN_REVIEW_STATUS
    return ready.strip(), in_review.strip()


def status_option_for_prefix(
    status_options: Dict[str, str], prefix: str
) -> Optional[Tuple[str, str]]:
    """Return (option_name, option_id) whose name starts with prefix.

    Prefers an exact match when several options share the prefix. Returns
    None when none match or when two or more non-exact names match.
    """
    if not prefix:
        return None
    matches = [
        (name, option_id)
        for name, option_id in status_options.items()
        if name == prefix or name.startswith(prefix)
    ]
    if not matches:
        return None
    exact = [item for item in matches if item[0] == prefix]
    if exact:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    return None


def parse_github_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a GitHub GraphQL DateTime (ISO-8601, often ending in Z)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def actor_login(node: Optional[Dict[str, Any]]) -> str:
    """Return the author login from a GraphQL node, or empty."""
    if not node:
        return ""
    author = node.get("author") or {}
    return (author.get("login") or "").strip()


def is_bot_actor(login: str, association: Optional[str] = None) -> bool:
    """True for GitHub bots and the ghost user."""
    if association == "BOT":
        return True
    lowered = login.lower()
    return lowered.endswith("[bot]") or lowered == "ghost"


def is_reviewer_actor(
    login: str,
    author_login: str,
    association: Optional[str] = None,
) -> bool:
    """True when login is a human other than the issue/PR author."""
    if not login or is_bot_actor(login, association):
        return False
    if author_login and login.lower() == author_login.lower():
        return False
    return True


def _activity_is_on_or_after(timestamp: Optional[str], since: datetime) -> bool:
    parsed = parse_github_datetime(timestamp)
    return parsed is not None and parsed >= since


def comment_is_reviewer_activity(
    comment: Dict[str, Any],
    author_login: str,
    since: datetime,
) -> bool:
    """True for a non-author human comment at or after the Status change."""
    if not _activity_is_on_or_after(comment.get("createdAt"), since):
        return False
    return is_reviewer_actor(
        actor_login(comment), author_login, comment.get("authorAssociation")
    )


def review_is_reviewer_activity(
    review: Dict[str, Any],
    author_login: str,
    since: datetime,
) -> bool:
    """True for a submitted non-author review at or after the Status change."""
    state = (review.get("state") or "").upper()
    if state not in COUNTABLE_REVIEW_STATES:
        return False
    if not _activity_is_on_or_after(review.get("submittedAt"), since):
        return False
    return is_reviewer_actor(
        actor_login(review), author_login, review.get("authorAssociation")
    )


def content_has_reviewer_activity(
    content: Dict[str, Any], since: datetime
) -> bool:
    """True when a non-author human commented or submitted a review after since."""
    author_login = actor_login(content)
    for comment in (content.get("comments") or {}).get("nodes") or []:
        if comment_is_reviewer_activity(comment, author_login, since):
            return True
    if content.get("__typename") == "PullRequest":
        for review in (content.get("reviews") or {}).get("nodes") or []:
            if review_is_reviewer_activity(review, author_login, since):
                return True
    return False


def item_content_label(content: Dict[str, Any]) -> str:
    """Short log label for a board issue or pull request."""
    repo = (content.get("repository") or {}).get("nameWithOwner") or "?"
    number = content.get("number")
    kind = "PR" if content.get("__typename") == "PullRequest" else "Issue"
    title = content.get("title") or ""
    return f"{kind} {repo}#{number}: {title}"


def list_board_status_items(
    client: GitHubClient, project_id: str
) -> List[Dict[str, Any]]:
    """Return board items with Status name, updatedAt, and content identity."""
    query = """
    query($projectId: ID!, $cursor: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              status: fieldValueByName(name: "Status") {
                ... on ProjectV2ItemFieldSingleSelectValue {
                  name
                  updatedAt
                }
              }
              content {
                __typename
                ... on Issue {
                  id
                  number
                  title
                  author { login }
                  repository { nameWithOwner }
                }
                ... on PullRequest {
                  id
                  number
                  title
                  author { login }
                  repository { nameWithOwner }
                }
              }
            }
          }
        }
      }
    }
    """
    return _paginate_project_item_nodes(client, project_id, query)


def _batched(values: List[str], size: int) -> List[List[str]]:
    """Split values into consecutive chunks of at most size."""
    if size < 1:
        raise ValueError(f"batch size must be >= 1, got {size}")
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_contents_review_activity(
    client: GitHubClient, content_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Return comments (and PR reviews) keyed by issue/PR node id."""
    if not content_ids:
        return {}
    query = """
    query($ids: [ID!]!, $pageSize: Int!) {
      nodes(ids: $ids) {
        __typename
        ... on Issue {
          id
          author { login }
          comments(last: $pageSize) {
            nodes {
              createdAt
              author { login }
              authorAssociation
            }
          }
        }
        ... on PullRequest {
          id
          author { login }
          comments(last: $pageSize) {
            nodes {
              createdAt
              author { login }
              authorAssociation
            }
          }
          reviews(last: $pageSize) {
            nodes {
              submittedAt
              state
              author { login }
              authorAssociation
            }
          }
        }
      }
    }
    """
    found: Dict[str, Dict[str, Any]] = {}
    for chunk in _batched(content_ids, REVIEW_ACTIVITY_BATCH_SIZE):
        data = client.graphql(
            query,
            {"ids": chunk, "pageSize": REVIEW_ACTIVITY_PAGE_SIZE},
        )
        for node in data.get("nodes") or []:
            if not node:
                continue
            node_id = node.get("id")
            if node_id:
                found[node_id] = node
    return found


def _ready_for_review_candidates(
    nodes: List[Dict[str, Any]], ready_name: str
) -> List[Tuple[str, str, Dict[str, Any], datetime]]:
    """Collect Ready for Review items with a parseable Status.updatedAt.

    Status.updatedAt is when this item's Status option last changed (not
    other project-item metadata). That is the since-boundary so comments
    from before the move into Ready for Review do not bounce the item
    into In Review.
    """
    candidates: List[Tuple[str, str, Dict[str, Any], datetime]] = []
    for node in nodes:
        status = node.get("status") or {}
        if (status.get("name") or "") != ready_name:
            continue
        since = parse_github_datetime(status.get("updatedAt"))
        if since is None:
            continue
        content = node.get("content") or {}
        content_id = content.get("id")
        item_id = node.get("id")
        if not content_id or not item_id:
            continue
        candidates.append((content_id, item_id, content, since))
    return candidates


def advance_ready_for_review(
    client: GitHubClient,
    fields: ProjectFields,
    stats: SyncStats,
    *,
    ready_prefix: str = DEFAULT_READY_FOR_REVIEW_STATUS,
    in_review_prefix: str = DEFAULT_IN_REVIEW_STATUS,
) -> None:
    """Move Ready for Review items to In Review after reviewer activity.

    Counts a non-author, non-bot issue comment or a submitted PR review at
    or after the Status field last changed. Author comments do not count, so
    an author moving their own item into Ready for Review does not bounce it
    into In Review.
    """
    if not fields.status_field_id or not fields.status_options:
        print("Status field missing on project; skipping review-status advance")
        return
    ready = status_option_for_prefix(fields.status_options, ready_prefix)
    in_review = status_option_for_prefix(fields.status_options, in_review_prefix)
    if not ready or not in_review:
        print(
            "Warning: Ready for Review / In Review Status options not found; "
            "skipping review-status advance"
        )
        return
    ready_name, _ready_id = ready
    in_review_name, in_review_id = in_review

    print(
        f"\n=== Advancing {ready_name} -> {in_review_name} "
        "on reviewer activity ==="
    )
    candidates = _ready_for_review_candidates(
        list_board_status_items(client, fields.project_id), ready_name
    )
    if not candidates:
        return
    try:
        content_ids = [content_id for content_id, _, _, _ in candidates]
        activities = fetch_contents_review_activity(client, content_ids)
    except SYNC_EXCEPTIONS as exc:
        for _content_id, _item_id, content, _since in candidates:
            stats.review_status_failed += 1
            label = item_content_label(content)
            msg = f"Failed advancing {label} to {in_review_name}: {exc}"
            print(f"  ! {msg}")
            stats.errors.append(msg)
        return

    for content_id, item_id, content, since in candidates:
        label = item_content_label(content)
        try:
            activity = activities.get(content_id) or {}
            if not content_has_reviewer_activity(activity, since):
                continue
            set_single_select(
                client,
                fields.project_id,
                item_id,
                fields.status_field_id,
                in_review_id,
            )
            stats.review_status_set += 1
            print(f"  status {label} -> {in_review_name}")
        except SYNC_EXCEPTIONS as exc:
            stats.review_status_failed += 1
            msg = f"Failed advancing {label} to {in_review_name}: {exc}"
            print(f"  ! {msg}")
            stats.errors.append(msg)


def format_summary(stats: SyncStats, dry_run: bool) -> str:
    """Format the job summary markdown (pure; no I/O)."""
    lines = [
        "## Compliance Automation project sync",
        "",
        f"- Mode: `{'dry-run' if dry_run else 'apply'}`",
        f"- Repositories considered: **{stats.repos_considered}**",
        f"- Repositories linked: **{stats.repos_linked}**"
        + (f" (skipped/already linked: {stats.repos_link_skipped})" if stats.repos_link_skipped else ""),
        f"- Open items scanned: **{stats.items_seen}**",
        f"- Already on board: **{stats.items_already_on_board}**",
        f"- Added: **{stats.items_added}**",
        f"- Failed: **{stats.items_failed}**",
        f"- Organization set/updated: **{stats.organization_set}**",
        f"- Organization failed: **{stats.organization_failed}**",
        f"- Priority copied from linked issues: **{stats.priority_set}**",
        f"- Priority copy failed: **{stats.priority_failed}**",
        f"- Priority option unmapped: **{stats.priority_unmapped}**",
        f"- Ready for Review advanced to In Review: **{stats.review_status_set}**",
        f"- Review-status advance failed: **{stats.review_status_failed}**",
    ]
    if stats.errors:
        lines.extend(["", "### Errors", ""])
        lines.extend(f"- `{err}`" for err in stats.errors[:50])
    return "\n".join(lines) + "\n"


def write_summary(stats: SyncStats, dry_run: bool) -> None:
    """Print the job summary and append it to GITHUB_STEP_SUMMARY when set."""
    summary = format_summary(stats, dry_run)
    print(summary)
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(summary)


def sync(
    config: Dict[str, Any],
    client: GitHubClient,
    org_filter: Set[str],
    backfill_org: str = "auto",
) -> SyncStats:
    stats = SyncStats()
    project_cfg = config["project"]
    sync_cfg = config.get("sync", {})
    owner = project_cfg["owner"]
    number = int(project_cfg["number"])
    default_status = project_cfg.get("default_status", "Backlog")
    include_issues = bool(sync_cfg.get("issues", True))
    include_prs = bool(sync_cfg.get("pull_requests", True))
    skip_archived = bool(sync_cfg.get("skip_archived", True))
    link_repos = bool(sync_cfg.get("link_repositories", True))

    fields = get_project(client, owner, number)
    project_id = fields.project_id
    status_field_id = fields.status_field_id
    status_options = fields.status_options
    status_option_id = status_options.get(default_status) if status_options else None
    if default_status and status_field_id and not status_option_id:
        print(
            f"Warning: Status option '{default_status}' not found; "
            "items will be added without a Status value"
        )
    if not fields.organization_field_id:
        print(
            "Warning: Organization field not found; "
            "items will be added without an Organization value"
        )

    print(f"Project {owner}/{number} id={project_id}")
    on_board = existing_content_ids(client, project_id)
    print(f"Existing board items with content: {len(on_board)}")

    for org_cfg in config.get("organizations", []):
        org = org_cfg["name"]
        if org_filter and org not in org_filter:
            continue
        exclude = set(org_cfg.get("exclude_repos") or [])
        print(f"\n=== {org} (exclude={sorted(exclude) or 'none'}) ===")
        org_mapped = organization_option_for_owner(org, fields.organization_options)
        organization_option_id = org_mapped[1] if org_mapped else None
        if fields.organization_field_id and not organization_option_id:
            print(
                f"  Warning: no Organization option mapped for '{org}'; "
                "new items will omit Organization"
            )
        try:
            repos = list_org_repos(
                client, org, exclude=exclude, skip_archived=skip_archived
            )
        except SYNC_EXCEPTIONS as exc:
            msg = f"Failed listing repos for {org}: {exc}"
            print(msg)
            stats.errors.append(msg)
            continue

        for repo in repos:
            full_name = repo["full_name"]
            stats.repos_considered += 1
            print(f"\n- {full_name}")

            if link_repos:
                # GitHub only allows linking a repository to a project owned by
                # the same org. Cross-org boards (e.g. unbound-force repos on a
                # complytime project) can still receive issues/PRs via
                # addProjectV2ItemById — skip the unsupported link step.
                if org != owner:
                    stats.repos_link_skipped += 1
                    print(
                        "  skip repo link (cross-org; items still sync onto the board)"
                    )
                else:
                    try:
                        linked = link_repository(
                            client, project_id, repo["node_id"]
                        )
                        if linked:
                            stats.repos_linked += 1
                            print("  linked to project")
                        else:
                            stats.repos_link_skipped += 1
                            print("  already linked (or skipped)")
                    except SYNC_EXCEPTIONS as exc:
                        # Linking is best-effort for same-org repos (permissions
                        # may be missing). Do not fail the job: item sync is the
                        # primary goal.
                        stats.repos_link_skipped += 1
                        print(f"  skip repo link for {full_name} ({exc})")

            try:
                open_items = list_open_items(
                    client,
                    full_name,
                    include_issues=include_issues,
                    include_prs=include_prs,
                )
            except SYNC_EXCEPTIONS as exc:
                msg = f"Failed listing items for {full_name}: {exc}"
                print(f"  {msg}")
                stats.errors.append(msg)
                continue

            for item in open_items:
                stats.items_seen += 1
                node_id = item["node_id"]
                title = item.get("title", "")
                number_ = item.get("number")
                kind = "PR" if "pull_request" in item else "Issue"
                label = f"{kind} #{number_}: {title}"

                if node_id in on_board:
                    stats.items_already_on_board += 1
                    continue

                try:
                    result = add_item(
                        client,
                        project_id,
                        node_id,
                        status_field_id,
                        status_option_id,
                        fields.organization_field_id,
                        organization_option_id,
                    )
                    stats.items_added += 1
                    on_board.add(node_id)
                    print(f"  + {label}")
                    if result.organization_set:
                        stats.organization_set += 1
                    if result.organization_error:
                        stats.organization_failed += 1
                        msg = (
                            f"Failed setting Organization on {full_name} "
                            f"{label}: {result.organization_error}"
                        )
                        print(f"  ! {msg}")
                        stats.errors.append(msg)
                except SYNC_EXCEPTIONS as exc:
                    stats.items_failed += 1
                    msg = f"Failed adding {full_name} {label}: {exc}"
                    print(f"  ! {msg}")
                    stats.errors.append(msg)

    if should_run_organization_backfill(backfill_org, stats):
        ensure_organizations(client, fields, stats)
    else:
        reason = (
            "--backfill-org never"
            if backfill_org == "never"
            else "newly added items already have Organization"
        )
        print(f"\nSkipping Organization backfill ({reason})")
    ensure_pr_priority_from_issues(client, fields, stats)
    ready_prefix, in_review_prefix = review_status_prefixes(config)
    advance_ready_for_review(
        client,
        fields,
        stats,
        ready_prefix=ready_prefix,
        in_review_prefix=in_review_prefix,
    )
    return stats


def main() -> int:
    args = parse_args()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("PROJECT_SYNC_TOKEN")
    if not token:
        print("GITHUB_TOKEN or PROJECT_SYNC_TOKEN is required", file=sys.stderr)
        return 2

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        config = validate_config(load_config(config_path))
    except ValueError as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2
    org_filter = {part for part in args.orgs.split() if part}
    client = GitHubClient(
        token=token,
        dry_run=args.dry_run,
        user_agent="complytime-project-board-sync",
    )
    stats = sync(config, client, org_filter, backfill_org=args.backfill_org)
    write_summary(stats, dry_run=args.dry_run)
    return 1 if stats.items_failed or stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
