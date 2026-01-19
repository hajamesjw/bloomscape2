"""Budget intelligence module.

Analyzes budget utilization and recommends optimal allocation.
"""

from typing import Optional, List, Dict, Any
from datetime import date
from dataclasses import dataclass

from ..config import Config, DEFAULT_CONFIG
from ..models import Campaign, Metrics, BudgetUtilization
from ..models.recommendations import (
    Recommendation,
    RecommendationCategory,
    RiskLevel,
    RolloutStrategy,
    ExpectedImpact,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BudgetAnalyzer:
    """
    Budget intelligence and optimization.

    Key principles:
    - Never change budget by more than 20% at once
    - Minimum 7 days between budget changes
    - Consider impression share lost to budget
    - Model diminishing returns
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG
        self.max_increase_pct = self.config.budget.MAX_INCREASE_PCT
        self.max_decrease_pct = self.config.budget.MAX_DECREASE_PCT
        self.min_days_between = self.config.budget.MIN_DAYS_BETWEEN_CHANGES
        self.min_budget = self.config.budget.MIN_BUDGET_FLOOR

    def analyze_utilization(
        self,
        campaign: Campaign,
    ) -> BudgetUtilization:
        """
        Analyze budget utilization for a campaign.

        Returns:
            BudgetUtilization with efficiency metrics
        """
        if not campaign.metrics_history:
            return BudgetUtilization(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                daily_budget=campaign.budget_amount,
                avg_daily_spend_7d=0,
                avg_daily_spend_30d=0,
                utilization_rate_7d=0,
                utilization_rate_30d=0,
                impression_share_lost_budget_7d=None,
                impression_share_lost_budget_30d=None,
            )

        metrics = campaign.metrics_history
        today = date.today()

        # Calculate 7-day averages
        metrics_7d = [m for m in metrics if (today - m.date).days <= 7]
        metrics_30d = [m for m in metrics if (today - m.date).days <= 30]

        avg_spend_7d = sum(m.cost for m in metrics_7d) / max(len(metrics_7d), 1)
        avg_spend_30d = sum(m.cost for m in metrics_30d) / max(len(metrics_30d), 1)

        utilization_7d = avg_spend_7d / campaign.budget_amount if campaign.budget_amount > 0 else 0
        utilization_30d = avg_spend_30d / campaign.budget_amount if campaign.budget_amount > 0 else 0

        # Get impression share lost to budget
        is_lost_7d = None
        is_lost_30d = None

        if metrics_7d:
            is_values_7d = [m.impression_share_lost_budget for m in metrics_7d if m.impression_share_lost_budget is not None]
            if is_values_7d:
                is_lost_7d = sum(is_values_7d) / len(is_values_7d)

        if metrics_30d:
            is_values_30d = [m.impression_share_lost_budget for m in metrics_30d if m.impression_share_lost_budget is not None]
            if is_values_30d:
                is_lost_30d = sum(is_values_30d) / len(is_values_30d)

        # Estimate incremental opportunity
        incremental = self._estimate_incremental_opportunity(
            campaign=campaign,
            metrics_30d=metrics_30d,
            impression_share_lost=is_lost_30d,
        )

        return BudgetUtilization(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            daily_budget=campaign.budget_amount,
            avg_daily_spend_7d=avg_spend_7d,
            avg_daily_spend_30d=avg_spend_30d,
            utilization_rate_7d=utilization_7d,
            utilization_rate_30d=utilization_30d,
            impression_share_lost_budget_7d=is_lost_7d,
            impression_share_lost_budget_30d=is_lost_30d,
            estimated_incremental_conversions=incremental.get("conversions"),
            estimated_incremental_cost=incremental.get("cost"),
            estimated_incremental_cpa=incremental.get("cpa"),
        )

    def analyze_all_campaigns(
        self,
        campaigns: List[Campaign],
    ) -> Dict[str, Any]:
        """
        Analyze budget across all campaigns.

        Returns:
            Account-level budget analysis with reallocation opportunities
        """
        utilizations = []
        for campaign in campaigns:
            util = self.analyze_utilization(campaign)
            utilizations.append(util)

        # Calculate totals
        total_budget = sum(u.daily_budget for u in utilizations)
        total_spend = sum(u.avg_daily_spend_30d for u in utilizations)

        # Identify high and low performers
        high_performers = []
        low_performers = []

        for util in utilizations:
            campaign = next((c for c in campaigns if c.id == util.campaign_id), None)
            if not campaign or not campaign.metrics:
                continue

            cpa = campaign.metrics.cpa
            if cpa is None:
                continue

            # Calculate account average CPA
            total_cost = sum(c.metrics.cost for c in campaigns if c.metrics)
            total_conv = sum(c.metrics.conversions for c in campaigns if c.metrics)
            avg_cpa = total_cost / total_conv if total_conv > 0 else 0

            if cpa < avg_cpa * 0.8 and util.impression_share_lost_budget_30d and util.impression_share_lost_budget_30d > 10:
                high_performers.append({
                    "campaign_id": util.campaign_id,
                    "campaign_name": util.campaign_name,
                    "cpa": cpa,
                    "is_lost_budget": util.impression_share_lost_budget_30d,
                    "budget": util.daily_budget,
                })
            elif cpa > avg_cpa * 1.5:
                low_performers.append({
                    "campaign_id": util.campaign_id,
                    "campaign_name": util.campaign_name,
                    "cpa": cpa,
                    "budget": util.daily_budget,
                })

        return {
            "total_daily_budget": total_budget,
            "total_daily_spend": total_spend,
            "overall_utilization": total_spend / total_budget if total_budget > 0 else 0,
            "campaigns_over_budget": [u for u in utilizations if u.utilization_rate_30d > 0.95],
            "campaigns_under_budget": [u for u in utilizations if u.utilization_rate_30d < 0.7],
            "high_performers_budget_constrained": high_performers,
            "low_performers": low_performers,
            "reallocation_opportunity": len(high_performers) > 0 and len(low_performers) > 0,
        }

    def recommend_budget_changes(
        self,
        campaigns: List[Campaign],
        account_analysis: Dict[str, Any],
    ) -> List[Recommendation]:
        """
        Generate budget change recommendations.

        Returns:
            List of budget recommendations with risk assessment
        """
        recommendations = []

        # Recommend increases for high performers losing impression share
        for hp in account_analysis.get("high_performers_budget_constrained", []):
            campaign = next((c for c in campaigns if c.id == hp["campaign_id"]), None)
            if not campaign:
                continue

            # Calculate recommended increase (max 20%)
            is_lost = hp.get("is_lost_budget", 0)
            increase_pct = min(self.max_increase_pct, is_lost / 2)  # Conservative: half of lost IS
            new_budget = campaign.budget_amount * (1 + increase_pct / 100)

            # Estimate impact
            current_conv = campaign.metrics.conversions if campaign.metrics else 0
            estimated_additional = current_conv * (increase_pct / 100) * 0.7  # 70% efficiency

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.BUDGET,
                action=f"Increase budget from ${campaign.budget_amount:.2f} to ${new_budget:.2f} (+{increase_pct:.1f}%)",
                entity_type="campaign",
                entity_id=campaign.id,
                entity_name=campaign.name,
                confidence=0.8,
                risk_level=RiskLevel.LOW,
                expected_impact=ExpectedImpact(
                    metric="conversions",
                    current_value=current_conv,
                    expected_value=current_conv + estimated_additional,
                    change_percent=(estimated_additional / current_conv * 100) if current_conv > 0 else 0,
                    confidence_interval_low=estimated_additional * 0.5,
                    confidence_interval_high=estimated_additional * 1.3,
                ),
                downside_scenario="Marginal CPA may increase slightly as we capture less qualified traffic",
                rollout_strategy=RolloutStrategy.IMMEDIATE,
                rollback_trigger="If CPA increases >20% after 7 days",
                rationale=f"Campaign is losing {is_lost:.1f}% impression share to budget while maintaining strong CPA of ${hp['cpa']:.2f}",
                evidence=[
                    {"metric": "impression_share_lost_budget", "value": is_lost},
                    {"metric": "current_cpa", "value": hp['cpa']},
                ],
                assumptions=[
                    "Incremental traffic quality will be similar to current",
                    "Competitor landscape remains stable",
                ],
                api_operations=[{
                    "operation": "update_campaign_budget",
                    "campaign_id": campaign.id,
                    "new_budget": new_budget,
                }],
            )
            recommendations.append(rec)

        # Recommend decreases for low performers
        for lp in account_analysis.get("low_performers", []):
            campaign = next((c for c in campaigns if c.id == lp["campaign_id"]), None)
            if not campaign:
                continue

            # Don't reduce below minimum
            decrease_pct = min(self.max_decrease_pct, 15)
            new_budget = max(self.min_budget, campaign.budget_amount * (1 - decrease_pct / 100))

            if new_budget >= campaign.budget_amount:
                continue

            import uuid
            rec = Recommendation(
                id=str(uuid.uuid4()),
                category=RecommendationCategory.BUDGET,
                action=f"Reduce budget from ${campaign.budget_amount:.2f} to ${new_budget:.2f} (-{decrease_pct:.1f}%)",
                entity_type="campaign",
                entity_id=campaign.id,
                entity_name=campaign.name,
                confidence=0.7,
                risk_level=RiskLevel.MEDIUM,
                expected_impact=ExpectedImpact(
                    metric="cost",
                    current_value=campaign.budget_amount * 30,
                    expected_value=new_budget * 30,
                    change_percent=-decrease_pct,
                    confidence_interval_low=-decrease_pct - 5,
                    confidence_interval_high=-decrease_pct + 5,
                ),
                downside_scenario="May lose some converting traffic; monitor conversion volume",
                rollout_strategy=RolloutStrategy.GRADUAL,
                rollback_trigger="If conversion volume drops >30%",
                rationale=f"Campaign CPA of ${lp['cpa']:.2f} is significantly above account average",
                evidence=[
                    {"metric": "current_cpa", "value": lp['cpa']},
                ],
                assumptions=[
                    "High CPA is structural, not temporary",
                    "Budget can be better utilized elsewhere",
                ],
                api_operations=[{
                    "operation": "update_campaign_budget",
                    "campaign_id": campaign.id,
                    "new_budget": new_budget,
                }],
            )
            recommendations.append(rec)

        return recommendations

    def _estimate_incremental_opportunity(
        self,
        campaign: Campaign,
        metrics_30d: List[Metrics],
        impression_share_lost: Optional[float],
    ) -> Dict[str, float]:
        """Estimate incremental opportunity if budget were uncapped."""
        if not impression_share_lost or impression_share_lost < 5:
            return {}

        if not metrics_30d:
            return {}

        # Current performance
        total_conv = sum(m.conversions for m in metrics_30d)
        total_cost = sum(m.cost for m in metrics_30d)
        current_cpa = total_cost / total_conv if total_conv > 0 else 0

        # Estimate incremental (with diminishing returns)
        # Assume 70% efficiency on incremental traffic
        diminishing_factor = 0.7

        incremental_share = impression_share_lost / 100
        incremental_conv = total_conv * incremental_share * diminishing_factor
        incremental_cost = incremental_conv * current_cpa * (1 / diminishing_factor)

        incremental_cpa = incremental_cost / incremental_conv if incremental_conv > 0 else 0

        return {
            "conversions": round(incremental_conv, 1),
            "cost": round(incremental_cost, 2),
            "cpa": round(incremental_cpa, 2),
        }

    def simulate_budget_change(
        self,
        campaign: Campaign,
        new_budget: float,
    ) -> Dict[str, Any]:
        """
        Simulate the expected outcome of a budget change.

        Returns:
            Projected metrics under new budget
        """
        if not campaign.metrics:
            return {"error": "No metrics available"}

        current_budget = campaign.budget_amount
        change_pct = ((new_budget - current_budget) / current_budget) * 100

        # Check limits
        if change_pct > self.max_increase_pct:
            return {
                "error": f"Increase exceeds maximum of {self.max_increase_pct}%",
                "recommended_max": current_budget * (1 + self.max_increase_pct / 100),
            }

        if change_pct < -self.max_decrease_pct:
            return {
                "error": f"Decrease exceeds maximum of {self.max_decrease_pct}%",
                "recommended_min": current_budget * (1 - self.max_decrease_pct / 100),
            }

        if new_budget < self.min_budget:
            return {
                "error": f"Budget below minimum of ${self.min_budget}",
                "recommended_min": self.min_budget,
            }

        # Project metrics
        current_metrics = campaign.metrics
        efficiency_factor = 0.85 if change_pct > 0 else 1.1  # Diminishing returns on increase

        projected_spend = new_budget  # Assuming full utilization
        projected_conv = current_metrics.conversions * (new_budget / current_budget) * efficiency_factor
        projected_cpa = projected_spend / projected_conv if projected_conv > 0 else 0

        return {
            "current": {
                "budget": current_budget,
                "spend": current_metrics.cost,
                "conversions": current_metrics.conversions,
                "cpa": current_metrics.cpa,
            },
            "projected": {
                "budget": new_budget,
                "spend": projected_spend,
                "conversions": round(projected_conv, 1),
                "cpa": round(projected_cpa, 2),
            },
            "change": {
                "budget_pct": round(change_pct, 1),
                "conversions_pct": round((projected_conv / current_metrics.conversions - 1) * 100, 1) if current_metrics.conversions > 0 else 0,
                "cpa_pct": round((projected_cpa / current_metrics.cpa - 1) * 100, 1) if current_metrics.cpa else 0,
            },
        }
