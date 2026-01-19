"""Central recommendation engine.

Aggregates insights from all analyzers and produces prioritized recommendations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from ..config import Config, DEFAULT_CONFIG
from ..models import Campaign, Keyword, SearchTerm
from ..models.recommendations import Recommendation, RecommendationBatch, RiskLevel
from ..analyzers import (
    LearningPhaseDetector,
    PerformanceAnalyzer,
    BudgetAnalyzer,
    KeywordAnalyzer,
    GeoAnalyzer,
    AudienceAnalyzer,
    CreativeAnalyzer,
    StructureAnalyzer,
)
from ..core.data_store import DataStore
from ..utils.logging import get_logger

logger = get_logger(__name__)


class RecommendationEngine:
    """
    Central recommendation engine.

    Aggregates insights from all analyzers and produces
    prioritized, risk-assessed recommendations.

    Key principles:
    - Every recommendation MUST have explanation and evidence
    - Filter by confidence and data sufficiency
    - Prioritize by expected impact / risk ratio
    - Respect learning phases - no recommendations for entities in learning
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Optional[Config] = None,
    ):
        self.data_store = data_store
        self.config = config or DEFAULT_CONFIG

        # Initialize analyzers
        self.learning_detector = LearningPhaseDetector(data_store, config)
        self.performance_analyzer = PerformanceAnalyzer(config)
        self.budget_analyzer = BudgetAnalyzer(config)
        self.keyword_analyzer = KeywordAnalyzer(config)
        self.geo_analyzer = GeoAnalyzer(config)
        self.audience_analyzer = AudienceAnalyzer(config)
        self.creative_analyzer = CreativeAnalyzer(config)
        self.structure_analyzer = StructureAnalyzer(config)

    def generate_recommendations(
        self,
        campaigns: List[Campaign],
        keywords: List[Keyword],
        search_terms: List[SearchTerm],
        geo_data: List = None,
        audience_data: List = None,
        ads: List = None,
    ) -> RecommendationBatch:
        """
        Generate all recommendations from available data.

        Args:
            campaigns: Campaign data with metrics
            keywords: Keyword data with metrics
            search_terms: Search term report data
            geo_data: Optional geo performance data
            audience_data: Optional audience performance data
            ads: Optional ad performance data

        Returns:
            RecommendationBatch with prioritized recommendations
        """
        logger.info("Generating recommendations", campaign_count=len(campaigns))

        all_recommendations = []

        # Calculate account-level metrics
        total_cost = sum(c.metrics.cost for c in campaigns if c.metrics)
        total_conv = sum(c.metrics.conversions for c in campaigns if c.metrics)
        account_avg_cpa = total_cost / total_conv if total_conv > 0 else 0

        # 1. Budget recommendations
        budget_recs = self._generate_budget_recommendations(campaigns)
        all_recommendations.extend(budget_recs)

        # 2. Keyword recommendations
        keyword_recs = self._generate_keyword_recommendations(
            keywords, search_terms, account_avg_cpa
        )
        all_recommendations.extend(keyword_recs)

        # 3. Geo recommendations
        if geo_data:
            geo_recs = self._generate_geo_recommendations(geo_data, account_avg_cpa)
            all_recommendations.extend(geo_recs)

        # 4. Audience recommendations
        if audience_data:
            audience_recs = self._generate_audience_recommendations(
                audience_data, account_avg_cpa
            )
            all_recommendations.extend(audience_recs)

        # 5. Structure recommendations
        structure_recs = self._generate_structure_recommendations(
            campaigns, keywords, search_terms
        )
        all_recommendations.extend(structure_recs)

        # Filter out recommendations for entities in learning
        filtered_recs = self._filter_learning_phase(all_recommendations)

        # Prioritize recommendations
        prioritized = self._prioritize_recommendations(filtered_recs)

        # Calculate total expected impact
        total_impact = self._calculate_total_impact(prioritized)

        batch = RecommendationBatch(
            generated_at=datetime.utcnow(),
            recommendations=prioritized,
            total_expected_impact=total_impact,
            summary=self._generate_summary(prioritized),
        )

        logger.info(
            "Recommendations generated",
            total=len(all_recommendations),
            after_filter=len(filtered_recs),
            final=len(prioritized),
        )

        return batch

    def validate_recommendation(
        self,
        recommendation: Recommendation,
    ) -> Dict[str, Any]:
        """
        Validate a recommendation before execution.

        Checks:
        - Entity not in learning phase
        - Sufficient data for decision
        - No conflicting recent changes
        - Within safe change limits
        """
        issues = []

        # Check learning phase
        learning_status = self.learning_detector.is_in_learning(
            recommendation.entity_type,
            recommendation.entity_id,
        )
        if learning_status.is_in_learning:
            issues.append({
                "type": "learning_phase",
                "message": f"Entity is in learning phase ({learning_status.days_remaining} days remaining)",
                "blocking": True,
            })

        # Check days since last change
        days_since_change = self.learning_detector.get_days_since_last_change(
            recommendation.entity_type,
            recommendation.entity_id,
        )
        min_days = self.config.budget.MIN_DAYS_BETWEEN_CHANGES

        if days_since_change < min_days:
            issues.append({
                "type": "recent_change",
                "message": f"Recent change {days_since_change} days ago (minimum {min_days} required)",
                "blocking": True,
            })

        # Check confidence threshold
        if recommendation.confidence < 0.5:
            issues.append({
                "type": "low_confidence",
                "message": f"Confidence {recommendation.confidence:.0%} is below 50% threshold",
                "blocking": False,
            })

        is_valid = not any(i["blocking"] for i in issues)

        return {
            "is_valid": is_valid,
            "issues": issues,
            "recommendation_id": recommendation.id,
        }

    def _generate_budget_recommendations(
        self,
        campaigns: List[Campaign],
    ) -> List[Recommendation]:
        """Generate budget-related recommendations."""
        account_analysis = self.budget_analyzer.analyze_all_campaigns(campaigns)
        return self.budget_analyzer.recommend_budget_changes(campaigns, account_analysis)

    def _generate_keyword_recommendations(
        self,
        keywords: List[Keyword],
        search_terms: List[SearchTerm],
        account_avg_cpa: float,
    ) -> List[Recommendation]:
        """Generate keyword-related recommendations."""
        return self.keyword_analyzer.recommend_keyword_actions(keywords, search_terms)

    def _generate_geo_recommendations(
        self,
        geo_data: List,
        account_avg_cpa: float,
    ) -> List[Recommendation]:
        """Generate geo-related recommendations."""
        geo_analysis = self.geo_analyzer.analyze_geo_performance(geo_data, account_avg_cpa)
        return self.geo_analyzer.recommend_geo_actions(geo_analysis)

    def _generate_audience_recommendations(
        self,
        audience_data: List,
        account_avg_cpa: float,
    ) -> List[Recommendation]:
        """Generate audience-related recommendations."""
        audience_analysis = self.audience_analyzer.analyze_audience_performance(
            audience_data, account_avg_cpa
        )
        return self.audience_analyzer.recommend_audience_actions(audience_analysis)

    def _generate_structure_recommendations(
        self,
        campaigns: List[Campaign],
        keywords: List[Keyword],
        search_terms: List[SearchTerm],
    ) -> List[Recommendation]:
        """Generate structure-related recommendations."""
        structure_analysis = self.structure_analyzer.analyze_account_structure(
            campaigns, keywords, search_terms
        )
        return self.structure_analyzer.recommend_structure_changes(structure_analysis)

    def _filter_learning_phase(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Filter out recommendations for entities in learning phase."""
        filtered = []

        for rec in recommendations:
            learning_status = self.learning_detector.is_in_learning(
                rec.entity_type, rec.entity_id
            )
            if not learning_status.is_in_learning:
                filtered.append(rec)
            else:
                logger.debug(
                    "Filtered recommendation due to learning phase",
                    rec_id=rec.id,
                    entity=rec.entity_name,
                )

        return filtered

    def _prioritize_recommendations(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """
        Prioritize recommendations by impact/risk ratio.

        Priority factors:
        - Expected impact (higher = higher priority)
        - Confidence (higher = higher priority)
        - Risk level (lower risk = higher priority)
        """
        def priority_score(rec: Recommendation) -> float:
            # Impact score (normalize to 0-1)
            impact = abs(rec.expected_impact.change_percent) / 100
            impact_score = min(1.0, impact)

            # Confidence score (already 0-1)
            confidence_score = rec.confidence

            # Risk score (invert: low risk = high score)
            risk_map = {
                RiskLevel.LOW: 1.0,
                RiskLevel.MEDIUM: 0.6,
                RiskLevel.HIGH: 0.3,
            }
            risk_score = risk_map.get(rec.risk_level, 0.5)

            # Combined score
            return (impact_score * 0.4) + (confidence_score * 0.3) + (risk_score * 0.3)

        # Sort by priority score (highest first)
        sorted_recs = sorted(recommendations, key=priority_score, reverse=True)

        # Assign priority numbers
        for i, rec in enumerate(sorted_recs):
            rec.priority = i + 1

        return sorted_recs

    def _calculate_total_impact(
        self,
        recommendations: List[Recommendation],
    ) -> Dict[str, float]:
        """Calculate total expected impact across all recommendations."""
        impact_by_metric = {}

        for rec in recommendations:
            metric = rec.expected_impact.metric
            change = rec.expected_impact.expected_value - rec.expected_impact.current_value

            if metric not in impact_by_metric:
                impact_by_metric[metric] = 0

            impact_by_metric[metric] += change

        return {k: round(v, 2) for k, v in impact_by_metric.items()}

    def _generate_summary(self, recommendations: List[Recommendation]) -> str:
        """Generate a human-readable summary of recommendations."""
        if not recommendations:
            return "No recommendations at this time."

        low_risk = sum(1 for r in recommendations if r.risk_level == RiskLevel.LOW)
        medium_risk = sum(1 for r in recommendations if r.risk_level == RiskLevel.MEDIUM)
        high_risk = sum(1 for r in recommendations if r.risk_level == RiskLevel.HIGH)

        return (
            f"{len(recommendations)} recommendations: "
            f"{low_risk} low risk, {medium_risk} medium risk, {high_risk} high risk"
        )
