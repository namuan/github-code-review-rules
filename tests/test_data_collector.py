"""Unit tests for data collector service."""

from datetime import datetime
from unittest.mock import Mock, patch

from github_pr_rules_analyzer.services.data_collector import DataCollector


class TestDataCollector:
    """Test data collector service."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.collector = DataCollector("test_token")

    def test_initialization(self) -> None:
        """Test data collector initialization."""
        assert self.collector.github_client.access_token == "test_token"
        assert self.collector.session is not None

    @patch("github_pr_rules_analyzer.services.data_collector.GitHubAPIClient")
    def test_collect_repository_data_success(self, mock_github_client) -> None:
        """Test successful repository data collection."""
        # Mock GitHub client
        mock_client = Mock()
        mock_client.validate_repository_access.return_value = True
        mock_client.get_repository_info.return_value = {
            "info": {
                "id": 1,
                "name": "test-repo",
                "full_name": "user/test-repo",
                "description": "Test repository",
                "owner": {"login": "user"},
            },
            "stats": {},
        }
        mock_client.get_pull_requests.return_value = [
            {
                "id": 1,
                "number": 1,
                "title": "Test PR",
                "state": "closed",
                "head": {"repo": {"full_name": "user/test-repo"}},
                "user": {"login": "user"},
                "html_url": "https://github.com/user/test-repo/pull/1",
            },
        ]
        mock_client.get_all_comments.return_value = [
            {
                "id": 1,
                "body": "This code needs improvement",
                "path": "src/main.py",
                "position": 5,
                "line": 10,
                "diff_hunk": "@@ -1,5 +1,5 @@\n+def test():\n+    pass\n",
                "user": {"login": "reviewer"},
                "html_url": "https://github.com/user/test-repo/pull/1#discussion_r1",
            },
        ]
        mock_github_client.return_value = mock_client

        # Mock database session
        with patch("github_pr_rules_analyzer.services.data_collector.get_session_local") as mock_session:
            mock_db_session = Mock()
            mock_session.return_value = mock_db_session

            # Mock repository query
            mock_repo = Mock()
            mock_repo.to_dict.return_value = {"id": 1, "name": "test-repo"}
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Mock pull request query
            mock_pr = Mock()
            mock_pr.to_dict.return_value = {"id": 1, "number": 1}
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Mock review comment query
            mock_comment = Mock()
            mock_comment.to_dict.return_value = {"id": 1, "body": "Test comment"}
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Mock code snippet creation
            mock_snippet = Mock()
            mock_snippet.to_dict.return_value = {"id": 1, "file_path": "src/main.py"}
            mock_db_session.add = Mock()

            results = self.collector.collect_repository_data("user", "test-repo")

            assert results["repository"] is not None
            assert len(results["pull_requests"]) == 1
            assert len(results["review_comments"]) == 1
            assert len(results["code_snippets"]) == 1
            assert len(results["errors"]) == 0

    @patch("github_pr_rules_analyzer.services.data_collector.GitHubAPIClient")
    def test_collect_repository_data_access_denied(self, mock_github_client) -> None:
        """Test repository data collection with access denied."""
        # Mock GitHub client to return access denied
        mock_client = Mock()
        mock_client.validate_repository_access.return_value = False
        mock_github_client.return_value = mock_client

        results = self.collector.collect_repository_data("user", "test-repo")

        assert len(results["errors"]) > 0
        assert "access" in results["errors"][0].lower()

    @patch("github_pr_rules_analyzer.services.data_collector.GitHubAPIClient")
    def test_collect_repository_data_pr_collection_error(self, mock_github_client) -> None:
        """Test repository data collection with PR collection error."""
        # Mock GitHub client
        mock_client = Mock()
        mock_client.validate_repository_access.return_value = True
        mock_client.get_repository_info.return_value = {
            "info": {
                "id": 1,
                "name": "test-repo",
                "full_name": "user/test-repo",
                "description": "Test repository",
                "owner": {"login": "user"},
            },
            "stats": {},
        }
        mock_client.get_pull_requests.side_effect = Exception("API Error")
        mock_github_client.return_value = mock_client

        results = self.collector.collect_repository_data("user", "test-repo")

        assert len(results["errors"]) > 0
        assert "api error" in results["errors"][0].lower()

    def test_upsert_repository_new(self) -> None:
        """Test creating new repository."""
        mock_session = Mock()
        mock_repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "user/test-repo",
            "description": "Test repository",
            "owner": {"login": "user"},
        }

        with patch("github_pr_rules_analyzer.services.data_collector.Repository") as mock_repo_class:
            mock_repo_instance = Mock()
            mock_repo_class.from_github_data.return_value = mock_repo_instance
            mock_session.query.return_value.filter.return_value.first.return_value = None

            self.collector._upsert_repository(mock_repo_data)

            mock_repo_class.from_github_data.assert_called_once_with(mock_repo_data)
            mock_session.add.assert_called_once_with(mock_repo_instance)
            mock_session.commit.assert_called_once()

    def test_upsert_repository_existing(self) -> None:
        """Test updating existing repository."""
        mock_session = Mock()
        mock_repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "user/test-repo",
            "description": "Test repository",
            "owner": {"login": "user"},
        }

        mock_existing_repo = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing_repo

        self.collector._upsert_repository(mock_repo_data)

        mock_existing_repo.update_from_github_data.assert_called_once_with(mock_repo_data)
        mock_session.commit.assert_called_once()

    def test_upsert_pull_request_new(self) -> None:
        """Test creating new pull request."""
        mock_session = Mock()
        mock_pr_data = {
            "id": 1,
            "number": 1,
            "title": "Test PR",
            "state": "closed",
            "user": {"login": "user"},
        }
        repository_id = 1

        with patch("github_pr_rules_analyzer.services.data_collector.PullRequest") as mock_pr_class:
            mock_pr_instance = Mock()
            mock_pr_class.from_github_data.return_value = mock_pr_instance
            mock_session.query.return_value.filter.return_value.first.return_value = None

            self.collector._upsert_pull_request(mock_pr_data, repository_id)

            mock_pr_class.from_github_data.assert_called_once_with(mock_pr_data, repository_id)
            mock_session.add.assert_called_once_with(mock_pr_instance)
            mock_session.commit.assert_called_once()

    def test_upsert_pull_request_existing(self) -> None:
        """Test updating existing pull request."""
        mock_session = Mock()
        mock_pr_data = {
            "id": 1,
            "number": 1,
            "title": "Test PR",
            "state": "closed",
            "user": {"login": "user"},
        }
        repository_id = 1

        mock_existing_pr = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing_pr

        self.collector._upsert_pull_request(mock_pr_data, repository_id)

        mock_existing_pr.update_from_github_data.assert_called_once_with(mock_pr_data)
        mock_session.commit.assert_called_once()

    def test_upsert_review_comment_new(self) -> None:
        """Test creating new review comment."""
        mock_session = Mock()
        mock_comment_data = {
            "id": 1,
            "body": "This code needs improvement",
            "path": "src/main.py",
            "position": 5,
            "line": 10,
            "user": {"login": "reviewer"},
        }
        pull_request_id = 1

        with patch("github_pr_rules_analyzer.services.data_collector.ReviewComment") as mock_comment_class:
            mock_comment_instance = Mock()
            mock_comment_class.from_github_data.return_value = mock_comment_instance
            mock_session.query.return_value.filter.return_value.first.return_value = None

            self.collector._upsert_review_comment(mock_comment_data, pull_request_id)

            mock_comment_class.from_github_data.assert_called_once_with(mock_comment_data, pull_request_id)
            mock_session.add.assert_called_once_with(mock_comment_instance)
            mock_session.commit.assert_called_once()

    def test_extract_code_snippets(self) -> None:
        """Test code snippet extraction from diff hunk."""
        mock_session = Mock()
        mock_review_comment = Mock()
        mock_review_comment.path = "src/main.py"

        diff_hunk = """@@ -50,6 +50,6 @@
 def old_function():
     pass
