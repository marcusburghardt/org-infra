#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""
Script to synchronize standard files and workflows across all repositories
defined in peribolos.yml from the .github repository.

This script uses a fork-based workflow with GitHub App authentication:
1. Forks the target repository (if not already forked)
2. Clones the fork
3. Makes changes and pushes to fork
4. Creates PR from fork to upstream repository

This approach only requires read access to target repositories.
"""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import yaml
import requests

from datetime import datetime
from git import GitCommandError
from git.repo import Repo
from pathlib import Path
from typing import Optional, Dict, Tuple


GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', os.getenv('GITHUB_PAT'))
DEFAULT_CONFIG_FILE = 'sync-config.yml'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync repository standards across organization repositories"
    )
    parser.add_argument(
        "--org",
        required=True,
        help="GitHub organization name",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to sync configuration file (default: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        help="Specific repositories to sync (default: all from peribolos.yml)",
    )
    args = parser.parse_args()
    return args


def load_sync_config(config_path: str) -> dict:
    """Load the sync configuration file."""
    script_dir = Path(__file__).parent.parent
    full_path = f'{script_dir}/{config_path}'
    with open(full_path, 'r') as f:
        return yaml.safe_load(f)


def validate_github_api_request(endpoint: str, method: str) -> bool:
    """Validate a GitHub API request."""
    allowed_patterns = [
        (r"^" + GITHUB_API + "/app$", "GET"),
        (r"^" + GITHUB_API + "/user$", "GET"),
        (r"^" + GITHUB_API + "/repos/[^/]+/[^/]+$", "GET"),
        (r"^" + GITHUB_API + "/repos/[^/]+/[^/]+/forks$", "POST"),
        (r"^" + GITHUB_API + "/repos/[^/]+/[^/]+/pulls$", "POST"),
        (r"^" + GITHUB_API + "/repos/[^/]+/[^/]+/git/refs/heads/.+$", "DELETE"),
    ]
    return any(re.match(pattern, endpoint) and method == allowed_method for pattern, allowed_method in allowed_patterns)


def github_api_request(endpoint: str, method: str = "POST", data: Optional[dict] = None) -> Tuple[int, Dict]:
    """
    Make a GitHub API request using requests library.

    Args:
        endpoint: API endpoint (e.g., "/user", "/repos/org/repo/forks")
        method: HTTP method (POST, DELETE, PATCH, etc.)
        data: Optional JSON data to send

    Returns:
        Tuple of (status_code, response_data)
    """
    # Guardrail: only allow specific endpoint patterns and methods
    if not validate_github_api_request(endpoint, method):
        print(f"Error: Endpoint {endpoint} with method {method} is not allowed")
        return 403, {"error": "Endpoint not allowed"}

    url = f"{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            timeout=30
        )
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw": response.text}
        return response.status_code, response_data
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return 500, {"error": str(e)}


def get_authenticated_actor() -> Optional[str]:
    """Identify the actor behind the current GitHub token (user or app)."""
    user_url = f"{GITHUB_API}/user"
    status, data = github_api_request(user_url, method="GET")
    if status == 200:
        return data.get("login")

    # If it's a GitHub App token, /user returns 403
    if status == 403 and "Resource not accessible by integration" in data.get("message", ""):
        app_url = f"{GITHUB_API}/app"
        app_status, app_data = github_api_request(app_url, method="GET")
        if app_status == 200:
            app_slug = app_data.get("slug")
            return f"GitHub App: {app_slug}"

        print(f"Failed to identify GitHub App (HTTP {app_status}): {app_data}")
        return None

    print(f"Failed to get authenticated user (HTTP {status}): {data}")
    return None


def check_fork_exists(org: str, repo_name: str, fork_owner: str) -> bool:
    """Check if a fork already exists."""
    url = f"{GITHUB_API}/repos/{fork_owner}/{repo_name}"
    status, _ = github_api_request(url, method="GET")
    if status == 200:
        return True


def create_fork(org: str, repo_name: str) -> bool:
    """
    Create a fork of the repository.

    Returns:
        True if fork was created or already exists, False on error.
    """
    print(f"Creating fork of {org}/{repo_name}...")
    url = f"{GITHUB_API}/repos/{org}/{repo_name}/forks"
    status, data = github_api_request(url, method="POST", data={})

    if status == 202:
        print("Fork created successfully, waiting for it to be ready...")
        # Wait for fork to be ready (GitHub takes a moment to set it up)
        time.sleep(5)
        return True
    elif status == 200:
        print("Fork already exists")
        return True
    else:
        print(f"Failed to create fork (HTTP {status}): {data}")
        return False


def delete_fork_branch(fork_owner: str, repo_name: str, branch_name: str) -> bool:
    """Delete a branch from the fork (cleanup old sync branches)."""
    status, _ = github_api_request(f"/repos/{fork_owner}/{repo_name}/git/refs/heads/{branch_name}", method="DELETE")
    return status == 204


def fetch_peribolos_file(org: str) -> dict:
    """
    Fetch peribolos.yaml from the organization's .github repository.
    """
    peribolos_repo = ".github"
    github_repo_url = f"https://github.com/{org}/{peribolos_repo}.git"
    print(f"Fetching peribolos configuration from {github_repo_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            cmd = f"git clone --quiet --depth 1 {github_repo_url}"
            subprocess.check_call(cmd, cwd=tmpdir, shell=True)

            repo_path = os.path.join(tmpdir, peribolos_repo)
            peribolos_path = os.path.join(repo_path, 'peribolos.yaml')
            if os.path.exists(peribolos_path):
                with open(peribolos_path, 'r') as f:
                    return yaml.safe_load(f)
            print(f"Error: peribolos.yaml not found in {peribolos_repo} repository")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {peribolos_repo} repository: {e}")
            sys.exit(1)


def extract_repositories(peribolos_data: dict, org: str) -> list:
    """
    Extract list of repositories from peribolos data.
    """
    repos = []

    if 'orgs' in peribolos_data and org in peribolos_data['orgs']:
        org_data = peribolos_data['orgs'][org]
        if 'repos' in org_data:
            repos = list(org_data['repos'].keys())

    print(f"Found {len(repos)} repositories in peribolos configuration for {org}")
    return repos


def compare_files(source_file: str, dest_file: str) -> bool:
    """
    Compare two files and return True if they are identical.
    """
    if not os.path.exists(dest_file):
        return False
    return filecmp.cmp(source_file, dest_file, shallow=False)


def sync_file(source_path: str, dest_path: str, relative_path: str) -> bool:
    """
    Sync a file from source to destination.
    Returns True if file was copied/updated, False if identical.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if os.path.exists(dest_path):
        if compare_files(source_path, dest_path):
            print(f"{relative_path} is up to date")
            return False
        else:
            print(f"{relative_path} needs update")
    else:
        print(f"{relative_path} is missing")

    shutil.copy2(source_path, dest_path)
    return True


