"""Configuration for the Google Ads Expansion System."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class KeywordExpansionConfig:
    """Configuration for keyword expansion."""

    # Minimum metrics for seed keywords
    MIN_SEED_CONVERSIONS: int = 5
    MIN_SEED_CLICKS: int = 50

    # Expansion limits
    MAX_KEYWORDS_PER_AD_GROUP: int = 20
    MAX_NEW_KEYWORDS_PER_RUN: int = 50

    # Quality thresholds
    MIN_SEARCH_VOLUME: int = 100
    MAX_COMPETITION: str = "HIGH"  # LOW, MEDIUM, HIGH
    MAX_SUGGESTED_BID: float = 50.0

    # Match type preferences
    DEFAULT_MATCH_TYPE: str = "PHRASE"
    USE_EXACT_FOR_HIGH_INTENT: bool = True


@dataclass
class AdCopyConfig:
    """Configuration for ad copy generation."""

    # RSA limits (Google's limits)
    MAX_HEADLINES: int = 15
    MAX_DESCRIPTIONS: int = 4
    HEADLINE_MAX_LENGTH: int = 30
    DESCRIPTION_MAX_LENGTH: int = 90

    # Generation settings
    MIN_HEADLINES_PER_AD: int = 8
    MIN_DESCRIPTIONS_PER_AD: int = 3

    # Variation settings
    GENERATE_VARIATIONS: int = 3  # Number of ad variations to create

    # Content guidelines
    INCLUDE_CTA: bool = True
    INCLUDE_KEYWORDS: bool = True
    INCLUDE_BENEFITS: bool = True
    INCLUDE_SOCIAL_PROOF: bool = True


@dataclass
class CampaignBuilderConfig:
    """Configuration for campaign building."""

    # Budget settings
    DEFAULT_DAILY_BUDGET: float = 50.0
    MIN_DAILY_BUDGET: float = 10.0

    # Bid strategy
    DEFAULT_BID_STRATEGY: str = "MAXIMIZE_CONVERSIONS"
    FALLBACK_BID_STRATEGY: str = "MANUAL_CPC"

    # Structure
    MAX_AD_GROUPS_PER_CAMPAIGN: int = 10
    MAX_KEYWORDS_PER_AD_GROUP: int = 20
    MIN_ADS_PER_AD_GROUP: int = 2

    # Targeting defaults
    DEFAULT_LOCATIONS: List[str] = field(default_factory=lambda: ["United States"])
    DEFAULT_LANGUAGES: List[str] = field(default_factory=lambda: ["English"])


@dataclass
class CompetitorConfig:
    """Configuration for competitor research."""

    # Auction insights thresholds
    MIN_OVERLAP_RATE: float = 10.0  # Minimum % overlap to consider competitor

    # Research depth
    ANALYZE_TOP_COMPETITORS: int = 10

    # Alerts
    ALERT_ON_NEW_COMPETITOR: bool = True
    ALERT_ON_AGGRESSION_INCREASE: float = 20.0  # % increase in impression share


@dataclass
class ExpansionConfig:
    """Main configuration container for expansion system."""

    keywords: KeywordExpansionConfig = field(default_factory=KeywordExpansionConfig)
    ad_copy: AdCopyConfig = field(default_factory=AdCopyConfig)
    campaigns: CampaignBuilderConfig = field(default_factory=CampaignBuilderConfig)
    competitors: CompetitorConfig = field(default_factory=CompetitorConfig)

    # Paths
    data_dir: Path = Path("./data")
    output_dir: Path = Path("./expansion_output")

    # API settings (shared with intelligence system)
    customer_id: str = ""

    # AI/LLM settings for copy generation
    use_ai_copy_generation: bool = True
    ai_model: str = "claude"  # or "gpt-4", "gemini"
    ai_api_key: str = ""

    @classmethod
    def from_env(cls) -> "ExpansionConfig":
        """Load configuration from environment variables."""
        import os

        config = cls()
        config.customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
        config.ai_api_key = os.getenv("AI_API_KEY", "")

        return config


DEFAULT_EXPANSION_CONFIG = ExpansionConfig()
