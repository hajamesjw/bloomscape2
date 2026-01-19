"""Data models for the Google Ads Intelligence System."""

from .entities import (
    Campaign,
    AdGroup,
    Keyword,
    Ad,
    SearchTerm,
    GeoPerformance,
    AudiencePerformance,
    DevicePerformance,
    HourlyPerformance,
    Extension,
)
from .metrics import Metrics, MetricsTrend
from .recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
)
from .analysis import (
    LearningStatus,
    DataSufficiency,
    TrendAnalysis,
    TrendDirection,
    Anomaly,
)
from .changes import ChangeEvent, ChangeType

__all__ = [
    "Campaign",
    "AdGroup",
    "Keyword",
    "Ad",
    "SearchTerm",
    "GeoPerformance",
    "AudiencePerformance",
    "DevicePerformance",
    "HourlyPerformance",
    "Extension",
    "Metrics",
    "MetricsTrend",
    "Recommendation",
    "RecommendationCategory",
    "RiskLevel",
    "RolloutStrategy",
    "LearningStatus",
    "DataSufficiency",
    "TrendAnalysis",
    "TrendDirection",
    "Anomaly",
    "ChangeEvent",
    "ChangeType",
]