def setup_git_credentials(repo_path: str, fork_owner: str, repo_name: str) -> None:
    """Configure git credentials for authenticated pushes."""
    repo = Repo(repo_path)

    fork_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{fork_owner}/{repo_name}.git"
    try:
        repo.remote('origin').set_url(fork_url)
    except Exception:
        repo.create_remote('origin', fork_url)


def create_branch_and_commit(repo_path: str, branch_name: str, files_changed: list, commit_message: str) -> bool:
    """
    Create a new branch, commit changes, and push to origin (fork).
    """
    repo = Repo(repo_path)

    try:
        # Create and checkout new branch
        repo.git.checkout("-b", branch_name)

        # Add all changed files to staging area
        for file_path in files_changed:
            repo.git.add(file_path)

        # Commit changes
        repo.index.commit(commit_message)

        # Push to origin (which is the fork)
        repo.git.push('--set-upstream', 'origin', branch_name)
        print(f"Pushed branch: {branch_name}")
        return True
    except GitCommandError as e:
        print(f"Git operation failed: {e}")
        return False


def create_pull_request(org: str, repo_name: str, fork_owner: str, branch_name: str, 
                       title: str, body: str, base_branch: str = "main") -> bool:
    """
    Create a pull request from fork to upstream repository using GitHub API.

    Args:
        org: Upstream organization name
        repo_name: Repository name
        fork_owner: Owner of the fork (GitHub App or user)
        branch_name: Branch name in the fork
        title: PR title
        body: PR body/description
        base_branch: Target branch in upstream repo (default: main)
    """
    data = {
        "title": title,
        "body": body,
        "base": base_branch,
        "head": f"{fork_owner}:{branch_name}"
    }

    status, response_data = github_api_request(f"{GITHUB_API}/repos/{org}/{repo_name}/pulls", method="POST", data=data)

    if status == 201:
        pr_url = response_data.get('html_url', '')
        print(f"Pull request created successfully: {pr_url}")
        return True
    else:
        error_msg = response_data.get('message', 'Unknown error')
        print(f"Failed to create PR (HTTP {status}): {error_msg}")
        return False


