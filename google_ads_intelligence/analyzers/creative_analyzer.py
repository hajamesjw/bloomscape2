"""Creative and ad performance analysis module."""

from typing import Optional, List, Dict, Any
from datetime import date

from ..config import Config, DEFAULT_CONFIG
from ..models import Ad, Metrics
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CreativeAnalyzer:
    """
    Creative/Ad performance analysis.

    Key principle: Avoid excessive ad refreshes that reset learning.
    Minimum 14 days performance data before making creative decisions.
    """

    MIN_IMPRESSIONS_FOR_JUDGMENT = 5000
    MIN_DAYS_FOR_CREATIVE_CHANGE = 14
    FATIGUE_CTR_DECLINE_THRESHOLD = 20  # 20% decline

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def analyze_ad_performance(
        self,
        ads: List[Ad],
        ad_group_avg_ctr: float,
        ad_group_avg_conversion_rate: float,
    ) -> Dict[str, Any]:
        """
        Analyze performance across all ads.

        Returns:
            Summary with top/bottom performers and recommendations
        """
        if not ads:
            return {"error": "No ad data available"}

        analyzed_ads = []
        top_performers = []
        bottom_performers = []
        insufficient_data = []

        for ad in ads:
            analysis = self._analyze_single_ad(
                ad, ad_group_avg_ctr, ad_group_avg_conversion_rate
            )
            analyzed_ads.append(analysis)

            if analysis["data_status"] == "insufficient":
                insufficient_data.append(analysis)
            elif analysis["performance_category"] == "top":
                top_performers.append(analysis)
            elif analysis["performance_category"] == "bottom":
                bottom_performers.append(analysis)

        return {
            "total_ads": len(ads),
            "ad_group_avg_ctr": ad_group_avg_ctr,
            "ad_group_avg_conversion_rate": ad_group_avg_conversion_rate,
            "top_performers": top_performers,
            "bottom_performers": bottom_performers,
            "insufficient_data": insufficient_data,
            "summary": {
                "analyzable_ads": len(ads) - len(insufficient_data),
                "top_count": len(top_performers),
                "bottom_count": len(bottom_performers),
            },
        }

    def detect_creative_fatigue(
        self,
        ad: Ad,
    ) -> Dict[str, Any]:
        """
        Detect if an ad is showing signs of creative fatigue.

        Signs of fatigue:
        - CTR declining over 3+ weeks
        - Same ad, declining engagement
        """
        if not ad.metrics_history or len(ad.metrics_history) < 21:
            return {
                "is_fatigued": False,
                "confidence": 0,
                "reason": "Insufficient data for fatigue detection",
            }

        metrics = ad.metrics_history
        today = date.today()

        # Get weekly CTR averages
        week1 = [m for m in metrics if 0 <= (today - m.date).days < 7]
        week2 = [m for m in metrics if 7 <= (today - m.date).days < 14]
        week3 = [m for m in metrics if 14 <= (today - m.date).days < 21]

        if not all([week1, week2, week3]):
            return {
                "is_fatigued": False,
                "confidence": 0,
                "reason": "Insufficient weekly data",
            }

        ctr_week1 = sum(m.ctr for m in week1) / len(week1)
        ctr_week2 = sum(m.ctr for m in week2) / len(week2)
        ctr_week3 = sum(m.ctr for m in week3) / len(week3)

        # Check for consistent decline
        decline_week1_vs_week2 = (ctr_week2 - ctr_week1) / ctr_week2 * 100 if ctr_week2 > 0 else 0
        decline_week2_vs_week3 = (ctr_week3 - ctr_week2) / ctr_week3 * 100 if ctr_week3 > 0 else 0

        # Fatigue = CTR declining each week
        if decline_week1_vs_week2 < -10 and decline_week2_vs_week3 < -10:
            total_decline = (ctr_week3 - ctr_week1) / ctr_week3 * 100 if ctr_week3 > 0 else 0

            return {
                "is_fatigued": True,
                "confidence": min(0.9, 0.5 + abs(total_decline) / 100),
                "reason": f"CTR declined {abs(total_decline):.1f}% over 3 weeks",
                "ctr_trend": {
                    "week_1": round(ctr_week1, 2),
                    "week_2": round(ctr_week2, 2),
                    "week_3": round(ctr_week3, 2),
                },
                "recommendation": "Test new ad variations",
            }

        return {
            "is_fatigued": False,
            "confidence": 0.7,
            "reason": "No consistent decline pattern detected",
        }

    def analyze_rsa_assets(
        self,
        ad: Ad,
    ) -> Dict[str, Any]:
        """
        Analyze RSA (Responsive Search Ad) asset performance.

        Returns:
            Asset analysis with recommendations
        """
        if ad.ad_type != "RESPONSIVE_SEARCH_AD":
            return {"error": "Not an RSA"}

        headlines = ad.headlines
        descriptions = ad.descriptions
        asset_performance = ad.asset_performance

        analysis = {
            "total_headlines": len(headlines),
            "total_descriptions": len(descriptions),
            "asset_ratings": {},
            "recommendations": [],
        }

        # Count asset ratings
        best_count = 0
        good_count = 0
        low_count = 0

        for asset, rating in asset_performance.items():
            if rating == "BEST":
                best_count += 1
            elif rating == "GOOD":
                good_count += 1
            elif rating == "LOW":
                low_count += 1

        analysis["asset_ratings"] = {
            "best": best_count,
            "good": good_count,
            "low": low_count,
        }

        # Generate recommendations
        if low_count > 0:
            analysis["recommendations"].append({
                "action": "Replace low-performing assets",
                "count": low_count,
                "priority": "medium",
            })

        if len(headlines) < 10:
            analysis["recommendations"].append({
                "action": f"Add {10 - len(headlines)} more headlines (have {len(headlines)}/15)",
                "priority": "low",
            })

        if len(descriptions) < 3:
            analysis["recommendations"].append({
                "action": f"Add {3 - len(descriptions)} more descriptions (have {len(descriptions)}/4)",
                "priority": "low",
            })

        return analysis

    def recommend_creative_actions(
        self,
        creative_analysis: Dict[str, Any],
        fatigued_ads: List[Dict[str, Any]],
    ) -> List[Recommendation]:
        """
        Generate creative recommendations.

        Returns:
            List of creative recommendations
        """
        recommendations = []

        # Recommendations for fatigued ads
        for fatigued in fatigued_ads:
            if not fatigued.get("is_fatigued"):
                continue

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.CREATIVE,
                action=f"Test new ad variations for fatigued ad",
                entity_type="ad",
                entity_id=fatigued.get("ad_id", ""),
                entity_name=fatigued.get("ad_name", "Fatigued Ad"),
                confidence=fatigued.get("confidence", 0.7),
                risk_level=RiskLevel.MEDIUM,
                expected_impact=ExpectedImpact(
                    metric="ctr",
                    current_value=fatigued.get("ctr_trend", {}).get("week_1", 0),
                    expected_value=fatigued.get("ctr_trend", {}).get("week_3", 0) * 1.2,
                    change_percent=20,
                    confidence_interval_low=10,
                    confidence_interval_high=30,
                ),
                downside_scenario="New ads may perform worse initially during learning",
                rollout_strategy=RolloutStrategy.TEST_FIRST,
                rollback_trigger="If new ads underperform after 14 days",
                rationale=fatigued.get("reason", "Creative fatigue detected"),
                evidence=[
                    {"metric": "ctr_trend", "value": fatigued.get("ctr_trend")},
                ],
                assumptions=[
                    "Audience has become desensitized to current messaging",
                    "Fresh creative will re-engage audience",
                ],
            )
            recommendations.append(rec)

        # Recommendations for bottom performers
        for bottom in creative_analysis.get("bottom_performers", [])[:3]:
            if bottom.get("data_status") == "insufficient":
                continue

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.CREATIVE,
                action=f"Review and potentially pause underperforming ad",
                entity_type="ad",
                entity_id=bottom.get("ad_id", ""),
                entity_name=bottom.get("ad_name", "Underperforming Ad"),
                confidence=0.6,
                risk_level=RiskLevel.LOW,
                expected_impact=ExpectedImpact(
                    metric="ctr",
                    current_value=bottom.get("metrics", {}).get("ctr", 0),
                    expected_value=bottom.get("metrics", {}).get("ctr", 0),
                    change_percent=0,
                    confidence_interval_low=0,
                    confidence_interval_high=0,
                ),
                downside_scenario="Minimal - ad is already underperforming",
                rollout_strategy=RolloutStrategy.MANUAL_REVIEW,
                rollback_trigger="N/A",
                rationale=bottom.get("reason", "Significantly below average performance"),
                evidence=[
                    {"metric": "ctr", "value": bottom.get("metrics", {}).get("ctr")},
                    {"metric": "conversion_rate", "value": bottom.get("metrics", {}).get("conversion_rate")},
                ],
                assumptions=[
                    "Poor performance is due to ad quality, not targeting",
                    "Other ads can capture the traffic",
                ],
            )
            recommendations.append(rec)

        return recommendations

    def _analyze_single_ad(
        self,
        ad: Ad,
        ad_group_avg_ctr: float,
        ad_group_avg_conversion_rate: float,
    ) -> Dict[str, Any]:
        """Analyze a single ad."""
        analysis = {
            "ad_id": ad.id,
            "ad_type": ad.ad_type,
            "headlines": ad.headlines[:3] if ad.headlines else [],
            "metrics": {},
            "data_status": "sufficient",
            "performance_category": "average",
            "reason": "",
        }

        if not ad.metrics:
            analysis["data_status"] = "insufficient"
            return analysis

        metrics = ad.metrics

        if metrics.impressions < self.MIN_IMPRESSIONS_FOR_JUDGMENT:
            analysis["data_status"] = "insufficient"
            analysis["reason"] = f"Only {metrics.impressions} impressions (need {self.MIN_IMPRESSIONS_FOR_JUDGMENT})"
            return analysis

        analysis["metrics"] = {
            "impressions": metrics.impressions,
            "clicks": metrics.clicks,
            "ctr": metrics.ctr,
            "conversions": metrics.conversions,
            "conversion_rate": metrics.conversion_rate,
        }

        # Compare to ad group average
        ctr_vs_avg = (metrics.ctr - ad_group_avg_ctr) / ad_group_avg_ctr * 100 if ad_group_avg_ctr > 0 else 0
        cvr_vs_avg = (metrics.conversion_rate - ad_group_avg_conversion_rate) / ad_group_avg_conversion_rate * 100 if ad_group_avg_conversion_rate > 0 else 0

        analysis["ctr_vs_avg"] = ctr_vs_avg
        analysis["cvr_vs_avg"] = cvr_vs_avg

        # Categorize performance
        if ctr_vs_avg > 20 or cvr_vs_avg > 20:
            analysis["performance_category"] = "top"
            analysis["reason"] = f"CTR {ctr_vs_avg:+.1f}% vs avg, CVR {cvr_vs_avg:+.1f}% vs avg"
        elif ctr_vs_avg < -20 and cvr_vs_avg < -20:
            analysis["performance_category"] = "bottom"
            analysis["reason"] = f"CTR {ctr_vs_avg:+.1f}% vs avg, CVR {cvr_vs_avg:+.1f}% vs avg"

        return analysis
