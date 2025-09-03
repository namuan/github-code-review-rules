"""Unit tests for data models."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from github_pr_rules_analyzer.models import ExtractedRule, PullRequest, Repository, ReviewComment


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    from github_pr_rules_analyzer.utils.database import Base

    Base.metadata.create_all(bind=engine)

    # Create session
    session = session_local()
    yield session

    # Close session
    session.close()


class TestRepository:
    """Test Repository model."""

    def test_repository_creation(self, db_session) -> None:
        """Test creating a repository."""
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
            description="Test repository",
        )

        db_session.add(repo)
        db_session.commit()

        assert repo.id is not None
        assert repo.github_id == 12345
        assert repo.name == "test-repo"
        assert repo.full_name == "owner/test-repo"
        assert repo.owner_login == "owner"
        assert repo.html_url == "https://github.com/owner/test-repo"
        assert repo.description == "Test repository"
        assert repo.is_active is True

    def test_repository_from_github_data(self, db_session) -> None:
        """Test creating repository from GitHub API data."""
        github_data = {
            "id": 12345,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": {"login": "owner"},
            "html_url": "https://github.com/owner/test-repo",
            "description": "Test repository",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "language": "Python",
        }

        repo = Repository.from_github_data(github_data)

        db_session.add(repo)
        db_session.commit()

        assert repo.github_id == 12345
        assert repo.name == "test-repo"
        assert repo.language == "Python"
        assert repo.created_at is not None

    def test_repository_to_dict(self, db_session) -> None:
        """Test converting repository to dictionary."""
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )

        db_session.add(repo)
        db_session.commit()

        repo_dict = repo.to_dict()

        assert repo_dict["id"] == repo.id
        assert repo_dict["github_id"] == 12345
        assert repo_dict["name"] == "test-repo"
        assert "created_at_timestamp" in repo_dict


class TestPullRequest:
    """Test PullRequest model."""

    def test_pull_request_creation(self, db_session) -> None:
        """Test creating a pull request."""
        # First create a repository
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        # Create pull request
        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )

        db_session.add(pr)
        db_session.commit()

        assert pr.id is not None
        assert pr.github_id == 67890
        assert pr.number == 1
        assert pr.title == "Test PR"
        assert pr.state == "open"
        assert pr.author_login == "testuser"
        assert pr.repository_id == repo.id

    def test_pull_request_properties(self, db_session) -> None:
        """Test pull request properties."""
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )

        db_session.add(pr)
        db_session.commit()

        assert pr.is_open is True
        assert pr.is_closed is False
        assert pr.is_merged is False

    def test_pull_request_from_github_data(self, db_session) -> None:
        """Test creating pull request from GitHub API data."""
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        github_data = {
            "id": 67890,
            "number": 1,
            "title": "Test PR",
            "body": "Test PR body",
            "state": "open",
            "created_at": "2023-01-01T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "user": {"login": "testuser"},
            "html_url": "https://github.com/owner/test-repo/pull/1",
            "diff_url": "https://github.com/owner/test-repo/pull/1.diff",
            "patch_url": "https://github.com/owner/test-repo/pull/1.patch",
        }

        pr = PullRequest.from_github_data(github_data, repo.id)

        db_session.add(pr)
        db_session.commit()

        assert pr.github_id == 67890
        assert pr.number == 1
        assert pr.title == "Test PR"
        assert pr.body == "Test PR body"
        assert pr.state == "open"
        assert pr.author_login == "testuser"


class TestReviewComment:
    """Test ReviewComment model."""

    def test_review_comment_creation(self, db_session) -> None:
        """Test creating a review comment."""
        # Create repository and pull request first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )
        db_session.add(pr)
        db_session.commit()

        # Create review comment
        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="reviewer",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/owner/test-repo/pull/1#discussion_r11111",
        )

        db_session.add(comment)
        db_session.commit()

        assert comment.id is not None
        assert comment.github_id == 11111
        assert comment.author_login == "reviewer"
        assert comment.body == "This code needs improvement"
        assert comment.path == "src/main.py"
        assert comment.position == 5
        assert comment.line == 10
        assert comment.pull_request_id == pr.id

    def test_review_comment_from_github_data(self, db_session) -> None:
        """Test creating review comment from GitHub API data."""
        # Create repository and pull request first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )
        db_session.add(pr)
        db_session.commit()

        github_data = {
            "id": 11111,
            "body": "This code needs improvement",
            "path": "src/main.py",
            "position": 5,
            "line": 10,
            "side": "RIGHT",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "html_url": "https://github.com/owner/test-repo/pull/1#discussion_r11111",
            "diff_hunk": "@@ -1,5 +1,5 @@\n+def test():\n+    pass\n",
            "user": {"login": "reviewer"},
        }

        comment = ReviewComment.from_github_data(github_data, pr.id)

        db_session.add(comment)
        db_session.commit()

        assert comment.github_id == 11111
        assert comment.body == "This code needs improvement"
        assert comment.path == "src/main.py"
        assert comment.position == 5
        assert comment.line == 10
        assert comment.side == "RIGHT"
        assert comment.author_login == "reviewer"


class TestExtractedRule:
    """Test ExtractedRule model."""

    def test_extracted_rule_creation(self, db_session) -> None:
        """Test creating an extracted rule."""
        # Create repository, pull request, and review comment first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )
        db_session.add(pr)
        db_session.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="reviewer",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/owner/test-repo/pull/1#discussion_r11111",
        )
        db_session.add(comment)
        db_session.commit()

        # Create extracted rule
        rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Use meaningful variable names",
            rule_category="naming",
            rule_severity="medium",
            confidence_score=0.85,
            llm_model="gpt-4",
            prompt_used="Extract coding rules from this comment",
            response_raw='{"rule": "Use meaningful variable names", "category": "naming"}',
        )

        db_session.add(rule)
        db_session.commit()

        assert rule.id is not None
        assert rule.review_comment_id == comment.id
        assert rule.rule_text == "Use meaningful variable names"
        assert rule.rule_category == "naming"
        assert rule.rule_severity == "medium"
        assert rule.confidence_score == 0.85
        assert rule.llm_model == "gpt-4"
        assert rule.is_valid is True

    def test_extracted_rule_properties(self, db_session) -> None:
        """Test extracted rule properties."""
        # Create repository, pull request, and review comment first
        repo = Repository(
            github_id=12345,
            name="test-repo",
            full_name="owner/test-repo",
            owner_login="owner",
            html_url="https://github.com/owner/test-repo",
        )
        db_session.add(repo)
        db_session.commit()

        pr = PullRequest(
            github_id=67890,
            repository_id=repo.id,
            number=1,
            title="Test PR",
            state="open",
            author_login="testuser",
            html_url="https://github.com/owner/test-repo/pull/1",
        )
        db_session.add(pr)
        db_session.commit()

        comment = ReviewComment(
            github_id=11111,
            pull_request_id=pr.id,
            author_login="reviewer",
            body="This code needs improvement",
            path="src/main.py",
            position=5,
            line=10,
            html_url="https://github.com/owner/test-repo/pull/1#discussion_r11111",
        )
        db_session.add(comment)
        db_session.commit()

        # Test high confidence rule
        high_conf_rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="High confidence rule",
            confidence_score=0.9,
        )
        db_session.add(high_conf_rule)
        db_session.commit()

        assert high_conf_rule.has_high_confidence is True
        assert high_conf_rule.has_medium_confidence is False
        assert high_conf_rule.has_low_confidence is False
        assert high_conf_rule.get_confidence_level() == "High"

        # Test medium confidence rule
        medium_conf_rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Medium confidence rule",
            confidence_score=0.6,
        )
        db_session.add(medium_conf_rule)
        db_session.commit()

        assert medium_conf_rule.has_high_confidence is False
        assert medium_conf_rule.has_medium_confidence is True
        assert medium_conf_rule.has_low_confidence is False
        assert medium_conf_rule.get_confidence_level() == "Medium"

        # Test low confidence rule
        low_conf_rule = ExtractedRule(
            review_comment_id=comment.id,
            rule_text="Low confidence rule",
            confidence_score=0.3,
        )
        db_session.add(low_conf_rule)
        db_session.commit()

        assert low_conf_rule.has_high_confidence is False
        assert low_conf_rule.has_medium_confidence is False
        assert low_conf_rule.has_low_confidence is True
        assert low_conf_rule.get_confidence_level() == "Low"


if __name__ == "__main__":
    pytest.main([__file__])
