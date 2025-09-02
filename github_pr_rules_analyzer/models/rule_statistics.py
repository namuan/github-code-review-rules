"""Rule Statistics data model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from github_pr_rules_analyzer.utils.database import Base


class RuleStatistics(Base):
    """Rule Statistics model for tracking rule usage and performance."""

    __tablename__ = "rule_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("extracted_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    occurrence_count = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    avg_confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    rule = relationship("ExtractedRule", back_populates="rule_statistics")
    repository = relationship("Repository")

    # Indexes
    __table_args__ = (Index("idx_rule_statistics_dates", "first_seen", "last_seen"),)

    def __repr__(self) -> str:
        return f"<RuleStatistics(id={self.id}, rule_id={self.rule_id}, count={self.occurrence_count})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "repository_id": self.repository_id,
            "occurrence_count": self.occurrence_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "avg_confidence": self.avg_confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_rule_and_repository(cls, rule, repository):
        """Create rule statistics from rule and repository."""
        return cls(
            rule_id=rule.id,
            repository_id=repository.id,
            occurrence_count=1,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            avg_confidence=rule.confidence_score,
        )

    def increment_occurrence(self, confidence_score=None) -> None:
        """Increment occurrence count and update timestamps."""
        self.occurrence_count += 1
        self.last_seen = datetime.utcnow()

        if confidence_score is not None:
            # Update average confidence
            if self.avg_confidence is None:
                self.avg_confidence = confidence_score
            else:
                # Calculate new average
                total_confidence = (self.avg_confidence * (self.occurrence_count - 1)) + confidence_score
                self.avg_confidence = total_confidence / self.occurrence_count

        self.updated_at = datetime.utcnow()

    def update_first_seen(self, timestamp) -> None:
        """Update first seen timestamp if earlier than current."""
        if timestamp < self.first_seen:
            self.first_seen = timestamp
            self.updated_at = datetime.utcnow()

    def get_trend(self, days=30) -> str:
        """Get trend information for the rule."""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        if self.last_seen < cutoff_date:
            return "inactive"
        if self.occurrence_count > 10:
            return "frequent"
        if self.occurrence_count > 5:
            return "moderate"
        return "rare"

    def get_frequency_description(self) -> str:
        """Get human-readable frequency description."""
        if self.occurrence_count == 1:
            return "Once"
        if self.occurrence_count <= 5:
            return f"{self.occurrence_count} times"
        if self.occurrence_count <= 20:
            return f"Several times ({self.occurrence_count})"
        return f"Very frequently ({self.occurrence_count} times)"

    def get_confidence_description(self) -> str:
        """Get human-readable confidence description."""
        if self.avg_confidence is None:
            return "No confidence data"

        if self.avg_confidence >= 0.9:
            return "Very high confidence"
        if self.avg_confidence >= 0.7:
            return "High confidence"
        if self.avg_confidence >= 0.5:
            return "Medium confidence"
        return "Low confidence"

    def get_age_description(self) -> str:
        """Get human-readable age description."""
        from datetime import timedelta

        now = datetime.utcnow()
        age = now - self.first_seen

        if age < timedelta(days=7):
            return "Recent"
        if age < timedelta(days=30):
            return "Last month"
        if age < timedelta(days=90):
            return "Last 3 months"
        if age < timedelta(days=365):
            return "Last year"
        return "Over a year old"

    def get_recency_description(self) -> str:
        """Get human-readable recency description."""
        from datetime import timedelta

        now = datetime.utcnow()
        age = now - self.last_seen

        if age < timedelta(hours=24):
            return "Today"
        if age < timedelta(days=7):
            return "This week"
        if age < timedelta(days=30):
            return "This month"
        if age < timedelta(days=90):
            return "Last 3 months"
        return "Ago"

    def format_for_display(self):
        """Format statistics for display."""
        result = []
        result.append(f"Statistics ID: {self.id}")
        result.append(f"Rule ID: {self.rule_id}")
        result.append(f"Repository: {self.repository.full_name if self.repository else 'Unknown'}")
        result.append(f"Occurrences: {self.get_frequency_description()}")
        result.append(f"First Seen: {self.first_seen.strftime('%Y-%m-%d %H:%M:%S')} ({self.get_age_description()})")
        result.append(f"Last Seen: {self.last_seen.strftime('%Y-%m-%d %H:%M:%S')} ({self.get_recency_description()})")
        result.append(f"Average Confidence: {self.get_confidence_description()}")
        result.append(f"Trend: {self.get_trend().title()}")

        return "\n".join(result)

    def get_impact_score(self):
        """Calculate impact score based on frequency and confidence."""
        if not self.avg_confidence or self.occurrence_count == 0:
            return 0

        # Weight confidence more heavily than frequency
        confidence_weight = 0.7
        frequency_weight = 0.3

        # Normalize confidence (0-1)
        normalized_confidence = self.avg_confidence

        # Normalize frequency (log scale to prevent extreme values)
        import math

        normalized_frequency = min(math.log(self.occurrence_count + 1) / math.log(100), 1.0)

        # Calculate weighted score
        impact_score = normalized_confidence * confidence_weight + normalized_frequency * frequency_weight

        return round(impact_score, 2)

    def get_priority_level(self) -> str:
        """Get priority level based on impact and recency."""
        impact_score = self.get_impact_score()
        trend = self.get_trend()

        if impact_score >= 0.8 and trend in ["frequent", "moderate"]:
            return "high"
        if impact_score >= 0.6 or trend == "frequent":
            return "medium"
        if impact_score >= 0.3:
            return "low"
        return "minimal"

    def get_priority_description(self):
        """Get human-readable priority description."""
        priority_map = {
            "high": "High Priority - High impact and frequent occurrence",
            "medium": "Medium Priority - Moderate impact or frequent occurrence",
            "low": "Low Priority - Low impact but still relevant",
            "minimal": "Minimal Priority - Low impact and infrequent",
        }

        return priority_map.get(self.get_priority_level(), "Unknown priority")
