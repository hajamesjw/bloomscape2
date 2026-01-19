"""Keyword expansion data models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class KeywordIntent(Enum):
    """Search intent classification."""
    TRANSACTIONAL = "transactional"  # Ready to buy: "buy", "price", "near me"
    COMMERCIAL = "commercial"         # Researching: "best", "review", "vs"
    INFORMATIONAL = "informational"   # Learning: "how to", "what is"
    NAVIGATIONAL = "navigational"     # Looking for specific brand/site


class KeywordSource(Enum):
    """Where the keyword idea came from."""
    SEARCH_TERM_REPORT = "search_term_report"
    KEYWORD_PLANNER = "keyword_planner"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    SEMANTIC_EXPANSION = "semantic_expansion"
    AI_GENERATED = "ai_generated"
    MANUAL = "manual"


@dataclass
class KeywordIdea:
    """A single keyword idea with research data."""

    keyword: str
    match_type: str = "PHRASE"  # EXACT, PHRASE, BROAD

    # Source and reasoning
    source: KeywordSource = KeywordSource.MANUAL
    source_keyword: Optional[str] = None  # If derived from existing keyword
    reasoning: str = ""

    # Search metrics (from Keyword Planner)
    avg_monthly_searches: Optional[int] = None
    competition: Optional[str] = None  # LOW, MEDIUM, HIGH
    competition_index: Optional[float] = None  # 0-100
    suggested_bid_low: Optional[float] = None
    suggested_bid_high: Optional[float] = None

    # Intent classification
    intent: Optional[KeywordIntent] = None
    intent_confidence: float = 0.0

    # Quality scores
    relevance_score: float = 0.0  # How relevant to business (0-1)
    opportunity_score: float = 0.0  # Volume × relevance / competition

    # Targeting
    suggested_campaign: Optional[str] = None
    suggested_ad_group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "match_type": self.match_type,
            "source": self.source.value,
            "avg_monthly_searches": self.avg_monthly_searches,
            "competition": self.competition,
            "suggested_bid": f"${self.suggested_bid_low}-${self.suggested_bid_high}" if self.suggested_bid_low else None,
            "intent": self.intent.value if self.intent else None,
            "relevance_score": round(self.relevance_score, 2),
            "opportunity_score": round(self.opportunity_score, 2),
            "reasoning": self.reasoning,
        }


@dataclass
class KeywordCluster:
    """A group of related keywords (for ad group creation)."""

    name: str
    theme: str
    keywords: List[KeywordIdea] = field(default_factory=list)

    # Cluster metrics
    total_search_volume: int = 0
    avg_competition: float = 0.0
    avg_suggested_bid: float = 0.0

    # Recommendations
    suggested_ad_group_name: str = ""
    suggested_headlines: List[str] = field(default_factory=list)

    def add_keyword(self, keyword: KeywordIdea) -> None:
        """Add keyword and update cluster metrics."""
        self.keywords.append(keyword)
        self._recalculate_metrics()

    def _recalculate_metrics(self) -> None:
        """Recalculate cluster-level metrics."""
        if not self.keywords:
            return

        volumes = [k.avg_monthly_searches or 0 for k in self.keywords]
        self.total_search_volume = sum(volumes)

        competitions = [k.competition_index or 50 for k in self.keywords]
        self.avg_competition = sum(competitions) / len(competitions)

        bids = [(k.suggested_bid_low or 0 + k.suggested_bid_high or 0) / 2
                for k in self.keywords if k.suggested_bid_low]
        self.avg_suggested_bid = sum(bids) / len(bids) if bids else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "theme": self.theme,
            "keyword_count": len(self.keywords),
            "total_search_volume": self.total_search_volume,
            "avg_competition": round(self.avg_competition, 1),
            "avg_suggested_bid": f"${self.avg_suggested_bid:.2f}",
            "keywords": [k.to_dict() for k in self.keywords],
            "suggested_ad_group_name": self.suggested_ad_group_name,
        }


@dataclass
class KeywordExpansionPlan:
    """Complete keyword expansion plan."""

    generated_at: str
    seed_keywords: List[str] = field(default_factory=list)

    # Results
    new_keywords: List[KeywordIdea] = field(default_factory=list)
    clusters: List[KeywordCluster] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)

    # Summary
    total_new_keywords: int = 0
    total_search_volume: int = 0
    estimated_clicks_per_month: int = 0
    estimated_cost_per_month: float = 0.0

    # By intent
    transactional_keywords: int = 0
    commercial_keywords: int = 0
    informational_keywords: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "seed_keywords": self.seed_keywords,
            "summary": {
                "total_new_keywords": self.total_new_keywords,
                "total_search_volume": self.total_search_volume,
                "estimated_clicks_per_month": self.estimated_clicks_per_month,
                "estimated_cost_per_month": f"${self.estimated_cost_per_month:.2f}",
                "by_intent": {
                    "transactional": self.transactional_keywords,
                    "commercial": self.commercial_keywords,
                    "informational": self.informational_keywords,
                },
            },
            "clusters": [c.to_dict() for c in self.clusters],
            "negative_keywords": self.negative_keywords,
        }
