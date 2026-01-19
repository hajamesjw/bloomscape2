"""Recommendation data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class RecommendationCategory(Enum):
    """Categories of recommendations."""
    BUDGET = "budget"
    KEYWORD = "keyword"
    SEARCH_TERM = "search_term"
    GEO = "geo"
    AUDIENCE = "audience"
    CREATIVE = "creative"
    BID = "bid"
    STRUCTURE = "structure"
    DEVICE = "device"
    SCHEDULE = "schedule"
    EXTENSION = "extension"


class RiskLevel(Enum):
    """Risk levels for recommendations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RolloutStrategy(Enum):
    """Rollout strategies for recommendations."""
    IMMEDIATE = "immediate"
    GRADUAL = "gradual"
    TEST_FIRST = "test_first"
    MANUAL_REVIEW = "manual_review"


@dataclass
class ExpectedImpact:
    """Expected impact of a recommendation."""

    metric: str
    current_value: float
    expected_value: float
    change_percent: float
    confidence_interval_low: float
    confidence_interval_high: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": round(self.current_value, 2),
            "expected_value": round(self.expected_value, 2),
            "change_percent": round(self.change_percent, 1),
            "confidence_interval": [
                round(self.confidence_interval_low, 2),
                round(self.confidence_interval_high, 2),
            ],
        }


@dataclass
class Recommendation:
    """
    A single recommendation with full context and risk assessment.
    Every recommendation MUST have explanation and evidence.
    """

    id: str
    category: RecommendationCategory
    action: str  # Human-readable action description
    entity_type: str
    entity_id: str
    entity_name: str

    # Risk assessment (REQUIRED)
    confidence: float  # 0.0-1.0
    risk_level: RiskLevel
    expected_impact: ExpectedImpact
    downside_scenario: str

    # Implementation guidance
    rollout_strategy: RolloutStrategy
    rollback_trigger: str

    # Explanation (REQUIRED - no black box recommendations)
    rationale: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    # Execution details
    api_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    priority: int = 0  # Lower = higher priority
    executed: bool = False
    execution_result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "action": self.action,
            "entity": {
                "type": self.entity_type,
                "id": self.entity_id,
                "name": self.entity_name,
            },
            "confidence": round(self.confidence, 2),
            "risk_level": self.risk_level.value,
            "expected_impact": self.expected_impact.to_dict(),
            "downside_scenario": self.downside_scenario,
            "rollout_strategy": self.rollout_strategy.value,
            "rollback_trigger": self.rollback_trigger,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "assumptions": self.assumptions,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }

    def to_human_readable(self) -> str:
        """Generate human-readable recommendation text."""
        risk_emoji = {"low": "", "medium": "", "high": ""}
        emoji = risk_emoji.get(self.risk_level.value, "")

        impact_str = (
            f"{self.expected_impact.change_percent:+.1f}% {self.expected_impact.metric}"
        )

        return f"""
[{self.risk_level.value.upper()} RISK] {self.action}
Entity: {self.entity_name} ({self.entity_type})
Expected Impact: {impact_str}
Confidence: {self.confidence:.0%}

Why: {self.rationale}

Downside: {self.downside_scenario}
Rollback if: {self.rollback_trigger}
""".strip()


@dataclass
class RecommendationBatch:
    """A batch of recommendations for review."""

    generated_at: datetime
    recommendations: List[Recommendation]
    total_expected_impact: Dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendation_count": len(self.recommendations),
            "by_category": self._group_by_category(),
            "by_risk": self._group_by_risk(),
            "total_expected_impact": self.total_expected_impact,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def _group_by_category(self) -> Dict[str, int]:
        counts = {}
        for rec in self.recommendations:
            cat = rec.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _group_by_risk(self) -> Dict[str, int]:
        counts = {}
        for rec in self.recommendations:
            risk = rec.risk_level.value
            counts[risk] = counts.get(risk, 0) + 1
        return counts
