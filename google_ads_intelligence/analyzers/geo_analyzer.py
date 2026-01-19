"""Geographic performance analysis module."""

from typing import Optional, List, Dict, Any

from ..config import Config, DEFAULT_CONFIG
from ..models import GeoPerformance, Metrics
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GeoAnalyzer:
    """
    Geographic performance analysis.

    Identifies high and low performing locations for targeting adjustments.
    """

    # Minimum thresholds for geo decisions
    MIN_COST_FOR_EXCLUSION = 50
    MIN_CLICKS_FOR_EXCLUSION = 30
    MIN_CONVERSIONS_FOR_EXPANSION = 3

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def analyze_geo_performance(
        self,
        geo_data: List[GeoPerformance],
        campaign_avg_cpa: float,
    ) -> Dict[str, Any]:
        """
        Analyze geographic performance across all locations.

        Returns:
            Summary with high/low performers and recommendations
        """
        if not geo_data:
            return {"error": "No geo data available"}

        # Categorize locations
        high_performers = []
        low_performers = []
        exclusion_candidates = []
        expansion_candidates = []

        for geo in geo_data:
            if not geo.metrics or geo.metrics.cost == 0:
                continue

            analysis = self._analyze_single_geo(geo, campaign_avg_cpa)

            if analysis["performance_category"] == "high":
                high_performers.append(analysis)
                if analysis.get("is_expansion_candidate"):
                    expansion_candidates.append(analysis)

            elif analysis["performance_category"] == "low":
                low_performers.append(analysis)
                if analysis.get("is_exclusion_candidate"):
                    exclusion_candidates.append(analysis)

        # Sort by impact
        high_performers.sort(key=lambda x: x["metrics"]["conversions"], reverse=True)
        low_performers.sort(key=lambda x: x["metrics"]["cost"], reverse=True)

        return {
            "total_locations": len(geo_data),
            "campaign_avg_cpa": campaign_avg_cpa,
            "high_performers": high_performers,
            "low_performers": low_performers,
            "exclusion_candidates": exclusion_candidates,
            "expansion_candidates": expansion_candidates,
            "summary": {
                "high_performer_count": len(high_performers),
                "low_performer_count": len(low_performers),
                "potential_savings": sum(l["metrics"]["cost"] for l in exclusion_candidates),
            },
        }

    def recommend_geo_actions(
        self,
        geo_analysis: Dict[str, Any],
    ) -> List[Recommendation]:
        """
        Generate geo-targeting recommendations.

        Returns:
            List of geo recommendations
        """
        recommendations = []

        # Exclusion recommendations
        for candidate in geo_analysis.get("exclusion_candidates", [])[:5]:
            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.GEO,
                action=f"Exclude location '{candidate['location_name']}' from targeting",
                entity_type="campaign",
                entity_id=candidate["campaign_id"],
                entity_name=f"Campaign targeting {candidate['location_name']}",
                confidence=candidate.get("confidence", 0.7),
                risk_level=RiskLevel.MEDIUM,
                expected_impact=ExpectedImpact(
                    metric="cost",
                    current_value=candidate["metrics"]["cost"],
                    expected_value=0,
                    change_percent=-100,
                    confidence_interval_low=-100,
                    confidence_interval_high=-100,
                ),
                downside_scenario="May miss occasional conversions from this location",
                rollout_strategy=RolloutStrategy.IMMEDIATE,
                rollback_trigger="If overall campaign performance drops",
                rationale=candidate.get("reason", "Poor performance vs campaign average"),
                evidence=[
                    {"metric": "cpa", "value": candidate["metrics"].get("cpa")},
                    {"metric": "cost", "value": candidate["metrics"]["cost"]},
                    {"metric": "conversions", "value": candidate["metrics"]["conversions"]},
                ],
                assumptions=[
                    "Poor performance is location-specific, not temporary",
                    "Excluding won't significantly reduce reach",
                ],
                api_operations=[{
                    "operation": "add_geo_exclusion",
                    "campaign_id": candidate["campaign_id"],
                    "location_id": candidate["location_id"],
                }],
            )
            recommendations.append(rec)

        # Bid modifier recommendations for high performers
        for candidate in geo_analysis.get("expansion_candidates", [])[:5]:
            if not candidate.get("recommended_bid_modifier"):
                continue

            modifier = candidate["recommended_bid_modifier"]
            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.GEO,
                action=f"Increase bid modifier for '{candidate['location_name']}' by +{modifier:.0f}%",
                entity_type="campaign",
                entity_id=candidate["campaign_id"],
                entity_name=f"Campaign targeting {candidate['location_name']}",
                confidence=0.75,
                risk_level=RiskLevel.LOW,
                expected_impact=ExpectedImpact(
                    metric="conversions",
                    current_value=candidate["metrics"]["conversions"],
                    expected_value=candidate["metrics"]["conversions"] * (1 + modifier / 200),
                    change_percent=modifier / 2,
                    confidence_interval_low=modifier / 4,
                    confidence_interval_high=modifier,
                ),
                downside_scenario="May slightly increase CPA as we capture more traffic",
                rollout_strategy=RolloutStrategy.IMMEDIATE,
                rollback_trigger="If location CPA increases >20%",
                rationale=f"Location has strong CPA ${candidate['metrics'].get('cpa', 0):.2f} vs campaign average",
                evidence=[
                    {"metric": "cpa", "value": candidate["metrics"].get("cpa")},
                    {"metric": "conversions", "value": candidate["metrics"]["conversions"]},
                ],
                assumptions=[
                    "Strong performance will continue at higher volume",
                    "Additional traffic quality will be similar",
                ],
                api_operations=[{
                    "operation": "set_geo_bid_modifier",
                    "campaign_id": candidate["campaign_id"],
                    "location_id": candidate["location_id"],
                    "bid_modifier": 1 + modifier / 100,
                }],
            )
            recommendations.append(rec)

        return recommendations

    def _analyze_single_geo(
        self,
        geo: GeoPerformance,
        campaign_avg_cpa: float,
    ) -> Dict[str, Any]:
        """Analyze a single geo location."""
        metrics = geo.metrics

        analysis = {
            "location_id": geo.location_id,
            "location_name": geo.location_name,
            "location_type": geo.location_type,
            "campaign_id": geo.campaign_id,
            "metrics": {
                "impressions": metrics.impressions,
                "clicks": metrics.clicks,
                "cost": metrics.cost,
                "conversions": metrics.conversions,
                "cpa": metrics.cpa,
                "conversion_rate": metrics.conversion_rate,
            },
            "performance_category": "average",
            "is_exclusion_candidate": False,
            "is_expansion_candidate": False,
        }

        if campaign_avg_cpa > 0 and metrics.cpa:
            performance_ratio = metrics.cpa / campaign_avg_cpa

            # High performer: CPA is 30%+ better than average
            if performance_ratio < 0.7 and metrics.conversions >= self.MIN_CONVERSIONS_FOR_EXPANSION:
                analysis["performance_category"] = "high"
                analysis["is_expansion_candidate"] = True
                analysis["recommended_bid_modifier"] = min(30, (1 - performance_ratio) * 50)
                analysis["reason"] = f"CPA ${metrics.cpa:.2f} is {(1-performance_ratio)*100:.0f}% better than average"

            # Low performer: CPA is 2x+ worse than average
            elif performance_ratio > 2.0:
                analysis["performance_category"] = "low"

                # Only recommend exclusion with sufficient data
                if metrics.cost >= self.MIN_COST_FOR_EXCLUSION and metrics.clicks >= self.MIN_CLICKS_FOR_EXCLUSION:
                    analysis["is_exclusion_candidate"] = True
                    analysis["confidence"] = self._calculate_exclusion_confidence(metrics, performance_ratio)
                    analysis["reason"] = f"CPA ${metrics.cpa:.2f} is {performance_ratio:.1f}x the campaign average"

        # Zero conversions with significant spend
        elif metrics.conversions == 0 and metrics.cost >= self.MIN_COST_FOR_EXCLUSION:
            analysis["performance_category"] = "low"
            analysis["is_exclusion_candidate"] = True
            analysis["confidence"] = 0.8
            analysis["reason"] = f"Zero conversions with ${metrics.cost:.2f} spend"

        return analysis

    def _calculate_exclusion_confidence(
        self,
        metrics: Metrics,
        performance_ratio: float,
    ) -> float:
        """Calculate confidence for exclusion recommendation."""
        confidence = 0.5

        # More data = higher confidence
        if metrics.clicks >= 50:
            confidence += 0.1
        if metrics.clicks >= 100:
            confidence += 0.1

        # Worse performance = higher confidence
        if performance_ratio > 3:
            confidence += 0.15
        elif performance_ratio > 2.5:
            confidence += 0.1

        # Higher spend = higher confidence
        if metrics.cost >= 100:
            confidence += 0.1

        return min(0.9, confidence)
