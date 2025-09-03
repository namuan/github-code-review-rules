"""Repository data model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class Repository(Base):
    """Repository model representing a GitHub repository."""

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    owner_login = Column(String(255), nullable=False, index=True)
    html_url = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    language = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at_timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, full_name='{self.full_name}')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "github_id": self.github_id,
            "name": self.name,
            "full_name": self.full_name,
            "owner_login": self.owner_login,
            "html_url": self.html_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "language": self.language,
            "is_active": self.is_active,
            "created_at_timestamp": self.created_at_timestamp.isoformat(),
            "updated_at_timestamp": self.updated_at_timestamp.isoformat(),
        }

    def to_github_dict(self):
        """Convert to GitHub API-like format."""
        return {
            "id": self.github_id,
            "name": self.name,
            "full_name": self.full_name,
            "owner": {
                "login": self.owner_login,
            },
            "html_url": self.html_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "language": self.language,
            "private": False,  # We'll only handle public repos for now
        }

    @classmethod
    def from_github_data(cls, github_data):
        """Create instance from GitHub API data."""
        return cls(
            github_id=github_data["id"],
            name=github_data["name"],
            full_name=github_data["full_name"],
            owner_login=github_data["owner"]["login"],
            html_url=github_data["html_url"],
            description=github_data.get("description"),
            created_at=datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None,
            updated_at=datetime.fromisoformat(github_data["updated_at"]) if github_data.get("updated_at") else None,
            language=github_data.get("language"),
        )

    def update_from_github_data(self, github_data) -> None:
        """Update instance from GitHub API data."""
        self.name = github_data["name"]
        self.full_name = github_data["full_name"]
        self.owner_login = github_data["owner"]["login"]
        self.html_url = github_data["html_url"]
        self.description = github_data.get("description")
        self.created_at = datetime.fromisoformat(github_data["created_at"]) if github_data.get("created_at") else None
        self.updated_at = datetime.fromisoformat(github_data["updated_at"]) if github_data.get("updated_at") else None
        self.language = github_data.get("language")
        self.updated_at_timestamp = datetime.now(UTC)
