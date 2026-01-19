"""Metrics data models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Any
from enum import Enum


@dataclass
class Metrics:
    """Core performance metrics for any entity."""

    date: date
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: float = 0.0
    conversion_value: float = 0.0

    # Calculated metrics
    ctr: float = 0.0
    cpc: float = 0.0
    conversion_rate: float = 0.0
    cpa: float = 0.0
    roas: float = 0.0

    # Impression share metrics
    impression_share: Optional[float] = None
    impression_share_lost_budget: Optional[float] = None
    impression_share_lost_rank: Optional[float] = None
    search_impression_share: Optional[float] = None

    # Quality metrics
    quality_score: Optional[int] = None
    expected_ctr: Optional[str] = None
    ad_relevance: Optional[str] = None
    landing_page_experience: Optional[str] = None

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100

        if self.clicks > 0:
            self.cpc = self.cost / self.clicks
            self.conversion_rate = (self.conversions / self.clicks) * 100

        if self.conversions > 0:
            self.cpa = self.cost / self.conversions

        if self.cost > 0:
            self.roas = self.conversion_value / self.cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date.isoformat(),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "cost": self.cost,
            "conversions": self.conversions,
            "conversion_value": self.conversion_value,
            "ctr": round(self.ctr, 2),
            "cpc": round(self.cpc, 2),
            "conversion_rate": round(self.conversion_rate, 2),
            "cpa": round(self.cpa, 2) if self.cpa else None,
            "roas": round(self.roas, 2) if self.roas else None,
            "impression_share": self.impression_share,
            "impression_share_lost_budget": self.impression_share_lost_budget,
            "impression_share_lost_rank": self.impression_share_lost_rank,
            "quality_score": self.quality_score,
        }


@dataclass
class MetricsTrend:
    """Trend data for a metric over multiple time windows."""

    metric_name: str
    current_value: float
    values_by_window: Dict[int, float] = field(default_factory=dict)  # days -> value
    percent_changes: Dict[int, float] = field(default_factory=dict)  # days -> % change
    trend_direction: str = "stable"  # improving, declining, stable, volatile
    confidence: float = 0.0

    def calculate_trend(self):
        """Calculate trend direction based on values."""
        if len(self.values_by_window) < 2:
            self.trend_direction = "stable"
            self.confidence = 0.0
            return

        windows = sorted(self.values_by_window.keys())
        values = [self.values_by_window[w] for w in windows]

        # Calculate percent changes
        for i, window in enumerate(windows[1:], 1):
            prev_window = windows[i - 1]
            prev_value = self.values_by_window[prev_window]
            curr_value = self.values_by_window[window]

            if prev_value != 0:
                pct_change = ((curr_value - prev_value) / prev_value) * 100
                self.percent_changes[window] = pct_change

        # Determine trend
        if len(self.percent_changes) >= 2:
            changes = list(self.percent_changes.values())
            avg_change = sum(changes) / len(changes)
            variance = sum((c - avg_change) ** 2 for c in changes) / len(changes)

            if variance > 400:  # High variance = volatile
                self.trend_direction = "volatile"
                self.confidence = 0.5
            elif avg_change > 5:
                self.trend_direction = "improving"
                self.confidence = min(0.9, 0.5 + (avg_change / 20))
            elif avg_change < -5:
                self.trend_direction = "declining"
                self.confidence = min(0.9, 0.5 + (abs(avg_change) / 20))
            else:
                self.trend_direction = "stable"
                self.confidence = 0.7
