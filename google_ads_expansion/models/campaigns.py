"""Campaign building data models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from .keywords import KeywordIdea, KeywordCluster
from .ads import AdCopySet


class CampaignType(Enum):
    """Types of campaigns."""
    SEARCH = "SEARCH"
    DISPLAY = "DISPLAY"
    SHOPPING = "SHOPPING"
    VIDEO = "VIDEO"
    PERFORMANCE_MAX = "PERFORMANCE_MAX"


class BidStrategyType(Enum):
    """Bid strategy options."""
    MANUAL_CPC = "MANUAL_CPC"
    ENHANCED_CPC = "ENHANCED_CPC"
    MAXIMIZE_CLICKS = "MAXIMIZE_CLICKS"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    MAXIMIZE_CONVERSION_VALUE = "MAXIMIZE_CONVERSION_VALUE"
    TARGET_CPA = "TARGET_CPA"
    TARGET_ROAS = "TARGET_ROAS"
    TARGET_IMPRESSION_SHARE = "TARGET_IMPRESSION_SHARE"


@dataclass
class AdGroupBlueprint:
    """Blueprint for creating an ad group."""

    name: str
    theme: str

    # Keywords
    keywords: List[KeywordIdea] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)

    # Ads
    ads: List[AdCopySet] = field(default_factory=list)

    # Targeting
    audiences: List[str] = field(default_factory=list)

    # Bids
    default_cpc_bid: Optional[float] = None

    # Estimates
    estimated_impressions: int = 0
    estimated_clicks: int = 0
    estimated_cost: float = 0.0

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate ad group blueprint."""
        self.validation_errors = []

        if len(self.keywords) == 0:
            self.validation_errors.append("No keywords specified")

        if len(self.keywords) > 20:
            self.validation_errors.append(f"Too many keywords: {len(self.keywords)}/20 max")

        if len(self.ads) == 0:
            self.validation_errors.append("No ads specified")

        if len(self.ads) < 2:
            self.validation_errors.append("Recommend at least 2 ads for testing")

        # Validate each ad
        for ad in self.ads:
            if not ad.is_valid:
                self.validation_errors.append(f"Ad '{ad.name}' has errors")

        self.is_valid = len([e for e in self.validation_errors if "No " in e]) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "name": self.name,
            "theme": self.theme,
            "keywords": [k.to_dict() for k in self.keywords],
            "negative_keywords": self.negative_keywords,
            "ads": [a.to_dict() for a in self.ads],
            "audiences": self.audiences,
            "default_cpc_bid": f"${self.default_cpc_bid:.2f}" if self.default_cpc_bid else None,
            "estimates": {
                "impressions": self.estimated_impressions,
                "clicks": self.estimated_clicks,
                "cost": f"${self.estimated_cost:.2f}",
            },
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


