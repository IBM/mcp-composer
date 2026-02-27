"""SRE tool for GitHub operations including file updates and PR creation."""

import base64
import os
from datetime import date
from typing import TypedDict

from mcp_composer.core.tools.nvd_tool import enrich_issues_csv_with_cvss

from github import Auth, Github, GithubException


class PRResult(TypedDict):
    """Result of PR creation operation."""

    status: str
    pr_number: int | None
    pr_url: str | None
    message: str | None


def _get_github_client(base_url: str | None = None) -> Github:
    """
    Create a GitHub client using token and base URL from environment variables.

    Args:
        base_url: Optional GitHub base URL. If not provided, uses GITHUB_BASE_URL env var.

    Returns:
        Configured Github client instance.

    Raises:
        ValueError: If GITHUB_TOKEN environment variable is not set.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    base_url = base_url or os.getenv("GITHUB_BASE_URL")
    auth = Auth.Token(token)

    return Github(base_url=base_url, auth=auth) if base_url else Github(auth=auth)


def _dated_csv_path(file_path: str, date_str: str) -> str:
    """Insert date into CSV filename before extension."""
    if not file_path.lower().endswith(".csv"):
        return file_path
    base, ext = file_path.rsplit(".", 1)
    return f"{base}_{date_str}.{ext}"


async def composite_update_file_and_pr(
    repo_name: str,
    file_path: str,
    branch_name: str,
    pr_title: str,
    base_url: str | None = None,
):
    """
    Execute a composite workflow to update a CSV file and create a pull request.

    This function performs the following steps:
    1. Validates the file is a CSV
    2. Retrieves current file content from the repository
    3. Enriches CSV with CVSS scores and sorts by severity
    4. Creates a dated output file name (e.g., issues_YYYY-MM-DD.csv)
    5. Creates a new branch (or uses existing)
    6. Commits the updated file to the branch
    7. Creates a pull request for review

    Args:
        repo_name: Full repository name (e.g., 'owner/repo').
        file_path: Path to the CSV file in the repository.
        branch_name: Name for the new branch to create.
        pr_title: Title for the pull request.
        base_url: Optional GitHub base URL for enterprise instances.

    Returns:
        Dictionary containing operation status, PR number, URL, and any error messages.

    Example:
        >>> result = composite_update_file_and_pr(
        ...     repo_name="myorg/myrepo",
        ...     file_path="data/records.csv",
        ...     branch_name="update-records",
        ...     pr_title="Enrich records with CVSS"
        ... )
        >>> print(result["status"])
        'success'
    """
    try:
        # Validate file type early
        if not file_path.lower().endswith(".csv"):
            return PRResult(
                status="error",
                pr_number=None,
                pr_url=None,
                message="Target file must be a CSV file.",
            )

        client = _get_github_client(base_url=base_url)
        repo = client.get_repo(repo_name)
        base_branch = repo.default_branch

        # Step 1: Get current file content and SHA
        contents = repo.get_contents(file_path, ref=branch_name)

        if isinstance(contents, list):
            return PRResult(
                status="error",
                pr_number=None,
                pr_url=None,
                message=f"Path '{file_path}' is a directory, not a file.",
            )

        try:
            # Try the standard way first
            current_text = contents.decoded_content.decode("utf-8")
        except AssertionError:
            # 3. If it fails, fetch the raw blob using the SHA
            print("Detected 'none' encoding. Fetching via Git Blob API...")
            blob = repo.get_git_blob(contents.sha)
            # The blob.content is always base64 encoded by the API
            current_text = base64.b64decode(blob.content).decode("utf-8")

        # Enrich CSV with CVSS scores and sort by severity
        updated_text = await enrich_issues_csv_with_cvss(current_text)
        print("updated_text:", updated_text)

        # # Create dated output file path
        # dated_file_path = _dated_csv_path(file_path, date.today().isoformat())

        # # Step 2: Create new branch from base branch
        # base_branch_obj = repo.get_branch(base_branch)
        # try:
        #     repo.create_git_ref(
        #         ref=f"refs/heads/{branch_name}", sha=base_branch_obj.commit.sha
        #     )
        # except GithubException as e:
        #     # Branch already exists - continue with existing branch
        #     if "Reference already exists" not in str(e):
        #         raise

        # # Step 5: Commit updated file to branch
        # try:
        #     target_contents = repo.get_contents(dated_file_path, ref=branch_name)
        #     repo.update_file(
        #         path=dated_file_path,
        #         message=f"Update {dated_file_path} with CVSS scores",
        #         content=updated_text,
        #         sha=target_contents.sha,
        #         branch=branch_name,
        #     )
        # except GithubException as e:
        #     if "404" not in str(e):
        #         raise
        #     repo.create_file(
        #         path=dated_file_path,
        #         message=f"Create {dated_file_path} with CVSS scores",
        #         content=updated_text,
        #         branch=branch_name,
        #     )

        # # Step 6: Create pull request
        # pr = repo.create_pull(
        #     title=pr_title,
        #     body="Automated PR created via MCP Composer",
        #     head=branch_name,
        #     base=base_branch,
        # )

        # return PRResult(
        #     status="success",
        #     pr_number=pr.number,
        #     pr_url=pr.html_url,
        #     message=None,
        # )

    except GithubException as e:
        error_message = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)
        return PRResult(
            status="error",
            pr_number=None,
            pr_url=None,
            message=error_message,
        )
    except Exception as e:
        return PRResult(
            status="error",
            pr_number=None,
            pr_url=None,
            message=f"Unexpected error: {str(e)}",
        )
