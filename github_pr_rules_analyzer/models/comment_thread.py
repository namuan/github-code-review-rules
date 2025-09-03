"""Comment Thread data model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class CommentThread(Base):
    """Comment Thread model representing related comments on the same file and position."""

    __tablename__ = "comment_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    review_comment_id = Column(
        Integer,
        ForeignKey("review_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_path = Column(String(500), nullable=False, index=True)
    thread_position = Column(Integer, nullable=False)
    is_resolved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    pull_request = relationship("PullRequest", back_populates="comment_threads")
    review_comment = relationship("ReviewComment", back_populates="comment_threads")

    # Indexes
    __table_args__ = (Index("idx_comment_threads_path", "thread_path"),)

    def __repr__(self) -> str:
        return f"<CommentThread(id={self.id}, path='{self.thread_path}', position={self.thread_position})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "pull_request_id": self.pull_request_id,
            "review_comment_id": self.review_comment_id,
            "thread_path": self.thread_path,
            "thread_position": self.thread_position,
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_review_comment(cls, review_comment, pull_request_id):
        """Create comment thread from review comment."""
        return cls(
            pull_request_id=pull_request_id,
            review_comment_id=review_comment.id,
            thread_path=review_comment.path,
            thread_position=review_comment.position,
            is_resolved=False,
        )

    def resolve(self) -> None:
        """Mark thread as resolved."""
        self.is_resolved = True
        self.updated_at = datetime.now(UTC)

    def unresolve(self) -> None:
        """Mark thread as unresolved."""
        self.is_resolved = False
        self.updated_at = datetime.now(UTC)

    @property
    def is_active(self) -> bool:
        """Check if thread is active (not resolved)."""
        return not self.is_resolved

    def get_thread_key(self) -> str:
        """Get a unique key for this thread."""
        return f"{self.thread_path}:{self.thread_position}"

    def matches_position(self, path, position):
        """Check if this thread matches the given path and position."""
        return self.thread_path == path and self.thread_position == position

    def get_related_comments(self, session):
        """Get all comments related to this thread."""
        # This would typically query for other comments in the same thread
        # For now, we just return the original review comment
        return [self.review_comment]

    def get_thread_summary(self):
        """Get a summary of the thread."""
        if not self.review_comment:
            return "No associated comment"

        return self.review_comment.get_context_summary(100)

    def get_participants(self):
        """Get list of participants in the thread."""
        participants = set()

        # Add original commenter
        if self.review_comment and self.review_comment.author_login:
            participants.add(self.review_comment.author_login)

        # In a more complex implementation, you would add other participants
        # from the thread comments

        return sorted(participants)

    def get_comment_count(self) -> int:
        """Get total number of comments in the thread."""
        # For now, just return 1 (the original review comment)
        # In a more complex implementation, this would count all thread comments
        return 1

    def get_last_activity(self):
        """Get the last activity timestamp."""
        return max(self.created_at, self.updated_at)

    def format_for_display(self):
        """Format thread for display."""
        result = []
        result.append(f"Thread ID: {self.id}")
        result.append(f"File: {self.thread_path}")
        result.append(f"Position: {self.thread_position}")
        result.append(f"Status: {'Resolved' if self.is_resolved else 'Active'}")
        result.append(f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        result.append(f"Participants: {', '.join(self.get_participants())}")
        result.append("")
        result.append("Summary:")
        result.append(self.get_thread_summary())

        return "\n".join(result)
