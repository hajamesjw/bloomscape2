"""Keyword and search term analysis module."""

from typing import Optional, List, Dict, Any
from datetime import date

from ..config import Config, DEFAULT_CONFIG
from ..models import Keyword, SearchTerm, Metrics
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class KeywordAnalyzer:
    """
    Keyword and search term intelligence.

    Key principle: NEVER recommend pausing keywords with < 100 clicks.
    """

    # Minimum thresholds for keyword decisions
    MIN_CLICKS_FOR_PAUSE = 100
    MIN_DAYS_FOR_PAUSE = 30
    MIN_COST_FOR_NEGATIVE = 50
    MIN_CLICKS_FOR_NEGATIVE = 20

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def analyze_keyword_health(
        self,
        keyword: Keyword,
        campaign_avg_cpa: float,
    ) -> Dict[str, Any]:
        """
        Analyze health of a single keyword.

        Returns:
            Health assessment with recommendations
        """
        if not keyword.metrics:
            return {
                "status": "insufficient_data",
                "health_score": 0,
                "recommendations": [],
            }

        metrics = keyword.metrics
        health_issues = []
        health_score = 100

        # Quality Score analysis
        if keyword.quality_score:
            if keyword.quality_score < 5:
                health_issues.append({
                    "issue": "low_quality_score",
                    "severity": "high",
                    "value": keyword.quality_score,
                    "suggestion": "Review ad relevance and landing page experience",
                })
                health_score -= 30
            elif keyword.quality_score < 7:
                health_issues.append({
                    "issue": "moderate_quality_score",
                    "severity": "medium",
                    "value": keyword.quality_score,
                })
                health_score -= 15

        # CPA analysis
        if metrics.cpa and campaign_avg_cpa > 0:
            cpa_ratio = metrics.cpa / campaign_avg_cpa

            if cpa_ratio > 2.0 and metrics.clicks >= self.MIN_CLICKS_FOR_PAUSE:
                health_issues.append({
                    "issue": "high_cpa",
                    "severity": "high",
                    "value": metrics.cpa,
                    "benchmark": campaign_avg_cpa,
                    "ratio": cpa_ratio,
                })
                health_score -= 25

            elif cpa_ratio > 1.5:
                health_issues.append({
                    "issue": "elevated_cpa",
                    "severity": "medium",
                    "value": metrics.cpa,
                })
                health_score -= 10

        # Conversion rate analysis
        if metrics.conversion_rate < 1.0 and metrics.clicks >= 50:
            health_issues.append({
                "issue": "low_conversion_rate",
                "severity": "medium",
                "value": metrics.conversion_rate,
            })
            health_score -= 15

        # Zero conversions with significant spend
        if metrics.conversions == 0 and metrics.cost >= 100 and metrics.clicks >= self.MIN_CLICKS_FOR_PAUSE:
            health_issues.append({
                "issue": "no_conversions",
                "severity": "high",
                "cost": metrics.cost,
                "clicks": metrics.clicks,
            })
            health_score -= 35

        return {
            "keyword_id": keyword.id,
            "keyword_text": keyword.text,
            "match_type": keyword.match_type.value,
            "status": self._get_health_status(health_score),
            "health_score": max(0, health_score),
            "issues": health_issues,
            "data_confidence": self._calculate_data_confidence(metrics),
        }

    def analyze_all_keywords(
        self,
        keywords: List[Keyword],
    ) -> Dict[str, Any]:
        """
        Analyze all keywords and identify issues.

        Returns:
            Summary with categorized keywords
        """
        # Calculate account average CPA
        total_cost = sum(k.metrics.cost for k in keywords if k.metrics)
        total_conv = sum(k.metrics.conversions for k in keywords if k.metrics)
        avg_cpa = total_cost / total_conv if total_conv > 0 else 0

        healthy = []
        needs_attention = []
        underperforming = []
        insufficient_data = []

        for keyword in keywords:
            health = self.analyze_keyword_health(keyword, avg_cpa)

            if health["status"] == "insufficient_data":
                insufficient_data.append(health)
            elif health["health_score"] >= 80:
                healthy.append(health)
            elif health["health_score"] >= 50:
                needs_attention.append(health)
            else:
                underperforming.append(health)

        return {
            "total_keywords": len(keywords),
            "account_avg_cpa": avg_cpa,
            "healthy": len(healthy),
            "needs_attention": len(needs_attention),
            "underperforming": len(underperforming),
            "insufficient_data": len(insufficient_data),
            "details": {
                "underperforming": underperforming,
                "needs_attention": needs_attention,
            },
        }

    def find_negative_keyword_candidates(
        self,
        search_terms: List[SearchTerm],
        campaign_avg_cpa: float,
    ) -> List[Dict[str, Any]]:
        """
        Find search terms that should be added as negatives.

        Criteria:
        - Minimum spend: $50
        - Minimum clicks: 20
        - Zero or very few conversions (or CPA > 3x target)
        """
        candidates = []

        for term in search_terms:
            if not term.metrics:
                continue

            metrics = term.metrics

            # Check minimum thresholds
            if metrics.cost < self.MIN_COST_FOR_NEGATIVE:
                continue
            if metrics.clicks < self.MIN_CLICKS_FOR_NEGATIVE:
                continue

            # Check performance
            is_negative_candidate = False
            reason = ""

            if metrics.conversions == 0:
                is_negative_candidate = True
                reason = f"Zero conversions with ${metrics.cost:.2f} spend"

            elif metrics.cpa and campaign_avg_cpa > 0 and metrics.cpa > campaign_avg_cpa * 3:
                is_negative_candidate = True
                reason = f"CPA ${metrics.cpa:.2f} is 3x+ above target ${campaign_avg_cpa:.2f}"

            if is_negative_candidate:
                candidates.append({
                    "query": term.query,
                    "keyword_text": term.keyword_text,
                    "campaign_id": term.campaign_id,
                    "ad_group_id": term.ad_group_id,
                    "cost": metrics.cost,
                    "clicks": metrics.clicks,
                    "conversions": metrics.conversions,
                    "cpa": metrics.cpa,
                    "reason": reason,
                    "confidence": self._calculate_negative_confidence(metrics, campaign_avg_cpa),
                })

        # Sort by cost (highest wasted spend first)
        candidates.sort(key=lambda x: x["cost"], reverse=True)

        return candidates

    def find_promotion_candidates(
        self,
        search_terms: List[SearchTerm],
        campaign_avg_cpa: float,
    ) -> List[Dict[str, Any]]:
        """
        Find high-performing search terms that could be promoted to exact match.

        Criteria:
        - Minimum conversions: 3
        - CPA at or below campaign average
        - Not already an exact match keyword
        """
        candidates = []

        for term in search_terms:
            if not term.metrics:
                continue

            metrics = term.metrics

            # Check minimum performance
            if metrics.conversions < 3:
                continue

            # Check CPA
            if metrics.cpa and campaign_avg_cpa > 0:
                if metrics.cpa <= campaign_avg_cpa:
                    candidates.append({
                        "query": term.query,
                        "source_keyword": term.keyword_text,
                        "campaign_id": term.campaign_id,
                        "ad_group_id": term.ad_group_id,
                        "conversions": metrics.conversions,
                        "cpa": metrics.cpa,
                        "cost": metrics.cost,
                        "improvement_vs_avg": ((campaign_avg_cpa - metrics.cpa) / campaign_avg_cpa * 100) if campaign_avg_cpa > 0 else 0,
                        "reason": f"Strong CPA ${metrics.cpa:.2f} vs average ${campaign_avg_cpa:.2f}",
                    })

        # Sort by conversions (highest first)
        candidates.sort(key=lambda x: x["conversions"], reverse=True)

        return candidates

    def recommend_keyword_actions(
        self,
        keywords: List[Keyword],
        search_terms: List[SearchTerm],
    ) -> List[Recommendation]:
        """
        Generate keyword recommendations.

        Returns:
            List of keyword-related recommendations
        """
        recommendations = []

        # Calculate account average CPA
        total_cost = sum(k.metrics.cost for k in keywords if k.metrics)
        total_conv = sum(k.metrics.conversions for k in keywords if k.metrics)
        avg_cpa = total_cost / total_conv if total_conv > 0 else 0

        # Negative keyword recommendations
        negative_candidates = self.find_negative_keyword_candidates(search_terms, avg_cpa)

        for candidate in negative_candidates[:10]:  # Top 10
            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.SEARCH_TERM,
                action=f"Add '{candidate['query']}' as negative keyword",
                entity_type="campaign",
                entity_id=candidate["campaign_id"],
                entity_name=candidate["campaign_id"],
                confidence=candidate["confidence"],
                risk_level=RiskLevel.LOW,
                expected_impact=ExpectedImpact(
                    metric="cost",
                    current_value=candidate["cost"],
                    expected_value=0,
                    change_percent=-100,
                    confidence_interval_low=-100,
                    confidence_interval_high=-100,
                ),
                downside_scenario="May block a small amount of relevant traffic with similar queries",
                rollout_strategy=RolloutStrategy.IMMEDIATE,
                rollback_trigger="If impression volume drops significantly",
                rationale=candidate["reason"],
                evidence=[
                    {"metric": "cost", "value": candidate["cost"]},
                    {"metric": "conversions", "value": candidate["conversions"]},
                ],
                assumptions=["Query is consistently irrelevant", "Similar queries won't be blocked"],
                api_operations=[{
                    "operation": "add_negative_keyword",
                    "campaign_id": candidate["campaign_id"],
                    "keyword_text": candidate["query"],
                    "match_type": "EXACT",
                }],
            )
            recommendations.append(rec)

        # Keyword pause recommendations (with strict safeguards)
        keyword_analysis = self.analyze_all_keywords(keywords)

        for kw_health in keyword_analysis["details"]["underperforming"]:
            # Find the keyword
            keyword = next((k for k in keywords if k.id == kw_health["keyword_id"]), None)
            if not keyword or not keyword.metrics:
                continue

            # CRITICAL: Never pause with insufficient data
            if keyword.metrics.clicks < self.MIN_CLICKS_FOR_PAUSE:
                continue

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.KEYWORD,
                action=f"Consider pausing keyword '{keyword.text}'",
                entity_type="keyword",
                entity_id=keyword.id,
                entity_name=keyword.text,
                confidence=0.6,  # Lower confidence for pausing
                risk_level=RiskLevel.MEDIUM,
                expected_impact=ExpectedImpact(
                    metric="cost",
                    current_value=keyword.metrics.cost,
                    expected_value=0,
                    change_percent=-100,
                    confidence_interval_low=-100,
                    confidence_interval_high=-100,
                ),
                downside_scenario="May lose some converting traffic; keyword may perform better seasonally",
                rollout_strategy=RolloutStrategy.MANUAL_REVIEW,
                rollback_trigger="Re-enable if needed for coverage",
                rationale=f"Health score {kw_health['health_score']}/100 with {len(kw_health['issues'])} issues",
                evidence=kw_health["issues"],
                assumptions=[
                    "Poor performance is structural, not temporary",
                    "Traffic can be captured by other keywords",
                ],
                api_operations=[{
                    "operation": "pause_keyword",
                    "keyword_id": keyword.id,
                }],
            )
            recommendations.append(rec)

        return recommendations

    def _get_health_status(self, score: int) -> str:
        """Get health status from score."""
        if score >= 80:
            return "healthy"
        elif score >= 50:
            return "needs_attention"
        elif score > 0:
            return "underperforming"
        else:
            return "critical"

    def _calculate_data_confidence(self, metrics: Metrics) -> str:
        """Calculate confidence level based on data volume."""
        if metrics.clicks >= 200 and metrics.conversions >= 10:
            return "high"
        elif metrics.clicks >= 100 and metrics.conversions >= 5:
            return "medium"
        elif metrics.clicks >= 50:
            return "low"
        else:
            return "insufficient"

    def _calculate_negative_confidence(
        self,
        metrics: Metrics,
        campaign_avg_cpa: float,
    ) -> float:
        """Calculate confidence for negative keyword recommendation."""
        confidence = 0.5

        # More data = higher confidence
        if metrics.clicks >= 50:
            confidence += 0.15
        if metrics.clicks >= 100:
            confidence += 0.1

        # Zero conversions = higher confidence
        if metrics.conversions == 0:
            confidence += 0.15

        # Higher spend = higher confidence
        if metrics.cost >= 100:
            confidence += 0.1

        return min(0.95, confidence)
