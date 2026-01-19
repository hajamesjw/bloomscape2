"""Audience performance analysis module."""

from typing import Optional, List, Dict, Any

from ..config import Config, DEFAULT_CONFIG
from ..models import AudiencePerformance, Metrics
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AudienceAnalyzer:
    """
    Audience segment performance analysis.

    Key insight: Audiences often have 2-3x performance variance.
    RLSA visitors typically convert much better than cold traffic.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def analyze_audience_performance(
        self,
        audiences: List[AudiencePerformance],
        baseline_cpa: float,
    ) -> Dict[str, Any]:
        """
        Analyze performance across all audience segments.

        Returns:
            Summary with high/low performers and recommendations
        """
        if not audiences:
            return {"error": "No audience data available"}

        # Categorize by performance
        high_performers = []
        low_performers = []
        bid_increase_candidates = []
        bid_decrease_candidates = []

        for audience in audiences:
            if not audience.metrics or audience.metrics.cost == 0:
                continue

            analysis = self._analyze_single_audience(audience, baseline_cpa)

            if analysis["performance_category"] == "high":
                high_performers.append(analysis)
                if analysis.get("recommended_action") == "increase_bid":
                    bid_increase_candidates.append(analysis)

            elif analysis["performance_category"] == "low":
                low_performers.append(analysis)
                if analysis.get("recommended_action") == "decrease_bid":
                    bid_decrease_candidates.append(analysis)

        # Group by audience type
        by_type = {}
        for audience in audiences:
            if audience.audience_type not in by_type:
                by_type[audience.audience_type] = []
            by_type[audience.audience_type].append(audience)

        type_performance = {}
        for aud_type, aud_list in by_type.items():
            total_cost = sum(a.metrics.cost for a in aud_list if a.metrics)
            total_conv = sum(a.metrics.conversions for a in aud_list if a.metrics)
            type_cpa = total_cost / total_conv if total_conv > 0 else 0
            type_performance[aud_type] = {
                "count": len(aud_list),
                "total_cost": total_cost,
                "total_conversions": total_conv,
                "avg_cpa": type_cpa,
                "vs_baseline": ((baseline_cpa - type_cpa) / baseline_cpa * 100) if baseline_cpa > 0 and type_cpa > 0 else 0,
            }

        return {
            "total_audiences": len(audiences),
            "baseline_cpa": baseline_cpa,
            "high_performers": high_performers,
            "low_performers": low_performers,
            "bid_increase_candidates": bid_increase_candidates,
            "bid_decrease_candidates": bid_decrease_candidates,
            "performance_by_type": type_performance,
            "summary": {
                "best_type": max(type_performance.items(), key=lambda x: x[1]["vs_baseline"])[0] if type_performance else None,
                "worst_type": min(type_performance.items(), key=lambda x: x[1]["vs_baseline"])[0] if type_performance else None,
            },
        }

    def recommend_audience_actions(
        self,
        audience_analysis: Dict[str, Any],
    ) -> List[Recommendation]:
        """
        Generate audience targeting recommendations.

        Returns:
            List of audience recommendations
        """
        recommendations = []

        # Bid increase recommendations
        for candidate in audience_analysis.get("bid_increase_candidates", [])[:5]:
            modifier = candidate.get("recommended_bid_modifier", 20)

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.AUDIENCE,
                action=f"Increase bid modifier for audience '{candidate['audience_name']}' by +{modifier:.0f}%",
                entity_type="audience",
                entity_id=candidate["audience_id"],
                entity_name=candidate["audience_name"],
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
                downside_scenario="May slightly increase CPA as we capture more audience traffic",
                rollout_strategy=RolloutStrategy.IMMEDIATE,
                rollback_trigger="If audience CPA increases >20%",
                rationale=candidate.get("reason", "Strong performance vs baseline"),
                evidence=[
                    {"metric": "cpa", "value": candidate["metrics"].get("cpa")},
                    {"metric": "conversions", "value": candidate["metrics"]["conversions"]},
                    {"metric": "performance_vs_baseline", "value": candidate.get("performance_vs_baseline")},
                ],
                assumptions=[
                    "Strong performance will continue at higher volume",
                    "Audience segment is correctly targeted",
                ],
                api_operations=[{
                    "operation": "set_audience_bid_modifier",
                    "audience_id": candidate["audience_id"],
                    "campaign_id": candidate.get("campaign_id"),
                    "bid_modifier": 1 + modifier / 100,
                }],
            )
            recommendations.append(rec)

        # Bid decrease recommendations
        for candidate in audience_analysis.get("bid_decrease_candidates", [])[:5]:
            modifier = candidate.get("recommended_bid_modifier", -20)

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.AUDIENCE,
                action=f"Decrease bid modifier for audience '{candidate['audience_name']}' by {modifier:.0f}%",
                entity_type="audience",
                entity_id=candidate["audience_id"],
                entity_name=candidate["audience_name"],
                confidence=0.65,
                risk_level=RiskLevel.MEDIUM,
                expected_impact=ExpectedImpact(
                    metric="cpa",
                    current_value=candidate["metrics"].get("cpa", 0),
                    expected_value=candidate["metrics"].get("cpa", 0) * (1 + modifier / 100),
                    change_percent=modifier,
                    confidence_interval_low=modifier * 1.5,
                    confidence_interval_high=modifier * 0.5,
                ),
                downside_scenario="May lose some conversions from this audience",
                rollout_strategy=RolloutStrategy.GRADUAL,
                rollback_trigger="If conversion volume drops significantly",
                rationale=candidate.get("reason", "Poor performance vs baseline"),
                evidence=[
                    {"metric": "cpa", "value": candidate["metrics"].get("cpa")},
                    {"metric": "conversions", "value": candidate["metrics"]["conversions"]},
                ],
                assumptions=[
                    "Poor performance is segment-specific",
                    "Reducing bids will improve efficiency",
                ],
                api_operations=[{
                    "operation": "set_audience_bid_modifier",
                    "audience_id": candidate["audience_id"],
                    "campaign_id": candidate.get("campaign_id"),
                    "bid_modifier": 1 + modifier / 100,
                }],
            )
            recommendations.append(rec)

        return recommendations

    def _analyze_single_audience(
        self,
        audience: AudiencePerformance,
        baseline_cpa: float,
    ) -> Dict[str, Any]:
        """Analyze a single audience segment."""
        metrics = audience.metrics

        analysis = {
            "audience_id": audience.audience_id,
            "audience_name": audience.audience_name,
            "audience_type": audience.audience_type,
            "campaign_id": audience.campaign_id,
            "ad_group_id": audience.ad_group_id,
            "metrics": {
                "impressions": metrics.impressions,
                "clicks": metrics.clicks,
                "cost": metrics.cost,
                "conversions": metrics.conversions,
                "cpa": metrics.cpa,
                "conversion_rate": metrics.conversion_rate,
            },
            "performance_category": "average",
            "performance_vs_baseline": 0,
            "recommended_action": None,
            "recommended_bid_modifier": None,
        }

        if baseline_cpa > 0 and metrics.cpa:
            performance_vs_baseline = ((baseline_cpa - metrics.cpa) / baseline_cpa) * 100
            analysis["performance_vs_baseline"] = performance_vs_baseline

            # High performer: CPA is 20%+ better than baseline
            if performance_vs_baseline > 20 and metrics.conversions >= 3:
                analysis["performance_category"] = "high"
                analysis["recommended_action"] = "increase_bid"
                analysis["recommended_bid_modifier"] = min(50, performance_vs_baseline)
                analysis["reason"] = f"CPA ${metrics.cpa:.2f} is {performance_vs_baseline:.0f}% better than baseline ${baseline_cpa:.2f}"

            # Low performer: CPA is 30%+ worse than baseline
            elif performance_vs_baseline < -30 and metrics.cost >= 50:
                analysis["performance_category"] = "low"
                analysis["recommended_action"] = "decrease_bid"
                analysis["recommended_bid_modifier"] = max(-50, performance_vs_baseline)
                analysis["reason"] = f"CPA ${metrics.cpa:.2f} is {abs(performance_vs_baseline):.0f}% worse than baseline ${baseline_cpa:.2f}"

        return analysis
