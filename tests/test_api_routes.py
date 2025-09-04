"""Unit tests for API routes."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from github_pr_rules_analyzer.api.routes import get_db
from github_pr_rules_analyzer.main import app
from github_pr_rules_analyzer.models import ExtractedRule, PullRequest, Repository, ReviewComment
from github_pr_rules_analyzer.utils.database import Base

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


# Override database dependency
def override_get_db() -> Generator[Session, None, None]:
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


class TestAPIRoutes:
    """Test API routes."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Clean up database
        db = TestingSessionLocal()
        db.query(ExtractedRule).delete()
        db.query(ReviewComment).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.commit()
        db.close()

    def test_root_endpoint(self) -> None:
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "GitHub PR Rules Analyzer API" in response.text

    def test_api_root_endpoint(self) -> None:
        """Test API root endpoint."""
        response = client.get("/api/v1/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data

    def test_health_check(self) -> None:
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "GitHub PR Rules Analyzer"

    def test_get_repositories_empty(self) -> None:
        """Test getting repositories when none exist."""
        response = client.get("/api/v1/repositories")
        assert response.status_code == 200
        data = response.json()
        assert data["repositories"] == []
        assert data["total"] == 0

    def test_get_repositories_with_data(self) -> None:
        """Test getting repositories with data."""
        # Create test repository
        db = TestingSessionLocal()
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
            description="Test repository",
            language="Python",
        )
        db.add(repo)
        db.commit()
        db.close()

        response = client.get("/api/v1/repositories")
        assert response.status_code == 200
        data = response.json()
        assert len(data["repositories"]) == 1
        assert data["total"] == 1
        assert data["repositories"][0]["name"] == "test-repo"

    def test_add_repository_success(self) -> None:
        """Test adding repository successfully."""
        repo_data = {
            "owner": "user",
            "name": "test-repo",
        }

        with patch("github_pr_rules_analyzer.api.routes.DataCollector") as mock_collector:
            # Mock collector
            mock_instance = Mock()
            mock_collector.return_value = mock_instance

            # Mock validation
            mock_instance.validate_repository_access.return_value = {
                "success": True,
                "message": "Repository accessible",
            }

            # Mock repository info
            mock_instance.get_repository_info.return_value = {
                "success": True,
                "info": {
                    "id": 12345,
                    "name": "test-repo",
                    "full_name": "user/test-repo",
                    "owner": {"login": "user"},
                    "html_url": "https://github.com/user/test-repo",
                    "description": "Test repository",
                    "language": "Python",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z",
                },
            }

            response = client.post("/api/v1/repositories", json=repo_data)
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "repository" in data
            assert data["repository"]["name"] == "test-repo"

    def test_add_repository_missing_fields(self) -> None:
        """Test adding repository with missing fields."""
        repo_data = {
            "owner": "user",
            # Missing "name"
        }

        response = client.post("/api/v1/repositories", json=repo_data)
        assert response.status_code == 422  # Validation error

    def test_add_repository_already_exists(self) -> None:
        """Test adding repository that already exists."""
        # Create test repository first
        db = TestingSessionLocal()
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()
        db.close()

        repo_data = {
            "owner": "user",
            "name": "test-repo",
        }

        response = client.post("/api/v1/repositories", json=repo_data)
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_delete_repository_success(self) -> None:
        """Test deleting repository successfully."""
        # Create test repository first
        db = TestingSessionLocal()
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id
        db.close()

        response = client.delete(f"/api/v1/repositories/{repo_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Repository deleted successfully"

    def test_delete_repository_not_found(self) -> None:
        """Test deleting non-existent repository."""
        response = client.delete("/api/v1/repositories/999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_get_sync_status(self) -> None:
        """Test getting sync status."""
        with patch("github_pr_rules_analyzer.api.routes.DataProcessor") as mock_processor:
            # Mock processor
            mock_instance = Mock()
            mock_processor.return_value = mock_instance

            # Mock stats
            mock_instance.get_processing_stats.return_value = {
                "processed_count": 10,
                "error_count": 2,
                "queue_size": 5,
                "worker_count": 2,
                "is_running": True,
            }

            response = client.get("/api/v1/sync/status")
            assert response.status_code == 200
            data = response.json()
            assert "processing_stats" in data
            assert "timestamp" in data
            assert data["processing_stats"]["processed_count"] == 10

    def test_get_rules_empty(self) -> None:
        """Test getting rules when none exist."""
        response = client.get("/api/v1/rules")
        assert response.status_code == 200
        data = response.json()
        assert data["rules"] == []
        assert data["total"] == 0

    def test_get_rules_with_data(self) -> None:
        """Test getting rules with data."""
        # Create test rule
        db = TestingSessionLocal()

        # Create repository and PR first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="user",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/user/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule)
        db.commit()
        db.close()

        response = client.get("/api/v1/rules")
        assert response.status_code == 200
        data = response.json()
        assert len(data["rules"]) == 1
        assert data["total"] == 1
        assert data["rules"][0]["rule_text"] == "Use meaningful variable names"

    def test_get_rule_by_id(self) -> None:
        """Test getting rule by ID."""
        # Create test rule first
        db = TestingSessionLocal()

        # Create repository and PR first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="user",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/user/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule)
        db.commit()
        rule_id = rule.id
        db.close()

        response = client.get(f"/api/v1/rules/{rule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["rule_text"] == "Use meaningful variable names"
        assert data["rule_category"] == "naming"

    def test_get_rule_by_id_not_found(self) -> None:
        """Test getting non-existent rule by ID."""
        response = client.get("/api/v1/rules/999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_search_rules(self) -> None:
        """Test searching rules."""
        # Create test rule first
        db = TestingSessionLocal()

        # Create repository and PR first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="user",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/user/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule)
        db.commit()
        db.close()

        response = client.get("/api/v1/rules/search?query=meaningful")
        assert response.status_code == 200
        data = response.json()
        assert len(data["rules"]) == 1
        assert data["total"] == 1
        assert data["rules"][0]["rule_text"] == "Use meaningful variable names"

    def test_search_rules_no_results(self) -> None:
        """Test searching rules with no results."""
        response = client.get("/api/v1/rules/search?query=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["rules"] == []
        assert data["total"] == 0

    def test_get_rule_categories(self) -> None:
        """Test getting rule categories."""
        # Create test rule first
        db = TestingSessionLocal()

        # Create repository and PR first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="user",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/user/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule)
        db.commit()
        db.close()

        response = client.get("/api/v1/rules/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "naming" in data["categories"]

    def test_get_rule_severities(self) -> None:
        """Test getting rule severities."""
        # Create test rule first
        db = TestingSessionLocal()

        # Create repository and PR first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="user/test-repo",
            owner_login="user",
            html_url="https://github.com/user/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="user",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/user/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule)
        db.commit()
        db.close()

        response = client.get("/api/v1/rules/severities")
        assert response.status_code == 200
        data = response.json()
        assert "severities" in data
        assert "medium" in data["severities"]

    def test_get_dashboard_data_empty(self) -> None:
        """Test getting dashboard data with no data."""
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["repositories"]["total"] == 0
        assert data["repositories"]["active"] == 0
        assert data["pull_requests"]["total"] == 0
        assert data["pull_requests"]["closed"] == 0
        assert data["review_comments"]["total"] == 0
        assert data["rules"]["total"] == 0
        assert data["rules"]["valid"] == 0
        assert data["recent_rules"] == []

    def test_get_pull_request_not_found(self) -> None:
        """Test getting non-existent pull request."""
        response = client.get("/api/v1/pull-requests/999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_get_repository_rules_not_found(self) -> None:
        """Test getting rules for non-existent repository."""
        response = client.get("/api/v1/repositories/999/rules")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_get_repository_statistics_not_found(self) -> None:
        """Test getting statistics for non-existent repository."""
        response = client.get("/api/v1/repositories/999/statistics")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Repository not found"

    def test_404_error_handler(self) -> None:
        """Test 404 error handler."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
        assert "Page not found" in response.text

    def test_extract_rules_no_comments(self) -> None:
        """Test extracting rules with no valid comments."""
        response = client.post("/api/v1/rules/extract", json=[999])
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data  # Just check that detail field exists

    def test_extract_rules_invalid_input(self) -> None:
        """Test extracting rules with invalid input."""
        response = client.post("/api/v1/rules/extract", json="invalid")
        assert response.status_code == 422  # Validation error
