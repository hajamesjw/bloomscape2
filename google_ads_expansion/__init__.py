"""
Google Ads Expansion System

A creative expansion system for generating new keywords, ad copy,
campaigns, and assets to grow Google Ads accounts.

This complements the Intelligence System (optimization) by handling growth:
- Intelligence System: Makes existing campaigns more efficient
- Expansion System: Creates new opportunities for growth

Usage:
    from google_ads_expansion import ExpansionEngine, BusinessContext

    context = BusinessContext(
        business_name="ABC Plumbing",
        business_type="plumbing",
        website_url="https://abcplumbing.com",
        monthly_budget=3000,
    )

    engine = ExpansionEngine(context)
    plan = engine.create_expansion_plan(seed_keywords=["plumber", "plumbing services"])

    print(engine.generate_report(plan))
"""

__version__ = "1.0.0"

from .main import (
    ExpansionEngine,
    BusinessContext,
    ExpansionPlanResult,
)

from .models import (
    KeywordIdea,
    KeywordCluster,
    KeywordExpansionPlan,
    HeadlineIdea,
    DescriptionIdea,
    AdCopySet,
    AdVariation,
    CampaignBlueprint,
    AdGroupBlueprint,
    CampaignPlan,
    Competitor,
    CompetitorInsight,
    CompetitiveGap,
)

from .generators import (
    KeywordExpander,
    AdCopyGenerator,
    AssetVariationGenerator,
)

from .builders import CampaignBuilder

from .research import CompetitorAnalyzer

__all__ = [
    # Main
    "ExpansionEngine",
    "BusinessContext",
    "ExpansionPlanResult",
    # Models
    "KeywordIdea",
    "KeywordCluster",
    "KeywordExpansionPlan",
    "HeadlineIdea",
    "DescriptionIdea",
    "AdCopySet",
    "AdVariation",
    "CampaignBlueprint",
    "AdGroupBlueprint",
    "CampaignPlan",
    "Competitor",
    "CompetitorInsight",
    "CompetitiveGap",
    # Generators
    "KeywordExpander",
    "AdCopyGenerator",
    "AssetVariationGenerator",
    # Builders
    "CampaignBuilder",
    # Research
    "CompetitorAnalyzer",
]
