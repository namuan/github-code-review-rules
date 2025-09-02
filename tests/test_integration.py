"""Integration tests for the GitHub PR Rules Analyzer."""

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from github_pr_rules_analyzer.main import app
from github_pr_rules_analyzer.models import ExtractedRule, PullRequest, Repository, ReviewComment
from github_pr_rules_analyzer.utils.database import Base, get_session_local

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


# Override database dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_session_local] = override_get_db

# Create test client
client = TestClient(app)


class TestIntegration:
    """Integration tests for the entire system."""

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

    def test_full_workflow_repository_addition_to_rule_extraction(self) -> None:
        """Test complete workflow from repository addition to rule extraction."""
        # Step 1: Add repository
        repo_data = {
            "owner": "testuser",
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
                    "full_name": "testuser/test-repo",
                    "owner": {"login": "testuser"},
                    "html_url": "https://github.com/testuser/test-repo",
                    "description": "Test repository",
                    "language": "Python",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z",
                },
            }

            response = client.post("/api/v1/repositories", json=repo_data)
            assert response.status_code == 200
            repo_response = response.json()
            repo_id = repo_response["repository"]["id"]

        # Step 2: Sync repository (mock data collection)
        with patch("github_pr_rules_analyzer.api.routes.DataCollector") as mock_collector:
            mock_instance = Mock()
            mock_collector.return_value = mock_instance

            # Mock PR data
            mock_pr_data = {
                "github_id": 67890,
                "number": 1,
                "title": "Add new feature",
                "state": "closed",
                "author_login": "testuser",
                "html_url": "https://github.com/testuser/test-repo/pull/1",
                "created_at": "2023-01-02T00:00:00Z",
                "closed_at": "2023-01-03T00:00:00Z",
            }

            # Mock review comment data
            mock_comment_data = {
                "github_id": 11111,
                "body": "This code needs improvement",
                "path": "src/main.py",
                "position": 5,
                "line": 10,
                "author_login": "reviewer",
                "html_url": "https://github.com/testuser/test-repo/pull/1#discussion_r11111",
            }

            mock_instance.collect_repository_data.return_value = {
                "pull_requests": [mock_pr_data],
                "review_comments": [mock_comment_data],
                "code_snippets": [],
                "comment_threads": [],
                "errors": [],
            }

            response = client.post(f"/api/v1/sync/{repo_id}")
            assert response.status_code == 200
            sync_response = response.json()
            assert sync_response["processed_comments"] == 1

        # Step 3: Extract rules from comments
        response = client.post("/api/v1/rules/extract", json=[1])
        assert response.status_code == 200
        extract_response = response.json()
        assert extract_response["extracted_count"] == 1

        # Step 4: Verify rule was created
        response = client.get("/api/v1/rules")
        assert response.status_code == 200
        rules_response = response.json()
        assert rules_response["total"] == 1
        assert rules_response["rules"][0]["rule_text"] == "Use meaningful variable names"

    def test_dashboard_data_aggregation(self) -> None:
        """Test dashboard data aggregation from multiple sources."""
        # Create test data
        db = TestingSessionLocal()

        # Create repository
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="testuser/test-repo",
            owner_login="testuser",
            html_url="https://github.com/testuser/test-repo",
            description="Test repository",
            language="Python",
        )
        db.add(repo)
        db.commit()

        # Create PR
        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        # Create comment
        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="testuser",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/testuser/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        # Create rule
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

        # Test dashboard endpoint
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        dashboard_data = response.json()

        # Verify all data is present
        assert dashboard_data["repositories"]["total"] == 1
        assert dashboard_data["repositories"]["active"] == 1
        assert dashboard_data["pull_requests"]["total"] == 1
        assert dashboard_data["pull_requests"]["closed"] == 1
        assert dashboard_data["review_comments"]["total"] == 1
        assert dashboard_data["rules"]["total"] == 1
        assert dashboard_data["rules"]["valid"] == 1
        assert len(dashboard_data["recent_rules"]) == 1
        assert dashboard_data["recent_rules"][0]["rule_text"] == "Use meaningful variable names"

    def test_repository_rules_filtering(self) -> None:
        """Test filtering rules by repository."""
        db = TestingSessionLocal()

        # Create two repositories
        repo1 = Repository(
            github_id=12345,
            name="repo1",
            full_name="user/repo1",
            owner_login="user",
            html_url="https://github.com/user/repo1",
        )
        repo2 = Repository(
            github_id=67890,
            name="repo2",
            full_name="user/repo2",
            owner_login="user",
            html_url="https://github.com/user/repo2",
        )
        db.add_all([repo1, repo2])
        db.commit()

        # Create PRs for both repositories
        pr1 = PullRequest(
            github_id=11111,
            repository_id=repo1.id,
            number=1,
            title="PR 1",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/repo1/pull/1",
        )
        pr2 = PullRequest(
            github_id=22222,
            repository_id=repo2.id,
            number=1,
            title="PR 2",
            state="closed",
            author_login="user",
            html_url="https://github.com/user/repo2/pull/1",
        )
        db.add_all([pr1, pr2])
        db.commit()

        # Create comments and rules
        comment1 = ReviewComment(
            github_id=33333,
            pull_request_id=pr1.id,
            author_login="user",
            body="Comment 1",
            path="file1.py",
            position=1,
            line=1,
            html_url="https://github.com/user/repo1/pull/1#discussion_r33333",
        )
        comment2 = ReviewComment(
            github_id=44444,
            pull_request_id=pr2.id,
            author_login="user",
            body="Comment 2",
            path="file2.py",
            position=1,
            line=1,
            html_url="https://github.com/user/repo2/pull/1#discussion_r44444",
        )
        db.add_all([comment1, comment2])
        db.commit()

        rule1 = ExtractedRule(
            review_comment_id=comment1.id,
            rule_text="Rule 1",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        rule2 = ExtractedRule(
            review_comment_id=comment2.id,
            rule_text="Rule 2",
            rule_category="style",
            rule_severity="low",
            confidence_score=0.6,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add_all([rule1, rule2])
        db.commit()
        db.close()

        # Test filtering by repository
        response = client.get(f"/api/v1/repositories/{repo1.id}/rules")
        assert response.status_code == 200
        repo1_rules = response.json()
        assert repo1_rules["total"] == 1
        assert repo1_rules["rules"][0]["rule_text"] == "Rule 1"

        response = client.get(f"/api/v1/repositories/{repo2.id}/rules")
        assert response.status_code == 200
        repo2_rules = response.json()
        assert repo2_rules["total"] == 1
        assert repo2_rules["rules"][0]["rule_text"] == "Rule 2"

    def test_rule_search_functionality(self) -> None:
        """Test rule search functionality."""
        db = TestingSessionLocal()

        # Create repository and PR
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="testuser/test-repo",
            owner_login="testuser",
            html_url="https://github.com/testuser/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        # Create multiple rules with different content
        rules_data = [
            {
                "body": "Use meaningful variable names",
                "rule_text": "Variables should have descriptive names",
                "category": "naming",
            },
            {
                "body": "Add error handling",
                "rule_text": "Always handle exceptions properly",
                "category": "error_handling",
            },
            {
                "body": "Code style",
                "rule_text": "Follow consistent code formatting",
                "category": "style",
            },
        ]

        for i, rule_data in enumerate(rules_data):
            comment = ReviewComment(
                github_id=11111 + i,
                pull_request_id=pr.id,
                author_login="testuser",
                body=rule_data["body"],
                path="src/main.py",
                position=5,
                line=10,
                html_url="https://github.com/testuser/test-repo/pull/1#discussion_r11111",
            )
            db.add(comment)
            db.commit()

            rule = ExtractedRule(
                review_comment_id=comment.id,
                rule_text=rule_data["rule_text"],
                rule_category=rule_data["category"],
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

        # Test search functionality
        response = client.get("/api/v1/rules/search?query=meaningful")
        assert response.status_code == 200
        search_results = response.json()
        assert search_results["total"] == 1
        assert search_results["rules"][0]["rule_text"] == "Variables should have descriptive names"

        response = client.get("/api/v1/rules/search?query=error")
        assert response.status_code == 200
        search_results = response.json()
        assert search_results["total"] == 1
        assert search_results["rules"][0]["rule_text"] == "Always handle exceptions properly"

        response = client.get("/api/v1/rules/search?query=code")
        assert response.status_code == 200
        search_results = response.json()
        assert search_results["total"] == 2  # Both "meaningful variable names" and "code formatting"

    def test_rule_statistics_calculation(self) -> None:
        """Test rule statistics calculation."""
        db = TestingSessionLocal()

        # Create repository and PR
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="testuser/test-repo",
            owner_login="testuser",
            html_url="https://github.com/testuser/test-repo",
        )
        db.add(repo)
        db.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        # Create rules with different categories and severities
        rules_data = [
            {
                "body": "Naming issue",
                "rule_text": "Use meaningful variable names",
                "category": "naming",
                "severity": "medium",
                "confidence": 0.8,
            },
            {
                "body": "Style issue",
                "rule_text": "Follow consistent code formatting",
                "category": "style",
                "severity": "low",
                "confidence": 0.6,
            },
            {
                "body": "Error handling",
                "rule_text": "Always handle exceptions properly",
                "category": "error_handling",
                "severity": "high",
                "confidence": 0.9,
            },
            {
                "body": "Another naming issue",
                "rule_text": "Use descriptive function names",
                "category": "naming",
                "severity": "medium",
                "confidence": 0.7,
            },
        ]

        for i, rule_data in enumerate(rules_data):
            comment = ReviewComment(
                github_id=11111 + i,
                pull_request_id=pr.id,
                author_login="testuser",
                body=rule_data["body"],
                path="src/main.py",
                position=5,
                line=10,
                html_url="https://github.com/testuser/test-repo/pull/1#discussion_r11111",
            )
            db.add(comment)
            db.commit()

            rule = ExtractedRule(
                review_comment_id=comment.id,
                rule_text=rule_data["rule_text"],
                rule_category=rule_data["category"],
                rule_severity=rule_data["severity"],
                confidence_score=rule_data["confidence"],
                llm_model="gpt-4",
                prompt_used="Test prompt",
                response_raw='{"rule": "test"}',
                is_valid=True,
            )
            db.add(rule)
            db.commit()

        db.close()

        # Test statistics endpoint
        response = client.get("/api/v1/rules/statistics")
        assert response.status_code == 200
        stats = response.json()

        # Verify total count
        assert stats["total_rules"] == 4

        # Verify category distribution
        assert stats["category_distribution"]["naming"] == 2
        assert stats["category_distribution"]["style"] == 1
        assert stats["category_distribution"]["error_handling"] == 1

        # Verify severity distribution
        assert stats["severity_distribution"]["medium"] == 2
        assert stats["severity_distribution"]["low"] == 1
        assert stats["severity_distribution"]["high"] == 1

        # Verify average confidence
        assert stats["average_confidence"] == 0.75  # (0.8 + 0.6 + 0.9 + 0.7) / 4

    def test_repository_statistics_endpoint(self) -> None:
        """Test repository-specific statistics endpoint."""
        db = TestingSessionLocal()

        # Create repository
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="testuser/test-repo",
            owner_login="testuser",
            html_url="https://github.com/testuser/test-repo",
        )
        db.add(repo)
        db.commit()

        # Create PRs
        pr1 = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="PR 1",
            state="closed",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/1",
        )
        pr2 = PullRequest(
            github_id=67891,
            repository_id=repo.id,
            number=2,
            title="PR 2",
            state="open",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/2",
        )
        db.add_all([pr1, pr2])
        db.commit()

        # Create comments
        comment1 = ReviewComment(
            github_id=11111,
            pull_request_id=pr1.id,
            author_login="testuser",
            body="Comment 1",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/testuser/test-repo/pull/1#discussion_r11111",
        )
        comment2 = ReviewComment(
            github_id=11112,
            pull_request_id=pr2.id,
            author_login="testuser",
            body="Comment 2",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/testuser/test-repo/pull/2#discussion_r11112",
        )
        db.add_all([comment1, comment2])
        db.commit()

        # Create rules
        rule1 = ExtractedRule(
            review_comment_id=comment1.id,
            rule_text="Rule 1",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.8,
            llm_model="gpt-4",
            prompt_used="Test prompt",
            response_raw='{"rule": "test"}',
            is_valid=True,
        )
        db.add(rule1)
        db.commit()

        db.close()

        # Test repository statistics
        response = client.get(f"/api/v1/repositories/{repo.id}/statistics")
        assert response.status_code == 200
        stats = response.json()

        # Verify repository info
        assert stats["repository"]["name"] == "test-repo"
        assert stats["repository"]["full_name"] == "testuser/test-repo"

        # Verify PR statistics
        assert stats["pull_requests"]["total"] == 2
        assert stats["pull_requests"]["closed"] == 1

        # Verify comment statistics
        assert stats["review_comments"]["total"] == 2

        # Verify rule statistics
        assert stats["rules"]["total"] == 1

        # Verify category distribution
        assert stats["category_distribution"]["naming"] == 1

    def test_error_handling_and_rollback(self) -> None:
        """Test error handling and database rollback."""
        # Test adding repository with invalid data
        invalid_repo_data = {
            "owner": "",  # Empty owner
            "name": "test-repo",
        }

        response = client.post("/api/v1/repositories", json=invalid_repo_data)
        assert response.status_code == 422  # Validation error

        # Verify no repository was created
        response = client.get("/api/v1/repositories")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Test extracting rules with invalid comment IDs
        response = client.post("/api/v1/rules/extract", json=[99999])  # Non-existent comment
        assert response.status_code == 404  # Not found

        # Test getting non-existent resource
        response = client.get("/api/v1/repositories/99999/rules")
        assert response.status_code == 404  # Not found

        response = client.get("/api/v1/rules/99999")
        assert response.status_code == 404  # Not found

        response = client.get("/api/v1/pull-requests/99999")
        assert response.status_code == 404  # Not found

    def test_api_rate_limiting_and_error_responses(self) -> None:
        """Test API rate limiting and error responses."""
        # Test multiple rapid requests to the same endpoint
        for _i in range(10):
            response = client.get("/api/v1/dashboard")
            assert response.status_code == 200

        # Test malformed JSON requests
        response = client.post("/api/v1/repositories", data="invalid json")
        assert response.status_code == 422  # Validation error

        # Test missing required fields
        incomplete_data = {"owner": "testuser"}  # Missing name
        response = client.post("/api/v1/repositories", json=incomplete_data)
        assert response.status_code == 422  # Validation error

        # Test invalid data types
        invalid_data = {
            "owner": 123,  # Should be string
            "name": "test-repo",
        }
        response = client.post("/api/v1/repositories", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_data_consistency_and_integrity(self) -> None:
        """Test data consistency and integrity across operations."""
        db = TestingSessionLocal()

        # Create repository
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="testuser/test-repo",
            owner_login="testuser",
            html_url="https://github.com/testuser/test-repo",
        )
        db.add(repo)
        db.commit()

        # Create PR
        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="closed",
            author_login="testuser",
            html_url="https://github.com/testuser/test-repo/pull/1",
        )
        db.add(pr)
        db.commit()

        # Create comment
        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="testuser",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/testuser/test-repo/pull/1#discussion_r11111",
        )
        db.add(comment)
        db.commit()

        # Create rule
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

        # Verify relationships are maintained
        # Check that rule is linked to comment
        retrieved_rule = db.query(ExtractedRule).filter(ExtractedRule.id == rule.id).first()
        assert retrieved_rule.review_comment_id == comment.id

        # Check that comment is linked to PR
        retrieved_comment = db.query(ReviewComment).filter(ReviewComment.id == comment.id).first()
        assert retrieved_comment.pull_request_id == pr.id

        # Check that PR is linked to repository
        retrieved_pr = db.query(PullRequest).filter(PullRequest.id == pr.id).first()
        assert retrieved_pr.repository_id == repo.id

        # Test cascade deletion
        db.delete(repo)
        db.commit()

        # Verify all related data is deleted
        assert db.query(Repository).filter(Repository.id == repo.id).count() == 0
        assert db.query(PullRequest).filter(PullRequest.id == pr.id).count() == 0
        assert db.query(ReviewComment).filter(ReviewComment.id == comment.id).count() == 0
        assert db.query(ExtractedRule).filter(ExtractedRule.id == rule.id).count() == 0

        db.close()

    def test_concurrent_access_handling(self) -> None:
        """Test concurrent access handling."""
        import threading

        results = []
        errors = []

        def make_api_call() -> None:
            try:
                response = client.get("/api/v1/dashboard")
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads making concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_api_call)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests were successful
        assert len(errors) == 0
        assert all(status == 200 for status in results)

        # Test concurrent repository creation
        def create_repository(repo_name) -> None:
            try:
                repo_data = {
                    "owner": "testuser",
                    "name": repo_name,
                }
                response = client.post("/api/v1/repositories", json=repo_data)
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_repository, args=[f"repo-{i}"])
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all repository creations were successful
        assert len(errors) == 0
        assert all(status == 200 for status in results[-3:])  # Last 3 should be successful
