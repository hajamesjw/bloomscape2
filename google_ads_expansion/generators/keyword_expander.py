"""Keyword expansion generator.

Expands seed keywords into comprehensive keyword lists using multiple strategies:
- Semantic expansion (synonyms, related terms)
- Modifier expansion (prefixes, suffixes)
- Question expansion (how, what, where, etc.)
- Intent-based expansion
- Competitor keyword discovery
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..models.keywords import (
    KeywordIdea,
    KeywordCluster,
    KeywordExpansionPlan,
    KeywordIntent,
    KeywordSource,
)
from ..config import EXPANSION_CONFIG


@dataclass
class ExpansionContext:
    """Context for keyword expansion."""

    business_type: str
    business_name: str
    location: Optional[str] = None
    target_audience: Optional[str] = None
    products_services: List[str] = None
    competitors: List[str] = None

    def __post_init__(self):
        if self.products_services is None:
            self.products_services = []
        if self.competitors is None:
            self.competitors = []


class KeywordExpander:
    """Generates expanded keyword lists from seed keywords."""

    # Common modifiers for different industries
    INTENT_MODIFIERS = {
        KeywordIntent.TRANSACTIONAL: [
            "buy", "purchase", "order", "price", "cost", "cheap", "affordable",
            "discount", "deal", "sale", "near me", "online", "shop", "store",
            "hire", "book", "schedule", "get", "find"
        ],
        KeywordIntent.COMMERCIAL: [
            "best", "top", "review", "reviews", "vs", "versus", "compare",
            "comparison", "alternative", "alternatives", "recommended",
            "rated", "professional", "quality", "premium", "trusted"
        ],
        KeywordIntent.INFORMATIONAL: [
            "how to", "what is", "guide", "tutorial", "tips", "ideas",
            "examples", "definition", "meaning", "benefits", "pros and cons",
            "learn", "understand", "explained"
        ],
    }

    QUESTION_STARTERS = [
        "how to", "how do", "how can", "how much", "how long",
        "what is", "what are", "what does",
        "where to", "where can",
        "when to", "when should",
        "why do", "why should", "why is",
        "which", "who", "can I", "should I", "is it"
    ]

    LOCATION_MODIFIERS = [
        "near me", "nearby", "local", "in {city}", "{city}",
        "in my area", "closest", "nearest"
    ]

    def __init__(self, context: ExpansionContext):
        """Initialize with business context."""
        self.context = context
        self.config = EXPANSION_CONFIG["keyword_expansion"]

    def expand_keywords(
        self,
        seed_keywords: List[str],
        strategies: Optional[List[str]] = None,
        max_keywords_per_seed: int = 50
    ) -> KeywordExpansionPlan:
        """
        Expand seed keywords using multiple strategies.

        Args:
            seed_keywords: Base keywords to expand from
            strategies: Which expansion strategies to use
            max_keywords_per_seed: Maximum keywords to generate per seed

        Returns:
            Complete keyword expansion plan
        """
        if strategies is None:
            strategies = ["modifier", "question", "intent", "semantic"]

        all_keywords: List[KeywordIdea] = []

        for seed in seed_keywords:
            seed_keywords_list = []

            if "modifier" in strategies:
                seed_keywords_list.extend(
                    self._expand_with_modifiers(seed)
                )

            if "question" in strategies:
                seed_keywords_list.extend(
                    self._expand_with_questions(seed)
                )

            if "intent" in strategies:
                seed_keywords_list.extend(
                    self._expand_by_intent(seed)
                )

            if "semantic" in strategies:
                seed_keywords_list.extend(
                    self._expand_semantically(seed)
                )

            if "location" in strategies and self.context.location:
                seed_keywords_list.extend(
                    self._expand_with_locations(seed)
                )

            # Deduplicate and limit
            seen = set()
            unique_keywords = []
            for kw in seed_keywords_list:
                if kw.keyword.lower() not in seen:
                    seen.add(kw.keyword.lower())
                    unique_keywords.append(kw)

            all_keywords.extend(unique_keywords[:max_keywords_per_seed])

        # Cluster keywords by theme
        clusters = self._cluster_keywords(all_keywords)

        # Generate negative keywords
        negatives = self._generate_negative_keywords(seed_keywords)

        # Build expansion plan
        plan = KeywordExpansionPlan(
            generated_at=datetime.now().isoformat(),
            seed_keywords=seed_keywords,
            new_keywords=all_keywords,
            clusters=clusters,
            negative_keywords=negatives,
            total_new_keywords=len(all_keywords),
        )

        # Calculate intent breakdown
        plan.transactional_keywords = len([
            k for k in all_keywords if k.intent == KeywordIntent.TRANSACTIONAL
        ])
        plan.commercial_keywords = len([
            k for k in all_keywords if k.intent == KeywordIntent.COMMERCIAL
        ])
        plan.informational_keywords = len([
            k for k in all_keywords if k.intent == KeywordIntent.INFORMATIONAL
        ])

        return plan

    def _expand_with_modifiers(self, seed: str) -> List[KeywordIdea]:
        """Expand keyword with common modifiers."""
        keywords = []

        # Prefix modifiers
        prefixes = [
            "best", "top", "cheap", "affordable", "professional",
            "local", "online", "quality", "premium", "trusted",
            "certified", "licensed", "experienced", "expert"
        ]

        for prefix in prefixes:
            kw = f"{prefix} {seed}"
            keywords.append(KeywordIdea(
                keyword=kw,
                source=KeywordSource.SEMANTIC_EXPANSION,
                source_keyword=seed,
                reasoning=f"Prefix modifier '{prefix}' expansion",
                intent=self._classify_intent(kw),
            ))

        # Suffix modifiers
        suffixes = [
            "services", "company", "near me", "online", "cost",
            "prices", "reviews", "for sale", "deals", "specialists",
            "experts", "professionals", "contractors"
        ]

        for suffix in suffixes:
            kw = f"{seed} {suffix}"
            keywords.append(KeywordIdea(
                keyword=kw,
                source=KeywordSource.SEMANTIC_EXPANSION,
                source_keyword=seed,
                reasoning=f"Suffix modifier '{suffix}' expansion",
                intent=self._classify_intent(kw),
            ))

        return keywords

    def _expand_with_questions(self, seed: str) -> List[KeywordIdea]:
        """Expand keyword into question formats."""
        keywords = []

        for starter in self.QUESTION_STARTERS:
            # Create question variations
            variations = [
                f"{starter} {seed}",
                f"{starter} find {seed}",
                f"{starter} choose {seed}",
                f"{starter} {seed} work",
            ]

            for kw in variations:
                if len(kw) < 80:  # Keep reasonable length
                    keywords.append(KeywordIdea(
                        keyword=kw,
                        source=KeywordSource.SEMANTIC_EXPANSION,
                        source_keyword=seed,
                        reasoning=f"Question expansion with '{starter}'",
                        intent=KeywordIntent.INFORMATIONAL,
                        intent_confidence=0.9,
                    ))

        return keywords

    def _expand_by_intent(self, seed: str) -> List[KeywordIdea]:
        """Expand keyword with intent-specific modifiers."""
        keywords = []

        for intent, modifiers in self.INTENT_MODIFIERS.items():
            for modifier in modifiers:
                # Try both prefix and suffix positions
                variations = [
                    f"{modifier} {seed}",
                    f"{seed} {modifier}",
                ]

                for kw in variations:
                    if len(kw) < 80:
                        keywords.append(KeywordIdea(
                            keyword=kw,
                            source=KeywordSource.SEMANTIC_EXPANSION,
                            source_keyword=seed,
                            reasoning=f"Intent-based expansion ({intent.value})",
                            intent=intent,
                            intent_confidence=0.85,
                        ))

        return keywords

    def _expand_semantically(self, seed: str) -> List[KeywordIdea]:
        """
        Expand using semantic relationships.

        In production, this would use:
        - Word embeddings
        - Google's Keyword Planner API
        - Search term reports
        """
        keywords = []

        # Common semantic patterns
        patterns = [
            # Pluralization
            (seed, f"{seed}s"),
            (seed, f"{seed}es"),
            # Verb forms
            (seed, f"{seed}ing"),
            (seed, f"{seed}er"),
            (seed, f"{seed}ers"),
            # Related concepts
            (seed, f"{seed} service"),
            (seed, f"{seed} provider"),
            (seed, f"{seed} solution"),
            (seed, f"{seed} help"),
        ]

        for _, variation in patterns:
            if variation != seed:
                keywords.append(KeywordIdea(
                    keyword=variation,
                    source=KeywordSource.SEMANTIC_EXPANSION,
                    source_keyword=seed,
                    reasoning="Semantic variation",
                    intent=self._classify_intent(variation),
                ))

        # Add business-specific variations
        for product in self.context.products_services:
            combined = f"{product} {seed}"
            keywords.append(KeywordIdea(
                keyword=combined,
                source=KeywordSource.SEMANTIC_EXPANSION,
                source_keyword=seed,
                reasoning=f"Combined with product/service: {product}",
                intent=self._classify_intent(combined),
            ))

        return keywords

    def _expand_with_locations(self, seed: str) -> List[KeywordIdea]:
        """Expand keyword with location modifiers."""
        keywords = []
        location = self.context.location or ""

        for loc_mod in self.LOCATION_MODIFIERS:
            # Replace {city} placeholder with actual location
            loc_str = loc_mod.replace("{city}", location)
            kw = f"{seed} {loc_str}"

            keywords.append(KeywordIdea(
                keyword=kw,
                source=KeywordSource.SEMANTIC_EXPANSION,
                source_keyword=seed,
                reasoning=f"Location expansion: {loc_str}",
                intent=KeywordIntent.TRANSACTIONAL,
                intent_confidence=0.8,
            ))

        return keywords

    def _classify_intent(self, keyword: str) -> KeywordIntent:
        """Classify the search intent of a keyword."""
        keyword_lower = keyword.lower()

        # Check for transactional signals
        transactional_signals = [
            "buy", "purchase", "order", "price", "cost", "cheap",
            "discount", "deal", "sale", "near me", "hire", "book",
            "schedule", "get quote", "free estimate"
        ]
        if any(signal in keyword_lower for signal in transactional_signals):
            return KeywordIntent.TRANSACTIONAL

        # Check for commercial signals
        commercial_signals = [
            "best", "top", "review", "vs", "compare", "alternative",
            "recommended", "rated", "professional"
        ]
        if any(signal in keyword_lower for signal in commercial_signals):
            return KeywordIntent.COMMERCIAL

        # Check for informational signals
        informational_signals = [
            "how", "what", "why", "when", "where", "guide", "tutorial",
            "tips", "ideas", "learn", "definition", "meaning"
        ]
        if any(signal in keyword_lower for signal in informational_signals):
            return KeywordIntent.INFORMATIONAL

        # Default to commercial (most valuable for ads)
        return KeywordIntent.COMMERCIAL

    def _cluster_keywords(
        self,
        keywords: List[KeywordIdea]
    ) -> List[KeywordCluster]:
        """Group keywords into thematic clusters for ad groups."""
        clusters: Dict[str, KeywordCluster] = {}

        for kw in keywords:
            # Determine cluster based on intent and core term
            cluster_key = self._get_cluster_key(kw)

            if cluster_key not in clusters:
                clusters[cluster_key] = KeywordCluster(
                    name=cluster_key,
                    theme=kw.intent.value if kw.intent else "general",
                    suggested_ad_group_name=self._format_ad_group_name(cluster_key),
                )

            clusters[cluster_key].add_keyword(kw)

        # Generate suggested headlines for each cluster
        for cluster in clusters.values():
            cluster.suggested_headlines = self._generate_cluster_headlines(cluster)

        return list(clusters.values())

    def _get_cluster_key(self, keyword: KeywordIdea) -> str:
        """Determine which cluster a keyword belongs to."""
        # Simple clustering by intent + source keyword
        intent_str = keyword.intent.value if keyword.intent else "general"
        source = keyword.source_keyword or keyword.keyword.split()[0]
        return f"{source}_{intent_str}"

    def _format_ad_group_name(self, cluster_key: str) -> str:
        """Format cluster key into proper ad group name."""
        parts = cluster_key.split("_")
        # Capitalize and join
        return " - ".join(word.title() for word in parts)

    def _generate_cluster_headlines(self, cluster: KeywordCluster) -> List[str]:
        """Generate suggested headlines for a keyword cluster."""
        headlines = []

        # Get the most common/important keyword in cluster
        if cluster.keywords:
            main_kw = cluster.keywords[0].keyword

            # Intent-based headlines
            if cluster.theme == "transactional":
                headlines = [
                    f"Get {main_kw.title()} Today",
                    f"Affordable {main_kw.title()}",
                    f"Professional {main_kw.title()}",
                    f"Quality {main_kw.title()} Services",
                ]
            elif cluster.theme == "commercial":
                headlines = [
                    f"Top Rated {main_kw.title()}",
                    f"Best {main_kw.title()} Services",
                    f"Trusted {main_kw.title()} Experts",
                    f"#1 {main_kw.title()} Provider",
                ]
            else:
                headlines = [
                    f"Learn About {main_kw.title()}",
                    f"{main_kw.title()} Guide",
                    f"Expert {main_kw.title()} Tips",
                ]

        return headlines

    def _generate_negative_keywords(self, seed_keywords: List[str]) -> List[str]:
        """Generate recommended negative keywords to exclude."""
        negatives = []

        # Common negative keywords for most campaigns
        common_negatives = [
            "free", "cheap", "diy", "how to diy",
            "jobs", "career", "salary", "hiring",
            "training", "course", "certification", "school",
            "youtube", "video tutorial",
            "template", "sample", "example",
            "reddit", "forum", "wiki",
        ]

        negatives.extend(common_negatives)

        # Add competitor names as negatives (optional strategy)
        for competitor in self.context.competitors:
            negatives.append(competitor.lower())

        return list(set(negatives))

    def suggest_match_types(
        self,
        keyword: KeywordIdea
    ) -> List[Tuple[str, str]]:
        """
        Suggest match types for a keyword with reasoning.

        Returns list of (match_type, reasoning) tuples.
        """
        suggestions = []

        # High intent = exact match
        if keyword.intent == KeywordIntent.TRANSACTIONAL:
            suggestions.append((
                "EXACT",
                "High commercial intent - use exact match for precision"
            ))
            suggestions.append((
                "PHRASE",
                "Also add phrase match to capture variations"
            ))

        # Commercial = phrase match primarily
        elif keyword.intent == KeywordIntent.COMMERCIAL:
            suggestions.append((
                "PHRASE",
                "Commercial intent - phrase match balances reach and relevance"
            ))

        # Broad match for discovery
        if keyword.avg_monthly_searches and keyword.avg_monthly_searches < 100:
            suggestions.append((
                "BROAD",
                "Low volume keyword - use broad match to discover variations"
            ))

        return suggestions

    def estimate_keyword_metrics(
        self,
        keyword: KeywordIdea,
        industry_avg_cpc: float = 2.0,
        industry_avg_ctr: float = 0.03
    ) -> Dict[str, Any]:
        """
        Estimate keyword metrics when actual data isn't available.

        In production, use Google Keyword Planner API for real data.
        """
        # Estimate based on intent (transactional typically costs more)
        intent_multipliers = {
            KeywordIntent.TRANSACTIONAL: 1.5,
            KeywordIntent.COMMERCIAL: 1.2,
            KeywordIntent.INFORMATIONAL: 0.7,
            KeywordIntent.NAVIGATIONAL: 0.5,
        }

        multiplier = intent_multipliers.get(keyword.intent, 1.0)

        return {
            "estimated_cpc": round(industry_avg_cpc * multiplier, 2),
            "estimated_ctr": round(industry_avg_ctr * multiplier, 4),
            "confidence": "low",  # Estimates are low confidence
            "note": "Use Keyword Planner API for accurate metrics",
        }
