"""Extracted Rule data model."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class ExtractedRule(Base):
    """Extracted Rule model representing coding rules extracted from review comments."""

    __tablename__ = "extracted_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_comment_id = Column(
        Integer,
        ForeignKey("review_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_text = Column(Text, nullable=False)
    rule_category = Column(String(100), index=True)
    rule_severity = Column(String(50), index=True)
    confidence_score = Column(Float)
    llm_model = Column(String(100))
    prompt_used = Column(Text)
    response_raw = Column(Text)
    is_valid = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    review_comment = relationship("ReviewComment", back_populates="extracted_rules")
    rule_statistics = relationship("RuleStatistics", back_populates="rule", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (Index("idx_extracted_rules_dates", "created_at"),)

    def __repr__(self) -> str:
        """Return a string representation of the ExtractedRule object."""
        return f"<ExtractedRule(id={self.id}, category='{self.rule_category}', severity='{self.rule_severity}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "review_comment_id": self.review_comment_id,
            "rule_text": self.rule_text,
            "rule_category": self.rule_category,
            "rule_severity": self.rule_severity,
            "confidence_score": self.confidence_score,
            "llm_model": self.llm_model,
            "prompt_used": self.prompt_used,
            "response_raw": self.response_raw,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "id": self.id,
            "rule_text": self.rule_text,
            "category": self.rule_category,
            "severity": self.rule_severity,
            "confidence_score": self.confidence_score,
            "model": self.llm_model,
            "created_at": self.created_at.isoformat(),
            "repository_name": self.review_comment.pull_request.repository.full_name
            if self.review_comment and self.review_comment.pull_request
            else None,
            "pr_number": self.review_comment.pull_request.number
            if self.review_comment and self.review_comment.pull_request
            else None,
            "author": self.review_comment.author_login if self.review_comment else None,
            "file_path": self.review_comment.path if self.review_comment else None,
            "is_valid": self.is_valid,
        }

    @classmethod
    def from_llm_response(
        cls,
        review_comment,
        rule_text,
        rule_category=None,
        rule_severity=None,
        confidence_score=None,
        llm_model=None,
        prompt_used=None,
        response_raw=None,
    ) -> "ExtractedRule":
        """Create extracted rule from LLM response."""
        return cls(
            review_comment_id=review_comment.id,
            rule_text=rule_text,
            rule_category=rule_category,
            rule_severity=rule_severity,
            confidence_score=confidence_score,
            llm_model=llm_model,
            prompt_used=prompt_used,
            response_raw=response_raw,
        )

    def update_from_llm_response(
        self,
        rule_text,
        rule_category=None,
        rule_severity=None,
        confidence_score=None,
        llm_model=None,
        prompt_used=None,
        response_raw=None,
    ) -> None:
        """Update rule from LLM response."""
        self.rule_text = rule_text
        self.rule_category = rule_category
        self.rule_severity = rule_severity
        self.confidence_score = confidence_score
        self.llm_model = llm_model
        self.prompt_used = prompt_used
        self.response_raw = response_raw
        self.updated_at = datetime.now(UTC)

    def mark_as_valid(self) -> None:
        """Mark rule as valid."""
        self.is_valid = True
        self.updated_at = datetime.now(UTC)

    def mark_as_invalid(self) -> None:
        """Mark rule as invalid."""
        self.is_valid = False
        self.updated_at = datetime.now(UTC)

    @property
    def has_high_confidence(self) -> bool:
        """Check if rule has high confidence."""
        return self.confidence_score and self.confidence_score >= 0.8

    @property
    def has_medium_confidence(self) -> bool:
        """Check if rule has medium confidence."""
        return self.confidence_score and 0.5 <= self.confidence_score < 0.8

    @property
    def has_low_confidence(self) -> bool:
        """Check if rule has low confidence."""
        return self.confidence_score and self.confidence_score < 0.5

    def get_confidence_level(self) -> str:
        """Get confidence level as string."""
        if not self.confidence_score:
            return "Unknown"

        if self.confidence_score >= 0.8:
            return "High"
        if self.confidence_score >= 0.5:
            return "Medium"
        return "Low"

    def get_severity_display(self) -> str:
        """Get human-readable severity."""
        if not self.rule_severity:
            return "Unknown"

        severity_map = {
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
            "info": "Info",
        }

        return severity_map.get(self.rule_severity.lower(), self.rule_severity.title())

    def get_category_display(self) -> str:
        """Get human-readable category."""
        if not self.rule_category:
            return "General"

        category_map = {
            "naming": "Naming Conventions",
            "style": "Code Style",
            "performance": "Performance",
            "security": "Security",
            "best_practices": "Best Practices",
            "error_handling": "Error Handling",
            "testing": "Testing",
            "documentation": "Documentation",
            "architecture": "Architecture",
            "readability": "Readability",
        }

        return category_map.get(self.rule_category.lower(), self.rule_category.title())

    def get_context_info(self) -> dict[str, Any]:
        """Get context information about the rule."""
        context = {}

        if self.review_comment:
            context["author"] = self.review_comment.author_login
            context["file_path"] = self.review_comment.path
            context["line"] = self.review_comment.line
            context["pr_number"] = self.review_comment.pull_request.number
            context["repository"] = self.review_comment.pull_request.repository.full_name
            context["pr_title"] = self.review_comment.pull_request.title
            context["pr_url"] = self.review_comment.pull_request.html_url

        return context

    def format_for_display(self) -> str:
        """Format rule for display."""
        result = []
        result.append(f"Rule ID: {self.id}")
        result.append(f"Category: {self.get_category_display()}")
        result.append(f"Severity: {self.get_severity_display()}")
        result.append(f"Confidence: {self.get_confidence_level()} ({self.confidence_score:.2%})")
        result.append(f"Valid: {'Yes' if self.is_valid else 'No'}")
        result.append(f"Model: {self.llm_model or 'Unknown'}")
        result.append("")
        result.append("Rule:")
        result.append(self.rule_text)

        if self.review_comment:
            result.append("")
            result.append("Context:")
            result.append(f"  Author: {self.review_comment.author_login}")
            result.append(f"  File: {self.review_comment.path}")
            result.append(
                f"  PR: #{self.review_comment.pull_request.number} - {self.review_comment.pull_request.title}",
            )
            result.append(f"  Repository: {self.review_comment.pull_request.repository.full_name}")

        return "\n".join(result)

    def get_related_rules(self, _session) -> list[Any]:
        """Get related rules with similar text or category."""
        # This would typically find rules with similar text or same category
        # For now, return empty list
        return []

    def get_usage_statistics(self, _session) -> dict[str, Any]:
        """Get usage statistics for this rule."""
        # This would typically query rule_statistics table
        # For now, return empty dict
        return {}