def sync_repository(org: str, repo_name: str, fork_owner: str, config: dict, dry_run: bool = False) -> bool:
    """
    Sync a single repository with standard files using fork-based workflow.

    Args:
        org: Upstream organization name
        repo_name: Repository name
        fork_owner: GitHub username/app that owns the fork
        config: Sync configuration
        dry_run: If True, only show what would be done
    """
    print(f"\n{'='*60}")
    print(f"Processing: {org}/{repo_name}")
    print(f"{'='*60}")

    source_root = Path(__file__).parent.parent
    files_to_sync = config.get('files_to_sync', [])
    if not files_to_sync:
        print("No files configured for sync")
        return False

    # Step 1: Ensure fork exists in order to prepare the PR without write access to the target repository
    if not dry_run:
        if not check_fork_exists(org, repo_name, fork_owner):
            if not create_fork(org, repo_name):
                print(f"Failed to create fork, skipping {repo_name}")
                return False
        else:
            print(f"Fork {fork_owner}/{repo_name} already exists")

    # Step 2: Clone the fork
    fork_url = f"https://github.com/{fork_owner}/{repo_name}.git"
    upstream_url = f"https://github.com/{org}/{repo_name}.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if dry_run:
                print(f"[DRY RUN] Would clone fork: {fork_url}")
                # For dry run, clone upstream to check files
                clone_url = upstream_url
            else:
                clone_url = fork_url

            print(f"Cloning {clone_url}...")
            cmd = ['git', 'clone', '--quiet', clone_url]
            subprocess.check_call(cmd, cwd=tmpdir, stderr=subprocess.DEVNULL)
            repo_path = os.path.join(tmpdir, repo_name)

            # Configure git if not dry run
            if not dry_run:
                setup_git_credentials(repo_path, fork_owner, repo_name)

                # Add upstream remote
                repo = Repo(repo_path)
                try:
                    repo.create_remote('upstream', upstream_url)
                    print("Added upstream remote")
                except Exception:
                    pass  # Remote might already exist

                # Fetch latest from upstream
                try:
                    repo.git.fetch('upstream')
                    repo.git.checkout('main')
                    repo.git.reset('--hard', 'upstream/main')
                    print("Synced fork with upstream")
                except GitCommandError as e:
                    print(f"Warning: Could not sync with upstream: {e}")

            # Step 3: Process files to sync
            files_changed = []
            for file_config in files_to_sync:
                source_rel_path = file_config['source']
                dest_rel_path = file_config.get('destination', source_rel_path)

                source_path = source_root / source_rel_path
                dest_path = os.path.join(repo_path, dest_rel_path)

                if not source_path.exists():
                    print(f"Source file not found: {source_rel_path}")
                    continue

                if 'exclude_repos' in file_config:
                    if repo_name in file_config['exclude_repos']:
                        print(f"{source_rel_path} excluded for this repo")
                        continue

                if dry_run:
                    if not os.path.exists(dest_path):
                        print(f"[DRY RUN] Would add: {dest_rel_path}")
                        files_changed.append(dest_rel_path)
                    elif not compare_files(source_path, dest_path):
                        print(f"[DRY RUN] Would update: {dest_rel_path}")
                        files_changed.append(dest_rel_path)
                    else:
                        print(f"{dest_rel_path} is up to date")
                else:
                    if sync_file(source_path, dest_path, dest_rel_path):
                        files_changed.append(dest_rel_path)

            if not files_changed:
                print(f"All files up to date for {repo_name}")
                return True

            if dry_run:
                print(f"[DRY RUN] Would create PR with {len(files_changed)} file(s)")
                return True

            # Step 4: Create branch, commit, and push to fork
            branch_name = f"sync-repo-standards-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            commit_message = "chore: sync repository standards\n\nUpdated files:\n" + \
                           "\n".join(f"- {f}" for f in files_changed)

            print("\nCreating branch and committing changes...")
            if not create_branch_and_commit(repo_path, branch_name, files_changed, commit_message):
                return False

            # Step 5: Create pull request from fork to upstream
            pr_title = "chore: sync repository standards"
            pr_body = f"""This PR synchronizes repository standards from org-infra.

## Files Updated
{chr(10).join(f"- `{f}`" for f in files_changed)}

## Description
This is an automated PR to ensure repository settings are consistent across the organization.

---
*This PR was automatically generated by the sync_org_repositories workflow.*
"""

            print("Creating pull request from fork to upstream...")
            return create_pull_request(org, repo_name, fork_owner, branch_name, pr_title, pr_body)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {repo_name}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error processing {repo_name}: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    args = parse_args()

    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN or GITHUB_PAT environment variable not set")
        sys.exit(1)

    # Get the authenticated user/app name
    fork_owner = get_authenticated_actor()
    if not fork_owner:
        print("Error: Could not determine authenticated user/app")
        sys.exit(1)

    print(f"Authenticated as: {fork_owner}")
    config = load_sync_config(args.config)

    # Fetch and parse peribolos.yml
    peribolos_data = fetch_peribolos_file(args.org)
    repositories = extract_repositories(peribolos_data, args.org)

    if not repositories:
        print("No repositories found in peribolos configuration")
        sys.exit(0)

    if args.repos:
        repositories = [r for r in repositories if r in args.repos]
        print(f"Filtering to {len(repositories)} specified repository(ies)")

    # Skip org-infra itself and other excluded repos
    excluded_repos = config.get('exclude_repos', ['org-infra'])
    repositories = [r for r in repositories if r not in excluded_repos]

    if args.dry_run:
        print("\n" + "="*60)
        print("DRY RUN MODE - No changes will be made")
        print("="*60)

    print(f"{len(excluded_repos)} repositories were excluded in this sync:\n- {'\n- '.join(excluded_repos)}")
    print(f"\nWill process {len(repositories)} repository(ies)")

    success_count = 0
    for repo_name in repositories:
        try:
            if sync_repository(args.org, repo_name, fork_owner, config, args.dry_run):
                success_count += 1
        except Exception as e:
            print(f"Failed to process {repo_name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Summary: Successfully processed {success_count}/{len(repositories)} repositories")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
