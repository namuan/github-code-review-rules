"""Pull Request data model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class PullRequest(Base):
    """Pull Request model representing a GitHub pull request."""

    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_id = Column(Integer, unique=True, nullable=False, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(Text)
    state = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime)
    closed_at = Column(DateTime)
    merged_at = Column(DateTime)
    author_login = Column(String(255), nullable=False, index=True)
    html_url = Column(Text, nullable=False)
    diff_url = Column(Text)
    patch_url = Column(Text)

    # Timestamps
    created_at_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at_timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    repository = relationship("Repository", back_populates="pull_requests")
    review_comments = relationship("ReviewComment", back_populates="pull_request", cascade="all, delete-orphan")
    comment_threads = relationship("CommentThread", back_populates="pull_request", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (Index("idx_pull_requests_dates", "created_at", "closed_at"),)

    def __repr__(self) -> str:
        return f"<PullRequest(id={self.id}, number={self.number}, title='{self.title[:50]}...')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "github_id": self.github_id,
            "repository_id": self.repository_id,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "state": self.state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "author_login": self.author_login,
            "html_url": self.html_url,
            "diff_url": self.diff_url,
            "patch_url": self.patch_url,
            "created_at_timestamp": self.created_at_timestamp.isoformat(),
            "updated_at_timestamp": self.updated_at_timestamp.isoformat(),
        }

    def to_github_dict(self):
        """Convert to GitHub API-like format."""
        return {
            "id": self.github_id,
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "state": self.state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "user": {
                "login": self.author_login,
            },
            "html_url": self.html_url,
            "diff_url": self.diff_url,
            "patch_url": self.patch_url,
            "pull_request": True,
        }

    @classmethod
    def from_github_data(cls, github_data, repository_id):
        """Create instance from GitHub API data."""
        return cls(
            github_id=github_data["id"],
            repository_id=repository_id,
            number=github_data["number"],
            title=github_data["title"],
            body=github_data.get("body"),
            state=github_data["state"],
            created_at=datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None,
            closed_at=datetime.fromisoformat(github_data["closed_at"]) if github_data.get("closed_at") else None,
            merged_at=datetime.fromisoformat(github_data["merged_at"]) if github_data.get("merged_at") else None,
            author_login=github_data["user"]["login"],
            html_url=github_data["html_url"],
            diff_url=github_data.get("diff_url"),
            patch_url=github_data.get("patch_url"),
        )

    def update_from_github_data(self, github_data) -> None:
        """Update instance from GitHub API data."""
        self.number = github_data["number"]
        self.title = github_data["title"]
        self.body = github_data.get("body")
        self.state = github_data["state"]
        self.created_at = datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None
        self.closed_at = datetime.fromisoformat(github_data["closed_at"]) if github_data.get("closed_at") else None
        self.merged_at = datetime.fromisoformat(github_data["merged_at"]) if github_data.get("merged_at") else None
        self.author_login = github_data["user"]["login"]
        self.html_url = github_data["html_url"]
        self.diff_url = github_data.get("diff_url")
        self.patch_url = github_data.get("patch_url")
        self.updated_at_timestamp = datetime.utcnow()

    @property
    def is_closed(self):
        """Check if PR is closed."""
        return self.state == "closed"

    @property
    def is_merged(self):
        """Check if PR is merged."""
        return self.merged_at is not None

    @property
    def is_open(self):
        """Check if PR is open."""
        return self.state == "open"

    def get_review_comments_count(self):
        """Get total number of review comments."""
        return len(self.review_comments)

    def get_comment_threads_count(self):
        """Get total number of comment threads."""
        return len(self.comment_threads)

    def get_extracted_rules_count(self):
        """Get total number of extracted rules."""
        return sum(len(comment.extracted_rules) for comment in self.review_comments)
