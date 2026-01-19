"""
Google Ads Expansion System - Main Orchestration

This system complements the Intelligence System by creating NEW content:
- Intelligence System: Optimizes existing campaigns (finds waste, suggests improvements)
- Expansion System: Creates new content (keywords, ads, campaigns, assets)

Usage:
    from google_ads_expansion import ExpansionEngine

    engine = ExpansionEngine(business_context)
    plan = engine.create_expansion_plan(seed_keywords=["plumber", "plumbing services"])
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .generators.keyword_expander import KeywordExpander, ExpansionContext
from .generators.ad_copy_generator import AdCopyGenerator, AdCopyContext
from .generators.asset_generator import AssetVariationGenerator, AssetContext
from .builders.campaign_builder import CampaignBuilder, CampaignBuildContext
from .research.competitor_analyzer import CompetitorAnalyzer, CompetitorAnalysisContext
from .models.keywords import KeywordExpansionPlan, KeywordCluster
from .models.ads import AdCopySet
from .models.campaigns import CampaignPlan
from .models.competitors import CompetitorInsight
from .utils.validators import validate_campaign


@dataclass
class BusinessContext:
    """Complete business context for expansion."""

    # Basic info
    business_name: str
    business_type: str
    website_url: str

    # Products/Services
    products_services: List[str] = field(default_factory=list)

    # Value propositions
    unique_selling_points: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)

    # Social proof
    years_in_business: Optional[int] = None
    customer_count: Optional[str] = None
    rating: Optional[str] = None
    awards: List[str] = field(default_factory=list)

    # Offers
    current_offers: List[str] = field(default_factory=list)
    guarantees: List[str] = field(default_factory=list)

    # Targeting
    target_locations: List[str] = field(default_factory=list)
    target_languages: List[str] = field(default_factory=list)
    target_audience: Optional[str] = None

    # Competitors
    known_competitors: List[str] = field(default_factory=list)

    # Budget
    monthly_budget: float = 3000.0
    primary_goal: str = "conversions"
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None

    # Contact
    phone_number: Optional[str] = None

    # Site structure
    pages: Dict[str, str] = field(default_factory=dict)  # {"About": "/about"}
    services_with_prices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExpansionPlanResult:
    """Complete expansion plan with all generated content."""

    generated_at: str
    business_name: str

    # Generated content
    keyword_plan: Optional[KeywordExpansionPlan] = None
    ad_copy_sets: List[AdCopySet] = field(default_factory=list)
    campaign_plan: Optional[CampaignPlan] = None
    assets: Dict[str, Any] = field(default_factory=dict)
    competitor_insight: Optional[CompetitorInsight] = None

    # Summary
    total_keywords: int = 0
    total_ads: int = 0
    total_campaigns: int = 0

    # Validation
    validation_results: Dict[str, Any] = field(default_factory=dict)
    is_ready: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "generated_at": self.generated_at,
            "business_name": self.business_name,
            "summary": {
                "total_keywords": self.total_keywords,
                "total_ads": self.total_ads,
                "total_campaigns": self.total_campaigns,
                "is_ready": self.is_ready,
            },
            "keyword_plan": self.keyword_plan.to_dict() if self.keyword_plan else None,
            "ad_copy_sets": [a.to_dict() for a in self.ad_copy_sets],
            "campaign_plan": self.campaign_plan.to_dict() if self.campaign_plan else None,
            "assets": self.assets,
            "competitor_insight": self.competitor_insight.to_dict() if self.competitor_insight else None,
            "validation": self.validation_results,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export as formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ExpansionEngine:
    """Main orchestration for the Google Ads Expansion System."""

    def __init__(self, context: BusinessContext):
        """
        Initialize the expansion engine with business context.

        Args:
            context: Complete business context for generating content
        """
        self.context = context

        # Initialize components with appropriate contexts
        self._init_components()

    def _init_components(self):
        """Initialize all component generators and builders."""
        # Keyword expander
        self.keyword_expander = KeywordExpander(
            ExpansionContext(
                business_type=self.context.business_type,
                business_name=self.context.business_name,
                location=self.context.target_locations[0] if self.context.target_locations else None,
                target_audience=self.context.target_audience,
                products_services=self.context.products_services,
                competitors=self.context.known_competitors,
            )
        )

        # Ad copy generator
        self.ad_copy_generator = AdCopyGenerator(
            AdCopyContext(
                business_name=self.context.business_name,
                business_type=self.context.business_type,
                unique_selling_points=self.context.unique_selling_points,
                benefits=self.context.benefits,
                features=self.context.features,
                years_in_business=self.context.years_in_business,
                customer_count=self.context.customer_count,
                rating=self.context.rating,
                awards=self.context.awards,
                current_offers=self.context.current_offers,
                guarantees=self.context.guarantees,
                phone_number=self.context.phone_number,
            )
        )

        # Asset generator
        self.asset_generator = AssetVariationGenerator(
            AssetContext(
                business_name=self.context.business_name,
                website_url=self.context.website_url,
                phone_number=self.context.phone_number,
                pages=self.context.pages,
                services=self.context.services_with_prices,
                unique_selling_points=self.context.unique_selling_points,
                guarantees=self.context.guarantees,
                features=self.context.features,
            )
        )

        # Campaign builder
        self.campaign_builder = CampaignBuilder(
            CampaignBuildContext(
                business_name=self.context.business_name,
                business_type=self.context.business_type,
                website_url=self.context.website_url,
                monthly_budget=self.context.monthly_budget,
                primary_goal=self.context.primary_goal,
                target_cpa=self.context.target_cpa,
                target_roas=self.context.target_roas,
                target_locations=self.context.target_locations,
                target_languages=self.context.target_languages,
                unique_selling_points=self.context.unique_selling_points,
                benefits=self.context.benefits,
                features=self.context.features,
            )
        )

        # Competitor analyzer
        self.competitor_analyzer = CompetitorAnalyzer(
            CompetitorAnalysisContext(
                our_domain=self.context.website_url.replace("https://", "").replace("http://", "").split("/")[0],
                known_competitors=self.context.known_competitors,
            )
        )

    def create_expansion_plan(
        self,
        seed_keywords: List[str],
        include_competitor_analysis: bool = True,
        campaign_structure: str = "single"
    ) -> ExpansionPlanResult:
        """
        Create a complete expansion plan from seed keywords.

        This is the main entry point that orchestrates all components.

        Args:
            seed_keywords: Starting keywords to expand from
            include_competitor_analysis: Whether to include competitor insights
            campaign_structure: "single", "by_intent", or "by_theme"

        Returns:
            Complete expansion plan with all generated content
        """
        result = ExpansionPlanResult(
            generated_at=datetime.now().isoformat(),
            business_name=self.context.business_name,
        )

        # Step 1: Expand keywords
        print("Step 1/5: Expanding keywords...")
        keyword_plan = self.keyword_expander.expand_keywords(
            seed_keywords=seed_keywords,
            strategies=["modifier", "question", "intent", "semantic"],
        )
        result.keyword_plan = keyword_plan
        result.total_keywords = len(keyword_plan.new_keywords)
        print(f"  Generated {result.total_keywords} keywords in {len(keyword_plan.clusters)} clusters")

        # Step 2: Generate ad copy for each cluster
        print("Step 2/5: Generating ad copy...")
        ad_copy_sets = []
        for cluster in keyword_plan.clusters:
            ads = self.ad_copy_generator.generate_for_cluster(
                cluster=cluster,
                final_url=self.context.website_url,
            )
            ad_copy_sets.extend(ads)
        result.ad_copy_sets = ad_copy_sets
        result.total_ads = len(ad_copy_sets)
        print(f"  Generated {result.total_ads} ad copy sets")

        # Step 3: Build campaign structure
        print("Step 3/5: Building campaign structure...")
        campaign_plan = self.campaign_builder.build_campaign_plan(
            keyword_clusters=keyword_plan.clusters,
            ad_copy_sets=ad_copy_sets,
            campaign_structure=campaign_structure,
        )
        result.campaign_plan = campaign_plan
        result.total_campaigns = len(campaign_plan.campaigns)
        print(f"  Built {result.total_campaigns} campaigns")

        # Step 4: Generate assets (sitelinks, callouts, etc.)
        print("Step 4/5: Generating ad assets...")
        assets = self.asset_generator.generate_all_assets()
        result.assets = self.asset_generator.to_dict(assets)
        print(f"  Generated {result.assets['validation']['total_assets']} assets")

        # Step 5: Competitor analysis (optional)
        if include_competitor_analysis and self.context.known_competitors:
            print("Step 5/5: Analyzing competitors...")
            # Discover competitor keywords
            competitor_keywords = self.competitor_analyzer.discover_competitor_keywords(
                competitor_domains=self.context.known_competitors,
                seed_keywords=seed_keywords,
            )
            # Add to keyword plan
            keyword_plan.new_keywords.extend(competitor_keywords)
            print(f"  Discovered {len(competitor_keywords)} competitor-related keywords")
        else:
            print("Step 5/5: Skipping competitor analysis (no competitors specified)")

        # Validate everything
        print("\nValidating plan...")
        result.validation_results = self._validate_plan(result)
        result.is_ready = result.validation_results.get("is_ready", False)

        if result.is_ready:
            print("✓ Plan is ready for implementation")
        else:
            print("✗ Plan has issues that need to be addressed")

        return result

    def expand_keywords_only(
        self,
        seed_keywords: List[str],
        strategies: Optional[List[str]] = None
    ) -> KeywordExpansionPlan:
        """
        Just expand keywords without building full campaigns.

        Useful for keyword research phase.
        """
        return self.keyword_expander.expand_keywords(
            seed_keywords=seed_keywords,
            strategies=strategies or ["modifier", "question", "intent", "semantic"],
        )

    def generate_ads_only(
        self,
        keywords: List[str],
        final_url: str
    ) -> List[AdCopySet]:
        """
        Just generate ad copy for specific keywords.

        Useful for creating ads for existing campaigns.
        """
        return [
            self.ad_copy_generator.generate_ad_copy_set(
                target_keyword=kw,
                final_url=final_url,
            )
            for kw in keywords
        ]

    def generate_assets_only(self) -> Dict[str, Any]:
        """
        Just generate ad assets (extensions).

        Useful for improving existing campaigns.
        """
        assets = self.asset_generator.generate_all_assets()
        return self.asset_generator.to_dict(assets)

    def _validate_plan(self, result: ExpansionPlanResult) -> Dict[str, Any]:
        """Validate the complete expansion plan."""
        issues = []
        warnings = []

        # Validate campaigns
        if result.campaign_plan:
            for campaign in result.campaign_plan.campaigns:
                validation = validate_campaign(campaign)
                if not validation["is_valid"]:
                    issues.extend(validation["issues"])
                warnings.extend(validation.get("warnings", []))

        # Check keyword quality
        if result.keyword_plan:
            low_intent_ratio = (
                result.keyword_plan.informational_keywords /
                max(result.total_keywords, 1)
            )
            if low_intent_ratio > 0.5:
                warnings.append(
                    f"High ratio of informational keywords ({low_intent_ratio:.0%}). "
                    "Consider focusing on transactional/commercial intent."
                )

        # Check ad coverage
        if result.total_ads < result.total_campaigns:
            issues.append({
                "field": "ads",
                "issue": "Not enough ads generated for all campaigns",
            })

        return {
            "is_ready": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "summary": {
                "total_keywords": result.total_keywords,
                "total_ads": result.total_ads,
                "total_campaigns": result.total_campaigns,
            },
        }

    def generate_report(self, result: ExpansionPlanResult) -> str:
        """Generate a human-readable report of the expansion plan."""
        lines = [
            "=" * 70,
            "GOOGLE ADS EXPANSION PLAN",
            f"Business: {result.business_name}",
            f"Generated: {result.generated_at}",
            "=" * 70,
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Keywords Generated: {result.total_keywords}",
            f"Total Ad Copy Sets: {result.total_ads}",
            f"Total Campaigns: {result.total_campaigns}",
            f"Plan Status: {'Ready ✓' if result.is_ready else 'Needs Review ✗'}",
            "",
        ]

        # Keyword breakdown
        if result.keyword_plan:
            lines.extend([
                "KEYWORD BREAKDOWN",
                "-" * 40,
                f"Transactional (high intent): {result.keyword_plan.transactional_keywords}",
                f"Commercial (research): {result.keyword_plan.commercial_keywords}",
                f"Informational (awareness): {result.keyword_plan.informational_keywords}",
                f"Clusters Created: {len(result.keyword_plan.clusters)}",
                "",
            ])

        # Campaign overview
        if result.campaign_plan:
            lines.extend([
                "CAMPAIGN STRUCTURE",
                "-" * 40,
            ])
            for campaign in result.campaign_plan.campaigns:
                lines.append(f"\n  Campaign: {campaign.name}")
                lines.append(f"  Daily Budget: ${campaign.daily_budget:.2f}")
                lines.append(f"  Bid Strategy: {campaign.bid_strategy.value}")
                lines.append(f"  Ad Groups: {len(campaign.ad_groups)}")

        # Assets
        if result.assets:
            validation = result.assets.get("validation", {})
            lines.extend([
                "",
                "ASSETS GENERATED",
                "-" * 40,
                f"Total Assets: {validation.get('total_assets', 0)}",
                f"Valid Assets: {validation.get('valid_assets', 0)}",
            ])

        # Validation issues
        if result.validation_results.get("issues"):
            lines.extend([
                "",
                "ISSUES TO ADDRESS",
                "-" * 40,
            ])
            for issue in result.validation_results["issues"]:
                lines.append(f"  • {issue.get('field', 'Unknown')}: {issue.get('issue', 'Error')}")

        # Warnings
        if result.validation_results.get("warnings"):
            lines.extend([
                "",
                "WARNINGS",
                "-" * 40,
            ])
            for warning in result.validation_results["warnings"]:
                lines.append(f"  • {warning}")

        # Next steps
        lines.extend([
            "",
            "NEXT STEPS",
            "-" * 40,
            "1. Review generated ad copy and customize for your brand voice",
            "2. Verify landing page URLs are correct",
            "3. Set up conversion tracking in Google Ads",
            "4. Review and adjust budgets as needed",
            "5. Import into Google Ads Editor or create manually",
            "",
            "=" * 70,
        ])

        return "\n".join(lines)
