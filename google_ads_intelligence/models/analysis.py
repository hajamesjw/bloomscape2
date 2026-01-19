"""Analysis result data models."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum


class TrendDirection(Enum):
    """Direction of a trend."""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"


class PatternType(Enum):
    """Type of pattern detected."""
    SEASONAL = "seasonal"
    DAY_OF_WEEK = "day_of_week"
    RANDOM = "random"
    STRUCTURAL = "structural"


@dataclass
class LearningStatus:
    """Learning phase status for an entity."""

    is_in_learning: bool
    reason: Optional[str] = None
    triggered_at: Optional[datetime] = None
    expected_completion: Optional[date] = None
    days_remaining: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_in_learning": self.is_in_learning,
            "reason": self.reason,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "expected_completion": self.expected_completion.isoformat() if self.expected_completion else None,
            "days_remaining": self.days_remaining,
        }


@dataclass
class DataSufficiency:
    """Data sufficiency assessment for an entity."""

    is_sufficient: bool
    clicks: int
    conversions: float
    days_of_data: int
    required_clicks: int
    required_conversions: int
    required_days: int
    sufficiency_score: float  # 0.0-1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_sufficient": self.is_sufficient,
            "current": {
                "clicks": self.clicks,
                "conversions": self.conversions,
                "days": self.days_of_data,
            },
            "required": {
                "clicks": self.required_clicks,
                "conversions": self.required_conversions,
                "days": self.required_days,
            },
            "sufficiency_score": round(self.sufficiency_score, 2),
        }


@dataclass
class TrendAnalysis:
    """Result of trend analysis for an entity."""

    entity_type: str
    entity_id: str
    metric: str

    direction: TrendDirection
    confidence: float
    pattern: PatternType
    recommendation: str  # "wait", "investigate", "act"

    values_by_period: Dict[int, float] = field(default_factory=dict)
    percent_changes: Dict[int, float] = field(default_factory=dict)

    # Statistical measures
    mean: float = 0.0
    std_dev: float = 0.0
    coefficient_of_variation: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": {"type": self.entity_type, "id": self.entity_id},
            "metric": self.metric,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 2),
            "pattern": self.pattern.value,
            "recommendation": self.recommendation,
            "statistics": {
                "mean": round(self.mean, 2),
                "std_dev": round(self.std_dev, 2),
                "cv": round(self.coefficient_of_variation, 2),
            },
            "values_by_period": self.values_by_period,
            "percent_changes": self.percent_changes,
        }


@dataclass
class Anomaly:
    """Detected anomaly in performance data."""

    entity_type: str
    entity_id: str
    metric: str
    detected_at: date

    value: float
    expected_value: float
    deviation_std: float  # How many standard deviations from expected

    severity: str  # "info", "warning", "critical"
    is_positive: bool  # True if anomaly is better than expected
    possible_causes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": {"type": self.entity_type, "id": self.entity_id},
            "metric": self.metric,
            "detected_at": self.detected_at.isoformat(),
            "value": round(self.value, 2),
            "expected_value": round(self.expected_value, 2),
            "deviation_std": round(self.deviation_std, 2),
            "severity": self.severity,
            "is_positive": self.is_positive,
            "possible_causes": self.possible_causes,
        }


@dataclass
class SignificanceResult:
    """Result of statistical significance test."""

    is_significant: bool
    p_value: float
    effect_size: float  # Percentage difference
    test_used: str  # e.g., "t-test", "mann-whitney"
    sample_size_a: int
    sample_size_b: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_significant": self.is_significant,
            "p_value": round(self.p_value, 4),
            "effect_size": round(self.effect_size, 2),
            "test_used": self.test_used,
            "sample_sizes": [self.sample_size_a, self.sample_size_b],
        }


@dataclass
class BudgetUtilization:
    """Budget utilization analysis."""

    campaign_id: str
    campaign_name: str
    daily_budget: float

    avg_daily_spend_7d: float
    avg_daily_spend_30d: float
    utilization_rate_7d: float  # spend / budget
    utilization_rate_30d: float

    impression_share_lost_budget_7d: Optional[float]
    impression_share_lost_budget_30d: Optional[float]

    estimated_incremental_conversions: Optional[float] = None
    estimated_incremental_cost: Optional[float] = None
    estimated_incremental_cpa: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign": {"id": self.campaign_id, "name": self.campaign_name},
            "daily_budget": self.daily_budget,
            "utilization": {
                "spend_7d": round(self.avg_daily_spend_7d, 2),
                "spend_30d": round(self.avg_daily_spend_30d, 2),
                "rate_7d": round(self.utilization_rate_7d, 2),
                "rate_30d": round(self.utilization_rate_30d, 2),
            },
            "impression_share_lost_budget": {
                "7d": self.impression_share_lost_budget_7d,
                "30d": self.impression_share_lost_budget_30d,
            },
            "incremental_opportunity": {
                "conversions": self.estimated_incremental_conversions,
                "cost": self.estimated_incremental_cost,
                "cpa": self.estimated_incremental_cpa,
            },
        }


@dataclass
class CompetitiveInsight:
    """Competitive analysis from auction insights."""

    competitor_domain: str
    overlap_rate: float  # How often you compete
    position_above_rate: float  # How often they're above you
    top_of_page_rate: float
    outranking_share: float

    trend_7d: str = "stable"  # "increasing", "decreasing", "stable"
    is_new_competitor: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor": self.competitor_domain,
            "overlap_rate": round(self.overlap_rate, 2),
            "position_above_rate": round(self.position_above_rate, 2),
            "top_of_page_rate": round(self.top_of_page_rate, 2),
            "outranking_share": round(self.outranking_share, 2),
            "trend_7d": self.trend_7d,
            "is_new_competitor": self.is_new_competitor,
        }
