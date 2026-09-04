#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: T201
# This is a CLI script whose stdout/stderr is its user-facing interface;
# print() is intentional.

"""
Sync compliance scan targets in complytime.yaml with the repository
inventory from peribolos.yaml.

Compares the repository list in peribolos.yaml (from the org's .github
repository) against the scan targets in complytime.yaml, and generates
an updated file when drift is detected.

Exit codes:
    0 - No drift detected; targets are in sync.
    1 - Error (missing file, parse failure, invalid data).
    2 - Drift detected; updated file written to --output.
"""

import argparse
import re
import sys
from typing import Any, Dict, Set, Tuple

import yaml

# Valid repository name pattern (GitHub convention).
REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

# Prefix used for target IDs.
TARGET_ID_PREFIX = "complytime-"

# Default organization name.
DEFAULT_ORG = "complytime"

# GitHub base URL for constructing target URLs.
GITHUB_BASE_URL = "https://github.com"

# Spec value applied to all targets.
TARGET_SPECS = "builtin:github/branch-rules.yaml"

# Exit codes.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DRIFT = 2


def extract_peribolos_repos(
    peribolos_data: Dict[str, Any],
    org: str,
) -> Set[str]:
    """Extract valid repository names from peribolos data.

    Args:
        peribolos_data: Parsed peribolos.yaml content.
        org: Organization name to look up.

    Returns:
        Set of valid repository names.

    Raises:
        SystemExit: If the org key is not found in peribolos data.
    """
    orgs = peribolos_data.get("orgs", {})
    if org not in orgs:
        print(
            f"Error: organization '{org}' not found in peribolos data",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERROR)

    repos = orgs[org].get("repos", {})
    if repos is None:
        return set()

    valid_repos: Set[str] = set()
    for name in repos:
        if not REPO_NAME_PATTERN.match(name):
            print(
                f"Warning: skipping invalid repo name '{name}'",
                file=sys.stderr,
            )
            continue
        valid_repos.add(name)

    return valid_repos


def extract_complytime_repos(
    complytime_data: Dict[str, Any],
) -> Set[str]:
    """Extract repository names from complytime.yaml targets.

    Parses the URL field of each target to extract the repo name
    (last path component of the GitHub URL).

    Args:
        complytime_data: Parsed complytime.yaml content.

    Returns:
        Set of repository names found in targets.
    """
    targets = complytime_data.get("targets", [])
    if not targets:
        return set()

    repos: Set[str] = set()
    for target in targets:
        url = target.get("variables", {}).get("url", "")
        if url:
            repo_name = url.rstrip("/").rsplit("/", 1)[-1]
            if repo_name:
                repos.add(repo_name)

    return repos


def compute_drift(
    peribolos_repos: Set[str],
    complytime_repos: Set[str],
) -> Tuple[Set[str], Set[str]]:
    """Compute drift between peribolos and complytime target lists.

    Args:
        peribolos_repos: Repos from peribolos.yaml.
        complytime_repos: Repos from complytime.yaml targets.

    Returns:
        Tuple of (added repos, removed repos).
    """
    added = peribolos_repos - complytime_repos
    removed = complytime_repos - peribolos_repos
    return added, removed


def make_target_id(repo_name: str) -> str:
    """Generate a target ID from a repository name.

    If the repo name already starts with 'complytime-', use it as-is
    to avoid double-prefixing. Otherwise, prefix with 'complytime-'.

    Args:
        repo_name: GitHub repository name.

    Returns:
        Target ID string.
    """
    if repo_name.startswith(TARGET_ID_PREFIX):
        return repo_name
    return f"{TARGET_ID_PREFIX}{repo_name}"


def generate_complytime(
    complytime_data: Dict[str, Any],
    peribolos_repos: Set[str],
    org: str,
) -> Dict[str, Any]:
    """Generate updated complytime.yaml data with targets from peribolos.

    Preserves the policies and complypacks sections from the original
    data. Generates a new targets list from the peribolos repo set,
    sorted alphabetically by target ID.

    Args:
        complytime_data: Original complytime.yaml content.
        peribolos_repos: Set of repo names from peribolos.
        org: Organization name for URL generation.

    Returns:
        Updated complytime data dict.
    """
    policies = complytime_data.get("policies") or []
    policy_ids = [p["id"] for p in policies if "id" in p]

    targets = []
    for repo_name in sorted(peribolos_repos, key=make_target_id):
        target = {
            "id": make_target_id(repo_name),
            "policies": list(policy_ids),
            "variables": {
                "url": f"{GITHUB_BASE_URL}/{org}/{repo_name}",
                "specs": TARGET_SPECS,
            },
        }
        targets.append(target)

    return {
        "policies": complytime_data.get("policies") or [],
        "complypacks": complytime_data.get("complypacks") or [],
        "targets": targets,
    }


def load_yaml_file(path: str, description: str) -> Dict[str, Any]:
    """Load and parse a YAML file with error handling.

    Args:
        path: File path to read.
        description: Human-readable name for error messages.

    Returns:
        Parsed YAML content as a dict.

    Raises:
        SystemExit: If the file is missing or contains invalid YAML.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(
            f"Error: {description} not found: {path}",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERROR)
    except yaml.YAMLError as exc:
        print(
            f"Error: failed to parse {description}: {exc}",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERROR)

    if not isinstance(data, dict):
        print(
            f"Error: {description} is not a valid YAML mapping: {path}",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERROR)

    return data


def main() -> int:
    """Entry point for the sync-compliance-targets script."""
    parser = argparse.ArgumentParser(
        description=(
            "Sync compliance targets with peribolos repository inventory."
        ),
    )
    parser.add_argument(
        "--peribolos",
        required=True,
        help="Path to peribolos.yaml file",
    )
    parser.add_argument(
        "--complytime",
        required=True,
        help="Path to complytime.yaml file",
    )
    parser.add_argument(
        "--org",
        default=DEFAULT_ORG,
        help=f"Organization name in peribolos (default: {DEFAULT_ORG})",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for updated complytime.yaml",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help=(
            "Comma-separated list of repo names to exclude "
            "(e.g., '.github,complyscribe')"
        ),
    )
    args = parser.parse_args()

    peribolos_data = load_yaml_file(args.peribolos, "peribolos file")
    complytime_data = load_yaml_file(args.complytime, "complytime config")

    excluded: Set[str] = set()
    if args.exclude:
        excluded = {
            name.strip() for name in args.exclude.split(",") if name.strip()
        }

    peribolos_repos = extract_peribolos_repos(peribolos_data, args.org)
    peribolos_repos -= excluded
    complytime_repos = extract_complytime_repos(complytime_data)
    complytime_repos -= excluded

    added, removed = compute_drift(peribolos_repos, complytime_repos)

    if not added and not removed:
        print("No drift detected — targets are in sync.")
        return EXIT_OK

    if added:
        print(f"Added repositories: {', '.join(sorted(added))}")
    if removed:
        print(f"Removed repositories: {', '.join(sorted(removed))}")

    updated = generate_complytime(
        complytime_data, peribolos_repos, args.org,
    )

    try:
        with open(args.output, "w") as f:
            yaml.dump(
                updated, f, default_flow_style=False, sort_keys=False,
            )
    except OSError as exc:
        print(
            f"Error: failed to write output file: {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    print(f"Updated config written to {args.output}")
    return EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
