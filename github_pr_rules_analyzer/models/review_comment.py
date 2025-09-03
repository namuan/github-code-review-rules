"""Review Comment data model."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class ReviewComment(Base):
    """Review Comment model representing a GitHub review comment."""

    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_id = Column(Integer, unique=True, nullable=False, index=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    author_login = Column(String(255), nullable=False, index=True)
    body = Column(Text, nullable=False)
    path = Column(String(500), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    line = Column(Integer)
    side = Column(String(20))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    html_url = Column(Text, nullable=False)
    diff_hunk = Column(Text)

    # Timestamps
    created_at_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at_timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pull_request = relationship("PullRequest", back_populates="review_comments")
    code_snippets = relationship("CodeSnippet", back_populates="review_comment", cascade="all, delete-orphan")
    comment_threads = relationship("CommentThread", back_populates="review_comment", cascade="all, delete-orphan")
    extracted_rules = relationship("ExtractedRule", back_populates="review_comment", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (Index("idx_review_comments_dates", "created_at"),)

    def __repr__(self) -> str:
        """Return a string representation of the ReviewComment object."""
        return f"<ReviewComment(id={self.id}, author='{self.author_login}', path='{self.path}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "github_id": self.github_id,
            "pull_request_id": self.pull_request_id,
            "author_login": self.author_login,
            "body": self.body,
            "path": self.path,
            "position": self.position,
            "line": self.line,
            "side": self.side,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "html_url": self.html_url,
            "diff_hunk": self.diff_hunk,
            "created_at_timestamp": self.created_at_timestamp.isoformat(),
            "updated_at_timestamp": self.updated_at_timestamp.isoformat(),
        }

    def to_github_dict(self) -> dict[str, Any]:
        """Convert to GitHub API-like format."""
        return {
            "id": self.github_id,
            "pull_request_review_id": None,  # Would be set if this was a review comment
            "body": self.body,
            "path": self.path,
            "position": self.position,
            "commit_id": None,  # Would be set for PR review comments
            "original_commit_id": None,
            "user": {
                "login": self.author_login,
            },
            "html_url": self.html_url,
            "diff_hunk": self.diff_hunk,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "subject_type": "file",
            "subject_url": None,
        }

    @classmethod
    def from_github_data(cls, github_data, pull_request_id) -> "ReviewComment":
        """Create instance from GitHub API data."""
        return cls(
            github_id=github_data["id"],
            pull_request_id=pull_request_id,
            author_login=github_data["user"]["login"],
            body=github_data["body"],
            path=github_data["path"],
            position=github_data["position"],
            line=github_data.get("line"),
            side=github_data.get("side"),
            created_at=datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None,
            updated_at=datetime.fromisoformat(github_data["updated_at"]) if github_data.get("updated_at") else None,
            html_url=github_data["html_url"],
            diff_hunk=github_data.get("diff_hunk"),
        )

    def update_from_github_data(self, github_data) -> None:
        """Update instance from GitHub API data."""
        self.author_login = github_data["user"]["login"]
        self.body = github_data["body"]
        self.path = github_data["path"]
        self.position = github_data["position"]
        self.line = github_data.get("line")
        self.side = github_data.get("side")
        self.created_at = datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None
        self.updated_at = datetime.fromisoformat(github_data["updated_at"]) if github_data.get("updated_at") else None
        self.html_url = github_data["html_url"]
        self.diff_hunk = github_data.get("diff_hunk")
        self.updated_at_timestamp = datetime.now(UTC)

    def get_code_snippets(self) -> list[Any]:
        """Get all code snippets associated with this comment."""
        return self.code_snippets

    def get_extracted_rules(self) -> list[Any]:
        """Get all extracted rules from this comment."""
        return self.extracted_rules

    def get_rule_categories(self) -> list[str]:
        """Get unique rule categories from extracted rules."""
        categories = set()
        for rule in self.extracted_rules:
            if rule.rule_category:
                categories.add(rule.rule_category)
        return sorted(categories)

    @property
    def has_rules(self) -> bool:
        """Check if this comment has extracted rules."""
        return len(self.extracted_rules) > 0

    @property
    def has_code_snippets(self) -> bool:
        """Check if this comment has associated code snippets."""
        return len(self.code_snippets) > 0

    def get_context_summary(self, max_length: int = 200) -> str:
        """Get a summary of the comment context."""
        if not self.body:
            return "No comment body"

        summary = self.body.strip()
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        return summary