+def new_function():
+    return True
 def another_function():
     pass"""

        with patch("github_pr_rules_analyzer.services.data_collector.CodeSnippet") as mock_snippet_class:
            mock_snippet_instance = Mock()
            mock_snippet_class.from_review_comment.return_value = mock_snippet_instance
            mock_session.add = Mock()

            result = self.collector._extract_code_snippets(mock_review_comment, diff_hunk)

            # Should create one snippet for the new function
            assert len(result) == 1
            mock_snippet_class.from_review_comment.assert_called()
            mock_session.add.assert_called()

    def test_detect_language(self) -> None:
        """Test language detection from file path."""
        # Test various file extensions
        assert self.collector._detect_language("src/main.py") == "python"
        assert self.collector._detect_language("src/app.js") == "javascript"
        assert self.collector._detect_language("src/types.ts") == "typescript"
        assert self.collector._detect_language("src/main.java") == "java"
        assert self.collector._detect_language("src/main.cpp") == "cpp"
        assert self.collector._detect_language("src/main.c") == "c"
        assert self.collector._detect_language("src/main.go") == "go"
        assert self.collector._detect_language("src/main.rs") == "rust"
        assert self.collector._detect_language("src/main.php") == "php"
        assert self.collector._detect_language("src/main.rb") == "ruby"
        assert self.collector._detect_language("src/main.swift") == "swift"
        assert self.collector._detect_language("src/main.kt") == "kotlin"
        assert self.collector._detect_language("src/main.scala") == "scala"
        assert self.collector._detect_language("src/index.html") == "html"
        assert self.collector._detect_language("src/style.css") == "css"
        assert self.collector._detect_language("src/Dockerfile") == "dockerfile"
        assert self.collector._detect_language("src/config.yaml") == "yaml"
        assert self.collector._detect_language("src/data.json") == "json"
        assert self.collector._detect_language("src/README.md") == "markdown"
        assert self.collector._detect_language("src/notes.txt") == "plaintext"

        # Test unknown extension
        assert self.collector._detect_language("src.unknown") is None

    def test_create_comment_thread_new(self) -> None:
        """Test creating new comment thread."""
        mock_session = Mock()
        mock_review_comment = Mock()
        mock_review_comment.path = "src/main.py"
        mock_review_comment.position = 5
        pull_request_id = 1

        with patch("github_pr_rules_analyzer.services.data_collector.CommentThread") as mock_thread_class:
            mock_thread_instance = Mock()
            mock_thread_class.from_review_comment.return_value = mock_thread_instance
            mock_session.query.return_value.filter.return_value.first.return_value = None
            mock_session.add = Mock()

            self.collector._create_comment_thread(mock_review_comment, pull_request_id)

            mock_thread_class.from_review_comment.assert_called_once_with(mock_review_comment, pull_request_id)
            mock_session.add.assert_called_once_with(mock_thread_instance)
            mock_session.commit.assert_called_once()

    def test_create_comment_thread_existing(self) -> None:
        """Test using existing comment thread."""
        mock_session = Mock()
        mock_review_comment = Mock()
        mock_review_comment.path = "src/main.py"
        mock_review_comment.position = 5
        pull_request_id = 1

        mock_existing_thread = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing_thread

        result = self.collector._create_comment_thread(mock_review_comment, pull_request_id)

        assert result == mock_existing_thread

    def test_get_collection_status(self) -> None:
        """Test getting collection status."""
        mock_session = Mock()

        # Mock query results
        mock_session.query.return_value.count.side_effect = [
            5,
            10,
            25,
            50,
            15,
        ]  # repos, prs, comments, snippets, threads

        with patch("github_pr_rules_analyzer.services.data_collector.GitHubAPIClient") as mock_client_class:
            mock_client = Mock()
            mock_client.get_rate_limit_status.return_value = {
                "resources": {
                    "core": {
                        "limit": 5000,
                        "remaining": 4500,
                        "reset": 1234567890,
                    },
                },
            }
            mock_client_class.return_value = mock_client

            result = self.collector.get_collection_status()

            assert result["repositories"] == 5
            assert result["pull_requests"] == 10
            assert result["review_comments"] == 25
            assert result["code_snippets"] == 50
            assert result["comment_threads"] == 15
            assert result["rate_limit"]["resources"]["core"]["remaining"] == 4500

    def test_cleanup_old_data(self) -> None:
        """Test cleaning up old data."""
        mock_session = Mock()

        # Mock query results
        mock_session.query.return_value.filter.return_value.delete.side_effect = [
            10,
            5,
            2,
            1,
            0,
        ]  # snippets, threads, comments, prs, repos

        from datetime import timedelta

        datetime.utcnow() - timedelta(days=30)

        result = self.collector.cleanup_old_data(30)

        assert result["code_snippets"] == 10
        assert result["comment_threads"] == 5
        assert result["review_comments"] == 2
        assert result["pull_requests"] == 1
        assert result["repositories"] == 0
        mock_session.commit.assert_called_once()

    def test_cleanup_old_data_error(self) -> None:
        """Test error handling in cleanup."""
        mock_session = Mock()

        # Mock query to raise exception
        mock_session.query.return_value.filter.return_value.delete.side_effect = Exception("Database error")

        from datetime import timedelta

        datetime.utcnow() - timedelta(days=30)

        result = self.collector.cleanup_old_data(30)

        assert "error" in result
        assert "database error" in result["error"].lower()
        mock_session.rollback.assert_called_once()
