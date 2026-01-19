"""Entity data models for Google Ads objects."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from .metrics import Metrics


class EntityStatus(Enum):
    """Status of a Google Ads entity."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class BidStrategyType(Enum):
    """Bid strategy types."""
    MANUAL_CPC = "MANUAL_CPC"
    ENHANCED_CPC = "ENHANCED_CPC"
    MAXIMIZE_CLICKS = "MAXIMIZE_CLICKS"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    MAXIMIZE_CONVERSION_VALUE = "MAXIMIZE_CONVERSION_VALUE"
    TARGET_CPA = "TARGET_CPA"
    TARGET_ROAS = "TARGET_ROAS"
    TARGET_IMPRESSION_SHARE = "TARGET_IMPRESSION_SHARE"


class MatchType(Enum):
    """Keyword match types."""
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


class DeviceType(Enum):
    """Device types."""
    DESKTOP = "DESKTOP"
    MOBILE = "MOBILE"
    TABLET = "TABLET"
    CONNECTED_TV = "CONNECTED_TV"


@dataclass
class Campaign:
    """Campaign entity."""

    id: str
    name: str
    status: EntityStatus
    budget_amount: float
    budget_type: str = "DAILY"
    bid_strategy_type: Optional[BidStrategyType] = None
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Performance data
    metrics: Optional[Metrics] = None
    metrics_history: List[Metrics] = field(default_factory=list)

    # Analysis metadata
    is_in_learning: bool = False
    learning_reason: Optional[str] = None
    days_since_last_change: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "budget_amount": self.budget_amount,
            "bid_strategy_type": self.bid_strategy_type.value if self.bid_strategy_type else None,
            "target_cpa": self.target_cpa,
            "target_roas": self.target_roas,
            "is_in_learning": self.is_in_learning,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class AdGroup:
    """Ad group entity."""

    id: str
    campaign_id: str
    name: str
    status: EntityStatus
    cpc_bid: Optional[float] = None

    metrics: Optional[Metrics] = None
    metrics_history: List[Metrics] = field(default_factory=list)

    is_in_learning: bool = False
    days_since_last_change: Optional[int] = None


@dataclass
class Keyword:
    """Keyword entity."""

    id: str
    ad_group_id: str
    campaign_id: str
    text: str
    match_type: MatchType
    status: EntityStatus
    cpc_bid: Optional[float] = None

    # Quality metrics
    quality_score: Optional[int] = None
    expected_ctr: Optional[str] = None
    ad_relevance: Optional[str] = None
    landing_page_experience: Optional[str] = None

    metrics: Optional[Metrics] = None
    metrics_history: List[Metrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ad_group_id": self.ad_group_id,
            "text": self.text,
            "match_type": self.match_type.value,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class Ad:
    """Ad entity."""

    id: str
    ad_group_id: str
    campaign_id: str
    ad_type: str
    status: EntityStatus
    headlines: List[str] = field(default_factory=list)
    descriptions: List[str] = field(default_factory=list)
    final_urls: List[str] = field(default_factory=list)

    # RSA-specific
    asset_performance: Dict[str, str] = field(default_factory=dict)  # asset -> "BEST"/"GOOD"/"LOW"

    metrics: Optional[Metrics] = None
    metrics_history: List[Metrics] = field(default_factory=list)


@dataclass
class SearchTerm:
    """Search term report entry."""

    query: str
    keyword_id: str
    keyword_text: str
    ad_group_id: str
    campaign_id: str

    metrics: Optional[Metrics] = None

    # Analysis flags
    is_negative_candidate: bool = False
    is_promotion_candidate: bool = False
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "keyword_text": self.keyword_text,
            "is_negative_candidate": self.is_negative_candidate,
            "is_promotion_candidate": self.is_promotion_candidate,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class GeoPerformance:
    """Geographic performance data."""

    location_id: str
    location_name: str
    location_type: str  # country, region, city
    campaign_id: str

    metrics: Optional[Metrics] = None

    # Analysis results
    performance_vs_average: float = 0.0  # % difference from campaign average
    is_exclusion_candidate: bool = False
    is_expansion_candidate: bool = False
    recommended_bid_modifier: Optional[float] = None


@dataclass
class AudiencePerformance:
    """Audience segment performance data."""

    audience_id: str
    audience_name: str
    audience_type: str  # in_market, affinity, remarketing, etc.
    campaign_id: str
    ad_group_id: Optional[str] = None

    metrics: Optional[Metrics] = None

    # Analysis results
    performance_vs_baseline: float = 0.0
    recommended_bid_modifier: Optional[float] = None


@dataclass
class DevicePerformance:
    """Device-level performance data."""

    device: DeviceType
    campaign_id: str

    metrics: Optional[Metrics] = None

    # Cross-device attribution
    assisted_conversions: float = 0.0
    assisted_conversion_value: float = 0.0

    recommended_bid_modifier: Optional[float] = None


@dataclass
class HourlyPerformance:
    """Hour-of-day performance data."""

    hour: int  # 0-23
    day_of_week: int  # 0-6 (Monday=0)
    campaign_id: str

    metrics: Optional[Metrics] = None

    performance_vs_average: float = 0.0
    recommended_bid_modifier: Optional[float] = None


@dataclass
class Extension:
    """Ad extension/asset performance."""

    id: str
    extension_type: str  # sitelink, callout, structured_snippet, etc.
    text: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None

    metrics: Optional[Metrics] = None

    ctr_lift: Optional[float] = None  # CTR improvement when shown