@dataclass
class CampaignBlueprint:
    """Blueprint for creating a campaign."""

    name: str
    campaign_type: CampaignType = CampaignType.SEARCH

    # Budget
    daily_budget: float = 50.0

    # Bidding
    bid_strategy: BidStrategyType = BidStrategyType.MAXIMIZE_CONVERSIONS
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None

    # Ad groups
    ad_groups: List[AdGroupBlueprint] = field(default_factory=list)

    # Campaign-level negatives
    negative_keywords: List[str] = field(default_factory=list)

    # Targeting
    locations: List[str] = field(default_factory=list)
    location_exclusions: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)

    # Schedule
    ad_schedule: Optional[Dict[str, Any]] = None  # Day/hour targeting

    # Networks
    search_network: bool = True
    display_network: bool = False
    search_partners: bool = False

    # Estimates
    estimated_daily_impressions: int = 0
    estimated_daily_clicks: int = 0
    estimated_daily_conversions: float = 0.0
    estimated_daily_cost: float = 0.0

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate campaign blueprint."""
        self.validation_errors = []

        if self.daily_budget < 1:
            self.validation_errors.append("Daily budget must be at least $1")

        if len(self.ad_groups) == 0:
            self.validation_errors.append("No ad groups specified")

        if len(self.ad_groups) > 20:
            self.validation_errors.append(f"Too many ad groups: {len(self.ad_groups)}/20 recommended max")

        if len(self.locations) == 0:
            self.validation_errors.append("No locations specified")

        # Validate each ad group
        for ag in self.ad_groups:
            if not ag.validate():
                self.validation_errors.append(f"Ad group '{ag.name}' has errors")

        # Check bid strategy requirements
        if self.bid_strategy == BidStrategyType.TARGET_CPA and not self.target_cpa:
            self.validation_errors.append("Target CPA bid strategy requires target_cpa value")

        if self.bid_strategy == BidStrategyType.TARGET_ROAS and not self.target_roas:
            self.validation_errors.append("Target ROAS bid strategy requires target_roas value")

        self.is_valid = len([e for e in self.validation_errors if "No " in e or "must be" in e]) == 0
        return self.is_valid

    def calculate_estimates(self) -> None:
        """Calculate campaign-level estimates from ad groups."""
        self.estimated_daily_impressions = sum(ag.estimated_impressions for ag in self.ad_groups)
        self.estimated_daily_clicks = sum(ag.estimated_clicks for ag in self.ad_groups)
        self.estimated_daily_cost = min(
            sum(ag.estimated_cost for ag in self.ad_groups),
            self.daily_budget
        )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        self.calculate_estimates()

        return {
            "name": self.name,
            "campaign_type": self.campaign_type.value,
            "daily_budget": f"${self.daily_budget:.2f}",
            "bid_strategy": {
                "type": self.bid_strategy.value,
                "target_cpa": f"${self.target_cpa:.2f}" if self.target_cpa else None,
                "target_roas": f"{self.target_roas:.1f}x" if self.target_roas else None,
            },
            "targeting": {
                "locations": self.locations,
                "location_exclusions": self.location_exclusions,
                "languages": self.languages,
            },
            "networks": {
                "search": self.search_network,
                "display": self.display_network,
                "search_partners": self.search_partners,
            },
            "ad_groups": [ag.to_dict() for ag in self.ad_groups],
            "negative_keywords": self.negative_keywords,
            "estimates": {
                "daily_impressions": self.estimated_daily_impressions,
                "daily_clicks": self.estimated_daily_clicks,
                "daily_conversions": round(self.estimated_daily_conversions, 1),
                "daily_cost": f"${self.estimated_daily_cost:.2f}",
                "monthly_cost": f"${self.estimated_daily_cost * 30:.2f}",
            },
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


@dataclass
class CampaignPlan:
    """Complete campaign expansion plan."""

    generated_at: str
    plan_name: str

    # Campaigns to create
    campaigns: List[CampaignBlueprint] = field(default_factory=list)

    # Summary
    total_campaigns: int = 0
    total_ad_groups: int = 0
    total_keywords: int = 0
    total_ads: int = 0

    # Budget summary
    total_daily_budget: float = 0.0
    total_monthly_budget: float = 0.0

    # Estimates
    estimated_monthly_impressions: int = 0
    estimated_monthly_clicks: int = 0
    estimated_monthly_conversions: float = 0.0

    # Implementation
    implementation_notes: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)

    def calculate_summary(self) -> None:
        """Calculate plan summary from campaigns."""
        self.total_campaigns = len(self.campaigns)
        self.total_ad_groups = sum(len(c.ad_groups) for c in self.campaigns)
        self.total_keywords = sum(
            len(ag.keywords)
            for c in self.campaigns
            for ag in c.ad_groups
        )
        self.total_ads = sum(
            len(ag.ads)
            for c in self.campaigns
            for ag in c.ad_groups
        )

        self.total_daily_budget = sum(c.daily_budget for c in self.campaigns)
        self.total_monthly_budget = self.total_daily_budget * 30

        self.estimated_monthly_clicks = sum(
            c.estimated_daily_clicks * 30 for c in self.campaigns
        )

    def to_dict(self) -> Dict[str, Any]:
        self.calculate_summary()

        return {
            "generated_at": self.generated_at,
            "plan_name": self.plan_name,
            "summary": {
                "total_campaigns": self.total_campaigns,
                "total_ad_groups": self.total_ad_groups,
                "total_keywords": self.total_keywords,
                "total_ads": self.total_ads,
                "total_daily_budget": f"${self.total_daily_budget:.2f}",
                "total_monthly_budget": f"${self.total_monthly_budget:.2f}",
            },
            "estimates": {
                "monthly_impressions": self.estimated_monthly_impressions,
                "monthly_clicks": self.estimated_monthly_clicks,
                "monthly_conversions": round(self.estimated_monthly_conversions, 1),
            },
            "campaigns": [c.to_dict() for c in self.campaigns],
            "implementation_notes": self.implementation_notes,
            "prerequisites": self.prerequisites,
        }
