"""Campaign structure analysis module."""

from typing import Optional, List, Dict, Any
from collections import defaultdict

from ..config import Config, DEFAULT_CONFIG
from ..models import Campaign, Keyword, SearchTerm
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class StructureAnalyzer:
    """
    Campaign structure analysis.

    Evaluates:
    - Over-segmentation (too many campaigns with insufficient data)
    - Under-segmentation (mixed intent in single ad groups)
    - Cannibalization between campaigns
    """

    # Healthy thresholds
    MIN_CONVERSIONS_PER_CAMPAIGN_MONTHLY = 30
    MIN_CONVERSIONS_PER_AD_GROUP_MONTHLY = 10

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def analyze_account_structure(
        self,
        campaigns: List[Campaign],
        keywords: List[Keyword],
        search_terms: List[SearchTerm],
    ) -> Dict[str, Any]:
        """
        Analyze overall account structure health.

        Returns:
            Structure analysis with issues and recommendations
        """
        issues = []

        # Check for over-segmentation
        over_segmented = self._check_over_segmentation(campaigns)
        if over_segmented["is_over_segmented"]:
            issues.append({
                "type": "over_segmentation",
                "severity": "medium",
                "details": over_segmented,
            })

        # Check for cannibalization
        cannibalization = self._detect_cannibalization(search_terms)
        if cannibalization["has_cannibalization"]:
            issues.append({
                "type": "cannibalization",
                "severity": "high",
                "details": cannibalization,
            })

        # Check for under-segmentation
        under_segmented = self._check_under_segmentation(keywords)
        if under_segmented["is_under_segmented"]:
            issues.append({
                "type": "under_segmentation",
                "severity": "low",
                "details": under_segmented,
            })

        # Calculate structure health score
        health_score = 100
        for issue in issues:
            if issue["severity"] == "high":
                health_score -= 30
            elif issue["severity"] == "medium":
                health_score -= 15
            else:
                health_score -= 5

        return {
            "health_score": max(0, health_score),
            "total_campaigns": len(campaigns),
            "issues": issues,
            "summary": {
                "over_segmentation": over_segmented,
                "cannibalization": cannibalization,
                "under_segmentation": under_segmented,
            },
        }

    def _check_over_segmentation(
        self,
        campaigns: List[Campaign],
    ) -> Dict[str, Any]:
        """
        Check if account is over-segmented.

        Over-segmentation = too many campaigns with insufficient conversion data
        """
        low_volume_campaigns = []

        for campaign in campaigns:
            if not campaign.metrics:
                continue

            # Estimate monthly conversions (assuming metrics are for ~30 days)
            monthly_conv = campaign.metrics.conversions

            if monthly_conv < self.MIN_CONVERSIONS_PER_CAMPAIGN_MONTHLY:
                low_volume_campaigns.append({
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "monthly_conversions": monthly_conv,
                    "recommendation": "Consider consolidating with similar campaigns",
                })

        is_over_segmented = len(low_volume_campaigns) > len(campaigns) * 0.4  # >40% have low volume

        return {
            "is_over_segmented": is_over_segmented,
            "low_volume_campaigns": low_volume_campaigns,
            "low_volume_count": len(low_volume_campaigns),
            "total_campaigns": len(campaigns),
            "percentage": len(low_volume_campaigns) / len(campaigns) * 100 if campaigns else 0,
        }

    def _detect_cannibalization(
        self,
        search_terms: List[SearchTerm],
    ) -> Dict[str, Any]:
        """
        Detect campaigns competing for the same search terms.

        Cannibalization = same query triggering ads in multiple campaigns
        """
        # Group search terms by query
        terms_by_query: Dict[str, List[SearchTerm]] = defaultdict(list)
        for term in search_terms:
            terms_by_query[term.query.lower()].append(term)

        # Find queries appearing in multiple campaigns
        cannibalized_queries = []

        for query, terms in terms_by_query.items():
            campaign_ids = set(t.campaign_id for t in terms)

            if len(campaign_ids) > 1:
                # Calculate total spend on this query
                total_cost = sum(t.metrics.cost for t in terms if t.metrics)
                total_clicks = sum(t.metrics.clicks for t in terms if t.metrics)

                if total_cost > 20:  # Only flag if meaningful spend
                    cannibalized_queries.append({
                        "query": query,
                        "campaigns": list(campaign_ids),
                        "campaign_count": len(campaign_ids),
                        "total_cost": total_cost,
                        "total_clicks": total_clicks,
                    })

        # Sort by cost impact
        cannibalized_queries.sort(key=lambda x: x["total_cost"], reverse=True)

        has_cannibalization = len(cannibalized_queries) > 0

        return {
            "has_cannibalization": has_cannibalization,
            "cannibalized_queries": cannibalized_queries[:20],  # Top 20
            "total_cannibalized": len(cannibalized_queries),
            "estimated_waste": sum(q["total_cost"] * 0.1 for q in cannibalized_queries),  # ~10% inefficiency
        }

    def _check_under_segmentation(
        self,
        keywords: List[Keyword],
    ) -> Dict[str, Any]:
        """
        Check for under-segmentation (mixed intent in ad groups).

        Under-segmentation = very different keywords in the same ad group
        """
        # Group keywords by ad group
        by_ad_group: Dict[str, List[Keyword]] = defaultdict(list)
        for kw in keywords:
            by_ad_group[kw.ad_group_id].append(kw)

        mixed_intent_groups = []

        for ad_group_id, group_keywords in by_ad_group.items():
            if len(group_keywords) < 3:
                continue

            # Simple heuristic: check if keyword lengths vary significantly
            # (Very different lengths often indicate mixed intent)
            lengths = [len(kw.text.split()) for kw in group_keywords]
            avg_length = sum(lengths) / len(lengths)
            length_variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)

            # Also check for brand vs non-brand mix
            has_brand_indicator = any("brand" in kw.text.lower() for kw in group_keywords)
            has_generic = any(len(kw.text.split()) >= 4 for kw in group_keywords)

            if length_variance > 4 or (has_brand_indicator and has_generic):
                mixed_intent_groups.append({
                    "ad_group_id": ad_group_id,
                    "keyword_count": len(group_keywords),
                    "sample_keywords": [kw.text for kw in group_keywords[:5]],
                    "recommendation": "Consider splitting into separate ad groups",
                })

        return {
            "is_under_segmented": len(mixed_intent_groups) > 0,
            "mixed_intent_groups": mixed_intent_groups[:10],
            "group_count": len(mixed_intent_groups),
        }

    def recommend_structure_changes(
        self,
        structure_analysis: Dict[str, Any],
    ) -> List[Recommendation]:
        """
        Generate structure change recommendations.

        Note: Structure changes are high-impact and should be reviewed carefully.
        """
        recommendations = []

        # Cannibalization recommendations
        cannibalization = structure_analysis.get("summary", {}).get("cannibalization", {})
        if cannibalization.get("has_cannibalization"):
            top_queries = cannibalization.get("cannibalized_queries", [])[:3]

            for query_info in top_queries:
                import uuid
                rec = Recommendation(
                    id=str(uuid.uuid4()),
                    category=RecommendationCategory.STRUCTURE,
                    action=f"Resolve cannibalization for query '{query_info['query']}'",
                    entity_type="account",
                    entity_id="structure",
                    entity_name="Account Structure",
                    confidence=0.7,
                    risk_level=RiskLevel.MEDIUM,
                    expected_impact=ExpectedImpact(
                        metric="efficiency",
                        current_value=0,
                        expected_value=query_info["total_cost"] * 0.1,
                        change_percent=10,
                        confidence_interval_low=5,
                        confidence_interval_high=15,
                    ),
                    downside_scenario="Restructuring may temporarily disrupt performance",
                    rollout_strategy=RolloutStrategy.MANUAL_REVIEW,
                    rollback_trigger="If overall performance drops",
                    rationale=f"Query '{query_info['query']}' is triggering ads in {query_info['campaign_count']} campaigns, causing internal competition",
                    evidence=[
                        {"metric": "campaigns_competing", "value": query_info["campaign_count"]},
                        {"metric": "total_cost", "value": query_info["total_cost"]},
                    ],
                    assumptions=[
                        "Internal competition is raising CPCs",
                        "Consolidating will improve efficiency",
                    ],
                )
                recommendations.append(rec)

        # Over-segmentation recommendations
        over_seg = structure_analysis.get("summary", {}).get("over_segmentation", {})
        if over_seg.get("is_over_segmented"):
            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.STRUCTURE,
                action="Consider consolidating low-volume campaigns",
                entity_type="account",
                entity_id="structure",
                entity_name="Account Structure",
                confidence=0.6,
                risk_level=RiskLevel.HIGH,
                expected_impact=ExpectedImpact(
                    metric="learning_efficiency",
                    current_value=0,
                    expected_value=0,
                    change_percent=20,
                    confidence_interval_low=10,
                    confidence_interval_high=30,
                ),
                downside_scenario="Consolidation may lose some targeting specificity",
                rollout_strategy=RolloutStrategy.MANUAL_REVIEW,
                rollback_trigger="N/A - structural change",
                rationale=f"{over_seg['low_volume_count']} of {over_seg['total_campaigns']} campaigns have <{self.MIN_CONVERSIONS_PER_CAMPAIGN_MONTHLY} monthly conversions, limiting Smart Bidding effectiveness",
                evidence=[
                    {"metric": "low_volume_campaigns", "value": over_seg['low_volume_count']},
                    {"metric": "percentage", "value": over_seg['percentage']},
                ],
                assumptions=[
                    "Consolidation will improve data density",
                    "Smart Bidding will work better with more data",
                ],
            )
            recommendations.append(rec)

        return recommendations
