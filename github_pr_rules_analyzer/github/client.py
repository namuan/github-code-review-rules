"""GitHub API client for collecting pull request data."""

import time
from typing import Any
from urllib.parse import urljoin

import requests

from github_pr_rules_analyzer.config import get_settings
from github_pr_rules_analyzer.utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GitHubAPIClient:
    """GitHub API client with rate limiting and error handling."""

    def __init__(self, access_token: str | None = None) -> None:
        """Initialize GitHub API client.

        Args:
        ----
            access_token: GitHub personal access token for authentication

        """
        self.access_token = access_token or settings.github_token
        self.base_url = "https://api.github.com"
        self.session = requests.Session()

        # Set up authentication
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-PR-Rules-Analyzer/1.0",
            })
        else:
            logger.warning("No GitHub token provided, using unauthenticated requests")

        # Rate limiting
        self.rate_limit_remaining = 5000  # Default for unauthenticated
        self.rate_limit_reset = None
        self.last_request_time = 0

        # Request delay to avoid hitting rate limits
        self.request_delay = 0.1  # 100ms between requests

    def _check_rate_limit(self) -> None:
        """Check rate limit status and wait if necessary."""
        if self.rate_limit_remaining is not None and self.rate_limit_remaining <= 0:
            if self.rate_limit_reset:
                wait_time = self.rate_limit_reset - time.time()
                if wait_time > 0:
                    logger.info("Rate limit exceeded, waiting %.1f seconds", wait_time)
                    time.sleep(wait_time + 1)  # Add 1 second buffer
            else:
                # Default wait if reset time not available
                logger.info("Rate limit exceeded, waiting 60 seconds")
                time.sleep(60)

        # Enforce minimum delay between requests
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.request_delay:
            time.sleep(self.request_delay - time_since_last_request)

        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:  # noqa: ANN401
        """Make HTTP request with rate limiting and error handling.

        Args:
        ----
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
        -------
            requests.Response: Response object

        Raises:
        ------
            requests.RequestException: If request fails

        """
        self._check_rate_limit()

        # Ensure URL is complete
        if not url.startswith(("http://", "https://")):
            url = urljoin(self.base_url, url.lstrip("/"))

        logger.debug("Making %s request to %s", method, url)

        try:
            response = self.session.request(method, url, **kwargs)

            # Update rate limit info
            if "X-RateLimit-Remaining" in response.headers:
                self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])

            if "X-RateLimit-Reset" in response.headers:
                self.rate_limit_reset = int(response.headers["X-RateLimit-Reset"])

            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                logger.warning("Rate limit exceeded")
                self._check_rate_limit()
                response = self.session.request(method, url, **kwargs)

            # Handle other errors
            response.raise_for_status()

            return response

        except requests.RequestException:
            logger.exception("Request failed")
            raise

    def _get_paginated_results(self, url: str, params: dict | None = None) -> list[dict]:
        """Get all results from paginated endpoint.

        Args:
        ----
            url: API endpoint URL
            params: Query parameters

        Returns:
        -------
            List of all results

        """
        all_results = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub

        while True:
            request_params = params.copy() if params else {}
            request_params.update({
                "page": page,
                "per_page": per_page,
            })

            response = self._make_request("GET", url, params=request_params)
            results = response.json()

            if not results:
                break

            all_results.extend(results)

            # Check if we got fewer results than requested (last page)
            if len(results) < per_page:
                break

            page += 1

        return all_results

    def get_user_repositories(self, visibility: str = "all") -> list[dict]:
        """Get repositories for the authenticated user.

        Args:
        ----
            visibility: Repository visibility ('all', 'public', 'private')

        Returns:
        -------
            List of repository dictionaries

        """
        url = "/user/repos"
        params = {"visibility": visibility}

        return self._get_paginated_results(url, params)

    def get_organization_repositories(self, organization: str) -> list[dict]:
        """Get repositories for an organization.

        Args:
        ----
            organization: Organization name

        Returns:
        -------
            List of repository dictionaries

        """
        url = f"/orgs/{organization}/repos"

        return self._get_paginated_results(url)

    def get_repository(self, owner: str, repo: str) -> dict:
        """Get repository information.

        Args:
        ----
            owner: Repository owner
            repo: Repository name

        Returns:
        -------
            Repository dictionary

        """
        url = f"/repos/{owner}/{repo}"

        response = self._make_request("GET", url)
        return response.json()

    def get_pull_requests(self, owner: str, repo: str, state: str = "closed", per_page: int = 100) -> list[dict]:
        """Get pull requests for a repository.

        Args:
        ----
            owner: Repository owner
            repo: Repository name
            state: PR state ('open', 'closed', 'all')
            per_page: Number of results per page

        Returns:
        -------
            List of pull request dictionaries

        """
        url = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": per_page}

        return self._get_paginated_results(url, params)

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Get files changed in a pull request.

        Args:
        ----
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
        -------
            List of file dictionaries

        """
        url = f"/repos/{owner}/{repo}/pulls/{pr_number}/files"

        response = self._make_request("GET", url)
        return response.json()

    def get_pull_request_comments(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Get review comments for a pull request.

        Args:
        ----
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
        -------
            List of review comment dictionaries

        """
        url = f"/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        return self._get_paginated_results(url)

    def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> list[dict]:
        """Get issue comments for a pull request (treated as issue).

        Args:
        ----
            owner: Repository owner
            repo: Repository name
            issue_number: Issue/PR number

        Returns:
        -------
            List of issue comment dictionaries

        """
        url = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"

        return self._get_paginated_results(url)

    def get_all_comments(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Get all comments (review comments + issue comments) for a pull request.

        Args:
        ----
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
        -------
            List of all comment dictionaries

        """
        # Get review comments
        review_comments = self.get_pull_request_comments(owner, repo, pr_number)

        # Get issue comments
        issue_comments = self.get_issue_comments(owner, repo, pr_number)

        # Combine and return
        return review_comments + issue_comments

    def get_repository_info(self, owner: str, repo: str) -> dict:
        """Get comprehensive repository information.

        Args:
        ----
            owner: Repository owner
            repo: Repository name

        Returns:
        -------
            Repository information dictionary

        """
        try:
            repo_info = self.get_repository(owner, repo)

            # Get basic stats
            stats = {
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "watchers": repo_info.get("watchers_count", 0),
                "open_issues": repo_info.get("open_issues_count", 0),
                "language": repo_info.get("language"),
                "size": repo_info.get("size", 0),
                "has_wiki": repo_info.get("has_wiki", False),
                "has_pages": repo_info.get("has_pages", False),
                "has_issues": repo_info.get("has_issues", False),
                "has_projects": repo_info.get("has_projects", False),
                "archived": repo_info.get("archived", False),
                "disabled": repo_info.get("disabled", False),
            }

            return {
                "info": repo_info,
                "stats": stats,
            }

        except Exception:
            logger.exception("Error getting repository info for %s/%s", owner, repo)
            raise

    def validate_repository_access(self, owner: str, repo: str) -> bool:
        """Validate access to a repository.

        Args:
        ----
            owner: Repository owner
            repo: Repository name

        Returns:
        -------
            True if access is valid, False otherwise

        """
        try:
            self.get_repository(owner, repo)
            return True
        except Exception:
            logger.exception("Repository access validation failed for %s/%s", owner, repo)
            return False

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status.

        Returns
        -------
            Rate limit status dictionary

        """
        url = "/rate_limit"

        response = self._make_request("GET", url)
        return response.json()

    def test_connection(self) -> bool:
        """Test connection to GitHub API.

        Returns
        -------
            True if connection is successful, False otherwise

        """
        try:
            response = self._make_request("GET", "/user")
            return response.status_code == 200
        except Exception:
            logger.exception("Connection test failed")
            return False
