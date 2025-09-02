"""Unit tests for GitHub API client."""

import pytest
import responses

from github_pr_rules_analyzer.github.client import GitHubAPIClient


class TestGitHubAPIClient:
    """Test GitHub API client."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = GitHubAPIClient("test_token")

    @responses.activate
    def test_get_user_repositories(self) -> None:
        """Test getting user repositories."""
        mock_repos = [
            {
                "id": 1,
                "name": "repo1",
                "full_name": "user/repo1",
                "owner": {"login": "user"},
                "html_url": "https://github.com/user/repo1",
            },
            {
                "id": 2,
                "name": "repo2",
                "full_name": "user/repo2",
                "owner": {"login": "user"},
                "html_url": "https://github.com/user/repo2",
            },
        ]

        # Mock paginated responses
        responses.add(
            responses.GET,
            "https://api.github.com/user/repos",
            json=mock_repos[:1],  # First page
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.github.com/user/repos",
            json=mock_repos[1:],  # Second page
            status=200,
        )

        repos = self.client.get_user_repositories()

        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"
        assert repos[1]["name"] == "repo2"

    @responses.activate
    def test_get_pull_requests(self) -> None:
        """Test getting pull requests."""
        mock_prs = [
            {
                "id": 1,
                "number": 1,
                "title": "Test PR 1",
                "state": "closed",
                "user": {"login": "user"},
                "html_url": "https://github.com/user/repo/pull/1",
            },
            {
                "id": 2,
                "number": 2,
                "title": "Test PR 2",
                "state": "closed",
                "user": {"login": "user"},
                "html_url": "https://github.com/user/repo/pull/2",
            },
        ]

        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo/pulls",
            json=mock_prs,
            status=200,
        )

        prs = self.client.get_pull_requests("user", "repo")

        assert len(prs) == 2
        assert prs[0]["number"] == 1
        assert prs[1]["number"] == 2

    @responses.activate
    def test_get_pull_request_comments(self) -> None:
        """Test getting pull request comments."""
        mock_comments = [
            {
                "id": 1,
                "body": "This code needs improvement",
                "path": "src/main.py",
                "position": 5,
                "line": 10,
                "user": {"login": "reviewer"},
                "html_url": "https://github.com/user/repo/pull/1#discussion_r1",
            },
        ]

        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo/pulls/1/comments",
            json=mock_comments,
            status=200,
        )

        comments = self.client.get_pull_request_comments("user", "repo", 1)

        assert len(comments) == 1
        assert comments[0]["body"] == "This code needs improvement"
        assert comments[0]["path"] == "src/main.py"

    @responses.activate
    def test_get_repository_info(self) -> None:
        """Test getting repository information."""
        mock_repo = {
            "id": 1,
            "name": "test-repo",
            "full_name": "user/test-repo",
            "description": "Test repository",
            "stargazers_count": 5,
            "forks_count": 2,
            "watchers_count": 3,
            "open_issues_count": 1,
            "language": "Python",
            "size": 1024,
            "has_wiki": True,
            "has_pages": False,
            "has_issues": True,
            "has_projects": False,
            "archived": False,
            "disabled": False,
            "owner": {"login": "user"},
        }

        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/test-repo",
            json=mock_repo,
            status=200,
        )

        repo_info = self.client.get_repository_info("user", "test-repo")

        assert repo_info["info"]["name"] == "test-repo"
        assert repo_info["stats"]["stars"] == 5
        assert repo_info["stats"]["language"] == "Python"

    @responses.activate
    def test_validate_repository_access(self) -> None:
        """Test repository access validation."""
        # Valid repository
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/valid-repo",
            json={"id": 1, "name": "valid-repo"},
            status=200,
        )

        assert self.client.validate_repository_access("user", "valid-repo") is True

        # Invalid repository
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/invalid-repo",
            json={"message": "Not Found"},
            status=404,
        )

        assert self.client.validate_repository_access("user", "invalid-repo") is False

    @responses.activate
    def test_rate_limit_handling(self) -> None:
        """Test rate limit handling."""
        # Mock rate limit response
        responses.add(
            responses.GET,
            "https://api.github.com/rate_limit",
            json={
                "resources": {
                    "core": {
                        "limit": 5000,
                        "remaining": 0,
                        "reset": 1234567890,
                    },
                },
            },
            status=200,
        )

        rate_limit = self.client.get_rate_limit_status()

        assert rate_limit["resources"]["core"]["remaining"] == 0
        assert rate_limit["resources"]["core"]["reset"] == 1234567890

    @responses.activate
    def test_connection_test(self) -> None:
        """Test connection to GitHub API."""
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"login": "user"},
            status=200,
        )

        assert self.client.test_connection() is True

    @responses.activate
    def test_connection_test_failure(self) -> None:
        """Test connection failure."""
        responses.add(
            responses.GET,
            "https://api.github.com/user",
            json={"message": "Bad credentials"},
            status=401,
        )

        assert self.client.test_connection() is False

    @responses.activate
    def test_error_handling(self) -> None:
        """Test error handling."""
        responses.add(
            responses.GET,
            "https://api.github.com/repos/user/repo",
            json={"message": "Server Error"},
            status=500,
        )

        with pytest.raises(Exception):
            self.client.get_repository("user", "repo")

    def test_initialization_without_token(self) -> None:
        """Test client initialization without token."""
        client = GitHubAPIClient()
        assert client.access_token is None
        assert "Authorization" not in client.session.headers

    def test_initialization_with_token(self) -> None:
        """Test client initialization with token."""
        client = GitHubAPIClient("test_token")
        assert client.access_token == "test_token"
        assert client.session.headers["Authorization"] == "token test_token"
