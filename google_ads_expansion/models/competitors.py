"""Competitor intelligence data models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date


@dataclass
class Competitor:
    """A competitor identified in auction insights."""

    domain: str
    display_name: str = ""

    # Auction metrics (from Google Ads Auction Insights)
    impression_share: float = 0.0
    overlap_rate: float = 0.0
    position_above_rate: float = 0.0
    top_of_page_rate: float = 0.0
    outranking_share: float = 0.0

    # Trends
    impression_share_trend: str = "stable"  # increasing, decreasing, stable
    impression_share_7d_change: float = 0.0
    impression_share_30d_change: float = 0.0

    # Classification
    is_new: bool = False  # First seen in last 30 days
    threat_level: str = "medium"  # low, medium, high

    # Estimated data (inferred)
    estimated_monthly_spend: Optional[float] = None
    estimated_keywords_targeting: Optional[int] = None

    def calculate_threat_level(self) -> str:
        """Calculate threat level based on metrics."""
        score = 0

        # High impression share = threat
        if self.impression_share > 50:
            score += 3
        elif self.impression_share > 30:
            score += 2
        elif self.impression_share > 15:
            score += 1

        # Frequently above us = threat
        if self.position_above_rate > 50:
            score += 2
        elif self.position_above_rate > 30:
            score += 1

        # Growing = threat
        if self.impression_share_30d_change > 20:
            score += 2
        elif self.impression_share_30d_change > 10:
            score += 1

        # New competitor = watch closely
        if self.is_new:
            score += 1

        if score >= 5:
            self.threat_level = "high"
        elif score >= 3:
            self.threat_level = "medium"
        else:
            self.threat_level = "low"

        return self.threat_level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "display_name": self.display_name or self.domain,
            "metrics": {
                "impression_share": f"{self.impression_share:.1f}%",
                "overlap_rate": f"{self.overlap_rate:.1f}%",
                "position_above_rate": f"{self.position_above_rate:.1f}%",
                "top_of_page_rate": f"{self.top_of_page_rate:.1f}%",
                "outranking_share": f"{self.outranking_share:.1f}%",
            },
            "trends": {
                "direction": self.impression_share_trend,
                "7d_change": f"{self.impression_share_7d_change:+.1f}%",
                "30d_change": f"{self.impression_share_30d_change:+.1f}%",
            },
            "is_new": self.is_new,
            "threat_level": self.threat_level,
        }


@dataclass
class CompetitiveGap:
    """A gap or opportunity identified from competitor analysis."""

    gap_type: str  # "keyword", "audience", "geo", "schedule", "message"
    description: str

    # Opportunity details
    opportunity_size: str = "medium"  # small, medium, large
    confidence: float = 0.0

    # Specific recommendations
    recommended_action: str = ""
    expected_impact: str = ""

    # Evidence
    supporting_data: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_type": self.gap_type,
            "description": self.description,
            "opportunity_size": self.opportunity_size,
            "confidence": f"{self.confidence:.0%}",
            "recommended_action": self.recommended_action,
            "expected_impact": self.expected_impact,
            "supporting_data": self.supporting_data,
        }


@dataclass
class CompetitorInsight:
    """Complete competitor analysis insight."""

    generated_at: str
    analysis_period_days: int = 30

    # Our metrics
    our_impression_share: float = 0.0
    our_top_of_page_rate: float = 0.0
    our_outranking_share: float = 0.0

    # Competitors
    competitors: List[Competitor] = field(default_factory=list)

    # Alerts
    new_competitors: List[Competitor] = field(default_factory=list)
    aggressive_competitors: List[Competitor] = field(default_factory=list)

    # Gaps and opportunities
    competitive_gaps: List[CompetitiveGap] = field(default_factory=list)

    # Recommendations
    defensive_actions: List[str] = field(default_factory=list)
    offensive_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "analysis_period_days": self.analysis_period_days,
            "our_position": {
                "impression_share": f"{self.our_impression_share:.1f}%",
                "top_of_page_rate": f"{self.our_top_of_page_rate:.1f}%",
                "outranking_share": f"{self.our_outranking_share:.1f}%",
            },
            "competitor_count": len(self.competitors),
            "competitors": [c.to_dict() for c in self.competitors],
            "alerts": {
                "new_competitors": [c.to_dict() for c in self.new_competitors],
                "aggressive_competitors": [c.to_dict() for c in self.aggressive_competitors],
            },
            "competitive_gaps": [g.to_dict() for g in self.competitive_gaps],
            "recommendations": {
                "defensive": self.defensive_actions,
                "offensive": self.offensive_actions,
            },
        }
