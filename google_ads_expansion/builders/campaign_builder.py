"""Campaign builder.

Builds complete campaign structures from keyword clusters and ad copy:
- Campaign structure (search, display, pmax)
- Ad groups with proper theming
- Keyword-to-ad-group mapping
- Budget allocation
- Bid strategy selection
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ..models.campaigns import (
    CampaignBlueprint,
    AdGroupBlueprint,
    CampaignPlan,
    CampaignType,
    BidStrategyType,
)
from ..models.keywords import KeywordCluster, KeywordIdea, KeywordIntent
from ..models.ads import AdCopySet
from ..generators.keyword_expander import KeywordExpander, ExpansionContext
from ..generators.ad_copy_generator import AdCopyGenerator, AdCopyContext
from ..config import EXPANSION_CONFIG


@dataclass
class CampaignBuildContext:
    """Context for building campaigns."""

    business_name: str
    business_type: str
    website_url: str

    # Budget constraints
    monthly_budget: float = 3000.0
    min_daily_budget: float = 10.0
    max_daily_budget: float = 500.0

    # Goals
    primary_goal: str = "conversions"  # conversions, leads, traffic, awareness
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None

    # Targeting
    target_locations: List[str] = None
    target_languages: List[str] = None

    # Business info for ad copy
    unique_selling_points: List[str] = None
    benefits: List[str] = None
    features: List[str] = None

    def __post_init__(self):
        if self.target_locations is None:
            self.target_locations = ["United States"]
        if self.target_languages is None:
            self.target_languages = ["English"]
        if self.unique_selling_points is None:
            self.unique_selling_points = []
        if self.benefits is None:
            self.benefits = []
        if self.features is None:
            self.features = []


class CampaignBuilder:
    """Builds complete Google Ads campaign structures."""

    def __init__(self, context: CampaignBuildContext):
        """Initialize with build context."""
        self.context = context
        self.config = EXPANSION_CONFIG["campaign_building"]

    def build_campaign_plan(
        self,
        keyword_clusters: List[KeywordCluster],
        ad_copy_sets: Optional[List[AdCopySet]] = None,
        campaign_structure: str = "single"  # single, by_intent, by_theme
    ) -> CampaignPlan:
        """
        Build a complete campaign plan from keyword clusters.

        Args:
            keyword_clusters: Grouped keywords for targeting
            ad_copy_sets: Pre-generated ad copy (optional)
            campaign_structure: How to organize campaigns

        Returns:
            Complete campaign plan ready for implementation
        """
        campaigns = []

        if campaign_structure == "single":
            # One campaign with multiple ad groups
            campaign = self._build_single_campaign(keyword_clusters, ad_copy_sets)
            campaigns.append(campaign)

        elif campaign_structure == "by_intent":
            # Separate campaigns by intent
            campaigns = self._build_campaigns_by_intent(keyword_clusters, ad_copy_sets)

        elif campaign_structure == "by_theme":
            # Separate campaigns by theme/cluster
            campaigns = self._build_campaigns_by_theme(keyword_clusters, ad_copy_sets)

        # Allocate budget across campaigns
        self._allocate_budgets(campaigns)

        # Build the plan
        plan = CampaignPlan(
            generated_at=datetime.now().isoformat(),
            plan_name=f"{self.context.business_name} - Expansion Plan",
            campaigns=campaigns,
        )

        # Add implementation notes
        plan.implementation_notes = self._generate_implementation_notes(campaigns)
        plan.prerequisites = self._generate_prerequisites()

        return plan

    def _build_single_campaign(
        self,
        clusters: List[KeywordCluster],
        ad_copy_sets: Optional[List[AdCopySet]]
    ) -> CampaignBlueprint:
        """Build a single campaign with multiple ad groups."""
        campaign = CampaignBlueprint(
            name=f"{self.context.business_name} - Search",
            campaign_type=CampaignType.SEARCH,
            daily_budget=self._calculate_daily_budget(),
            bid_strategy=self._select_bid_strategy(),
            target_cpa=self.context.target_cpa,
            target_roas=self.context.target_roas,
            locations=self.context.target_locations,
            languages=self.context.target_languages,
        )

        # Create ad group for each cluster
        for cluster in clusters:
            ad_group = self._build_ad_group(cluster, ad_copy_sets)
            campaign.ad_groups.append(ad_group)

        # Add campaign-level negatives
        campaign.negative_keywords = self._generate_campaign_negatives(clusters)

        return campaign

    def _build_campaigns_by_intent(
        self,
        clusters: List[KeywordCluster],
        ad_copy_sets: Optional[List[AdCopySet]]
    ) -> List[CampaignBlueprint]:
        """Build separate campaigns for each intent type."""
        campaigns = []

        # Group clusters by dominant intent
        intent_groups: Dict[str, List[KeywordCluster]] = {
            "transactional": [],
            "commercial": [],
            "informational": [],
        }

        for cluster in clusters:
            # Determine dominant intent in cluster
            intents = [kw.intent for kw in cluster.keywords if kw.intent]
            if intents:
                dominant = max(set(intents), key=intents.count)
                intent_groups[dominant.value].append(cluster)
            else:
                intent_groups["commercial"].append(cluster)

        # Build campaign for each intent
        intent_configs = {
            "transactional": {
                "name_suffix": "High Intent",
                "bid_strategy": BidStrategyType.MAXIMIZE_CONVERSIONS,
                "budget_weight": 0.5,  # 50% of budget
            },
            "commercial": {
                "name_suffix": "Research",
                "bid_strategy": BidStrategyType.MAXIMIZE_CONVERSIONS,
                "budget_weight": 0.35,
            },
            "informational": {
                "name_suffix": "Awareness",
                "bid_strategy": BidStrategyType.MAXIMIZE_CLICKS,
                "budget_weight": 0.15,
            },
        }

        for intent, intent_clusters in intent_groups.items():
            if not intent_clusters:
                continue

            config = intent_configs[intent]
            daily_budget = self._calculate_daily_budget() * config["budget_weight"]

            campaign = CampaignBlueprint(
                name=f"{self.context.business_name} - {config['name_suffix']}",
                campaign_type=CampaignType.SEARCH,
                daily_budget=max(daily_budget, self.context.min_daily_budget),
                bid_strategy=config["bid_strategy"],
                target_cpa=self.context.target_cpa if intent == "transactional" else None,
                locations=self.context.target_locations,
                languages=self.context.target_languages,
            )

            for cluster in intent_clusters:
                ad_group = self._build_ad_group(cluster, ad_copy_sets)
                campaign.ad_groups.append(ad_group)

            campaign.negative_keywords = self._generate_campaign_negatives(intent_clusters)
            campaigns.append(campaign)

        return campaigns

    def _build_campaigns_by_theme(
        self,
        clusters: List[KeywordCluster],
        ad_copy_sets: Optional[List[AdCopySet]]
    ) -> List[CampaignBlueprint]:
        """Build separate campaigns for major themes."""
        campaigns = []

        # Group similar clusters (simple approach - by first word)
        theme_groups: Dict[str, List[KeywordCluster]] = {}

        for cluster in clusters:
            # Extract theme from cluster name
            theme = cluster.name.split("_")[0] if "_" in cluster.name else cluster.name
            theme = theme.lower()

            if theme not in theme_groups:
                theme_groups[theme] = []
            theme_groups[theme].append(cluster)

        # Build campaign for each theme
        budget_per_theme = self._calculate_daily_budget() / max(len(theme_groups), 1)

        for theme, theme_clusters in theme_groups.items():
            campaign = CampaignBlueprint(
                name=f"{self.context.business_name} - {theme.title()}",
                campaign_type=CampaignType.SEARCH,
                daily_budget=max(budget_per_theme, self.context.min_daily_budget),
                bid_strategy=self._select_bid_strategy(),
                target_cpa=self.context.target_cpa,
                locations=self.context.target_locations,
                languages=self.context.target_languages,
            )

            for cluster in theme_clusters:
                ad_group = self._build_ad_group(cluster, ad_copy_sets)
                campaign.ad_groups.append(ad_group)

            campaign.negative_keywords = self._generate_campaign_negatives(theme_clusters)
            campaigns.append(campaign)

        return campaigns

    def _build_ad_group(
        self,
        cluster: KeywordCluster,
        ad_copy_sets: Optional[List[AdCopySet]]
    ) -> AdGroupBlueprint:
        """Build an ad group from a keyword cluster."""
        # Use suggested name or generate one
        name = cluster.suggested_ad_group_name or self._generate_ad_group_name(cluster)

        ad_group = AdGroupBlueprint(
            name=name,
            theme=cluster.theme,
            keywords=cluster.keywords,
            negative_keywords=self._generate_ad_group_negatives(cluster),
        )

        # Add ads
        if ad_copy_sets:
            # Find matching ad copy
            matching_ads = self._find_matching_ads(cluster, ad_copy_sets)
            ad_group.ads = matching_ads[:3]  # Max 3 ads per group
        else:
            # Generate basic ad copy
            ad_group.ads = self._generate_basic_ads(cluster)

        # Set bid based on cluster metrics
        ad_group.default_cpc_bid = cluster.avg_suggested_bid or 2.0

        # Estimate performance
        self._estimate_ad_group_performance(ad_group)

        return ad_group

    def _generate_ad_group_name(self, cluster: KeywordCluster) -> str:
        """Generate a descriptive ad group name."""
        # Get the most important keyword
        if cluster.keywords:
            main_kw = cluster.keywords[0].keyword
            words = main_kw.split()[:3]  # First 3 words
            return " ".join(word.title() for word in words)
        return cluster.name.replace("_", " ").title()

    def _find_matching_ads(
        self,
        cluster: KeywordCluster,
        ad_copy_sets: List[AdCopySet]
    ) -> List[AdCopySet]:
        """Find ad copy sets that match a cluster's keywords."""
        matching = []

        cluster_keywords = set(kw.keyword.lower() for kw in cluster.keywords)

        for ad in ad_copy_sets:
            # Check if ad's target keyword overlaps with cluster
            if ad.target_keyword.lower() in cluster_keywords:
                matching.append(ad)
            else:
                # Check for partial match
                ad_words = set(ad.target_keyword.lower().split())
                for kw in cluster_keywords:
                    kw_words = set(kw.split())
                    if ad_words & kw_words:  # Intersection
                        matching.append(ad)
                        break

        return matching

    def _generate_basic_ads(self, cluster: KeywordCluster) -> List[AdCopySet]:
        """Generate basic ad copy for a cluster."""
        # Create ad copy context from build context
        ad_context = AdCopyContext(
            business_name=self.context.business_name,
            business_type=self.context.business_type,
            unique_selling_points=self.context.unique_selling_points,
            benefits=self.context.benefits,
            features=self.context.features,
        )

        generator = AdCopyGenerator(ad_context)

        # Generate for top keyword
        if cluster.keywords:
            main_kw = cluster.keywords[0].keyword
            ad = generator.generate_ad_copy_set(
                target_keyword=main_kw,
                final_url=self.context.website_url,
            )
            return [ad]

        return []

    def _generate_ad_group_negatives(self, cluster: KeywordCluster) -> List[str]:
        """Generate ad group level negatives."""
        negatives = []

        # Cross-negative other clusters' core terms (to avoid overlap)
        # This would require knowledge of other clusters

        return negatives

    def _generate_campaign_negatives(
        self,
        clusters: List[KeywordCluster]
    ) -> List[str]:
        """Generate campaign-level negative keywords."""
        return [
            "free",
            "diy",
            "how to diy",
            "tutorial",
            "jobs",
            "career",
            "salary",
            "internship",
            "training",
            "certification",
            "course",
            "class",
            "youtube",
            "reddit",
            "wiki",
        ]

    def _estimate_ad_group_performance(self, ad_group: AdGroupBlueprint) -> None:
        """Estimate ad group performance metrics."""
        # Sum keyword volumes
        total_volume = sum(
            kw.avg_monthly_searches or 100
            for kw in ad_group.keywords
        )

        # Estimate based on industry averages
        # Assume 5% impression share, 3% CTR
        ad_group.estimated_impressions = int(total_volume * 0.05)
        ad_group.estimated_clicks = int(ad_group.estimated_impressions * 0.03)
        ad_group.estimated_cost = ad_group.estimated_clicks * (ad_group.default_cpc_bid or 2.0)

    def _calculate_daily_budget(self) -> float:
        """Calculate recommended daily budget."""
        daily = self.context.monthly_budget / 30
        return min(max(daily, self.context.min_daily_budget), self.context.max_daily_budget)

    def _select_bid_strategy(self) -> BidStrategyType:
        """Select appropriate bid strategy based on goals."""
        goal_strategies = {
            "conversions": BidStrategyType.MAXIMIZE_CONVERSIONS,
            "leads": BidStrategyType.MAXIMIZE_CONVERSIONS,
            "traffic": BidStrategyType.MAXIMIZE_CLICKS,
            "awareness": BidStrategyType.TARGET_IMPRESSION_SHARE,
        }

        strategy = goal_strategies.get(
            self.context.primary_goal,
            BidStrategyType.MAXIMIZE_CONVERSIONS
        )

        # If target CPA is set, use Target CPA
        if self.context.target_cpa and strategy == BidStrategyType.MAXIMIZE_CONVERSIONS:
            strategy = BidStrategyType.TARGET_CPA

        # If target ROAS is set, use Target ROAS
        if self.context.target_roas:
            strategy = BidStrategyType.TARGET_ROAS

        return strategy

    def _allocate_budgets(self, campaigns: List[CampaignBlueprint]) -> None:
        """Allocate total budget across campaigns."""
        if not campaigns:
            return

        total_daily = self._calculate_daily_budget()

        # If budgets already set, normalize to total
        current_total = sum(c.daily_budget for c in campaigns)

        if current_total > 0:
            # Scale to fit total budget
            scale = total_daily / current_total
            for campaign in campaigns:
                campaign.daily_budget = max(
                    campaign.daily_budget * scale,
                    self.context.min_daily_budget
                )
        else:
            # Equal distribution
            per_campaign = total_daily / len(campaigns)
            for campaign in campaigns:
                campaign.daily_budget = max(per_campaign, self.context.min_daily_budget)

    def _generate_implementation_notes(
        self,
        campaigns: List[CampaignBlueprint]
    ) -> List[str]:
        """Generate implementation guidance."""
        notes = [
            "Review and customize all ad copy before launching",
            "Set up conversion tracking before enabling campaigns",
            "Start with lower budgets and scale based on performance",
            "Monitor search terms report and add negatives in first 2 weeks",
            "Allow 2-3 weeks for learning phase before major optimizations",
        ]

        # Add specific notes based on plan
        total_keywords = sum(
            len(ag.keywords)
            for c in campaigns
            for ag in c.ad_groups
        )

        if total_keywords > 100:
            notes.append(f"Large keyword list ({total_keywords}). Consider phased rollout.")

        if any(c.bid_strategy == BidStrategyType.TARGET_CPA for c in campaigns):
            notes.append("Target CPA requires 15+ conversions/month for best results")

        return notes

    def _generate_prerequisites(self) -> List[str]:
        """Generate list of prerequisites before launching."""
        return [
            "Google Ads account with billing set up",
            "Conversion tracking configured and verified",
            "Landing pages reviewed and optimized",
            "Ad copy reviewed for policy compliance",
            "Budget approved and allocated",
            "Analytics connected to Google Ads",
        ]

    def build_pmax_campaign(
        self,
        asset_groups: List[Dict[str, Any]],
        daily_budget: float = 50.0
    ) -> Dict[str, Any]:
        """
        Build a Performance Max campaign structure.

        Performance Max requires different structure:
        - Asset groups instead of ad groups
        - Multiple asset types (images, videos, text)
        - Audience signals
        """
        return {
            "campaign_type": "PERFORMANCE_MAX",
            "name": f"{self.context.business_name} - Performance Max",
            "daily_budget": daily_budget,
            "bid_strategy": "MAXIMIZE_CONVERSIONS",
            "target_cpa": self.context.target_cpa,
            "locations": self.context.target_locations,
            "languages": self.context.target_languages,
            "asset_groups": asset_groups,
            "final_url_expansion": True,
            "notes": [
                "Performance Max uses machine learning to optimize across all Google channels",
                "Requires diverse assets: headlines, descriptions, images, logos",
                "Allow 4-6 weeks for algorithm learning",
                "Cannot control individual placements",
            ],
        }

    def validate_plan(self, plan: CampaignPlan) -> Dict[str, Any]:
        """Validate a campaign plan before implementation."""
        issues = []
        warnings = []

        for campaign in plan.campaigns:
            campaign.validate()

            if not campaign.is_valid:
                issues.extend([
                    f"Campaign '{campaign.name}': {err}"
                    for err in campaign.validation_errors
                ])

            # Check budget
            if campaign.daily_budget < self.context.min_daily_budget:
                warnings.append(
                    f"Campaign '{campaign.name}' budget ${campaign.daily_budget:.2f} "
                    f"is below recommended minimum ${self.context.min_daily_budget:.2f}"
                )

            # Check ad group count
            if len(campaign.ad_groups) > 20:
                warnings.append(
                    f"Campaign '{campaign.name}' has {len(campaign.ad_groups)} ad groups. "
                    "Consider splitting into multiple campaigns."
                )

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "ready_to_implement": len(issues) == 0,
        }
