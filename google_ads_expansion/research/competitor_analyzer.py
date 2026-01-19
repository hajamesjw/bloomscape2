"""Competitor analyzer.

Analyzes competitor presence and identifies opportunities:
- Auction insights analysis
- Competitor keyword discovery
- Gap analysis
- Competitive positioning recommendations
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..models.competitors import (
    Competitor,
    CompetitorInsight,
    CompetitiveGap,
)
from ..models.keywords import KeywordIdea, KeywordSource, KeywordIntent
from ..config import EXPANSION_CONFIG


@dataclass
class AuctionInsightData:
    """Raw auction insight data from Google Ads API."""

    domain: str
    impression_share: float
    overlap_rate: float
    position_above_rate: float
    top_of_page_rate: float
    abs_top_of_page_rate: float
    outranking_share: float

    # Historical (if available)
    impression_share_7d_ago: Optional[float] = None
    impression_share_30d_ago: Optional[float] = None


@dataclass
class CompetitorAnalysisContext:
    """Context for competitor analysis."""

    our_domain: str
    our_campaigns: List[str] = field(default_factory=list)
    analysis_period_days: int = 30

    # Known competitors
    known_competitors: List[str] = field(default_factory=list)

    # Our performance
    our_impression_share: float = 0.0
    our_top_of_page_rate: float = 0.0
    our_avg_position: float = 0.0


class CompetitorAnalyzer:
    """Analyzes competitor landscape and identifies opportunities."""

    def __init__(self, context: CompetitorAnalysisContext):
        """Initialize with analysis context."""
        self.context = context
        self.config = EXPANSION_CONFIG["competitor_analysis"]

    def analyze_auction_insights(
        self,
        auction_data: List[AuctionInsightData]
    ) -> CompetitorInsight:
        """
        Analyze auction insights data to generate competitor intelligence.

        Args:
            auction_data: Raw auction insight data from API

        Returns:
            Complete competitor insight report
        """
        competitors = []

        for data in auction_data:
            if data.domain == self.context.our_domain:
                continue  # Skip our own domain

            competitor = Competitor(
                domain=data.domain,
                display_name=self._format_display_name(data.domain),
                impression_share=data.impression_share,
                overlap_rate=data.overlap_rate,
                position_above_rate=data.position_above_rate,
                top_of_page_rate=data.top_of_page_rate,
                outranking_share=data.outranking_share,
            )

            # Calculate trends
            if data.impression_share_7d_ago is not None:
                competitor.impression_share_7d_change = (
                    data.impression_share - data.impression_share_7d_ago
                )

            if data.impression_share_30d_ago is not None:
                competitor.impression_share_30d_change = (
                    data.impression_share - data.impression_share_30d_ago
                )

                # Determine trend direction
                if competitor.impression_share_30d_change > 5:
                    competitor.impression_share_trend = "increasing"
                elif competitor.impression_share_30d_change < -5:
                    competitor.impression_share_trend = "decreasing"
                else:
                    competitor.impression_share_trend = "stable"

                # Check if new competitor
                if data.impression_share_30d_ago == 0 and data.impression_share > 0:
                    competitor.is_new = True

            # Calculate threat level
            competitor.calculate_threat_level()
            competitors.append(competitor)

        # Sort by threat level and impression share
        threat_order = {"high": 0, "medium": 1, "low": 2}
        competitors.sort(
            key=lambda c: (threat_order.get(c.threat_level, 1), -c.impression_share)
        )

        # Build insight report
        insight = CompetitorInsight(
            generated_at=datetime.now().isoformat(),
            analysis_period_days=self.context.analysis_period_days,
            our_impression_share=self.context.our_impression_share,
            our_top_of_page_rate=self.context.our_top_of_page_rate,
            competitors=competitors,
            new_competitors=[c for c in competitors if c.is_new],
            aggressive_competitors=[
                c for c in competitors
                if c.threat_level == "high" or c.impression_share_30d_change > 10
            ],
        )

        # Identify gaps and opportunities
        insight.competitive_gaps = self._identify_gaps(competitors)

        # Generate recommendations
        insight.defensive_actions = self._generate_defensive_actions(competitors)
        insight.offensive_actions = self._generate_offensive_actions(competitors)

        return insight

    def _format_display_name(self, domain: str) -> str:
        """Format domain into readable display name."""
        # Remove common TLDs and www
        name = domain.lower()
        for suffix in [".com", ".net", ".org", ".io", ".co"]:
            name = name.replace(suffix, "")
        name = name.replace("www.", "")

        # Title case
        return name.title()

    def _identify_gaps(
        self,
        competitors: List[Competitor]
    ) -> List[CompetitiveGap]:
        """Identify competitive gaps and opportunities."""
        gaps = []

        # Gap 1: Low impression share overall
        total_competitor_share = sum(c.impression_share for c in competitors)
        our_share = self.context.our_impression_share

        if our_share < 20:
            gaps.append(CompetitiveGap(
                gap_type="market_share",
                description=f"Low market visibility ({our_share:.1f}% impression share)",
                opportunity_size="large",
                confidence=0.9,
                recommended_action="Increase bids and budget to capture more impressions",
                expected_impact="10-30% increase in impression share",
                supporting_data=[{
                    "our_share": f"{our_share:.1f}%",
                    "top_competitor_share": f"{competitors[0].impression_share:.1f}%" if competitors else "N/A",
                }],
            ))

        # Gap 2: Losing position battles
        top_positioned_competitors = [
            c for c in competitors
            if c.position_above_rate > 50
        ]

        if top_positioned_competitors:
            gaps.append(CompetitiveGap(
                gap_type="positioning",
                description=f"{len(top_positioned_competitors)} competitors consistently above us",
                opportunity_size="medium",
                confidence=0.85,
                recommended_action="Improve ad rank through bid increases or Quality Score optimization",
                expected_impact="Higher ad positions, improved CTR",
                supporting_data=[{
                    "competitor": c.domain,
                    "position_above_rate": f"{c.position_above_rate:.1f}%"
                } for c in top_positioned_competitors[:3]],
            ))

        # Gap 3: Emerging competitors
        new_competitors = [c for c in competitors if c.is_new]
        if new_competitors:
            gaps.append(CompetitiveGap(
                gap_type="new_entrants",
                description=f"{len(new_competitors)} new competitors entered the market",
                opportunity_size="medium",
                confidence=0.8,
                recommended_action="Monitor new competitors closely, defend key positions",
                expected_impact="Maintain market position against new entrants",
                supporting_data=[{
                    "competitor": c.domain,
                    "impression_share": f"{c.impression_share:.1f}%"
                } for c in new_competitors],
            ))

        # Gap 4: Top of page opportunities
        if self.context.our_top_of_page_rate < 50:
            gaps.append(CompetitiveGap(
                gap_type="top_position",
                description=f"Low top of page rate ({self.context.our_top_of_page_rate:.1f}%)",
                opportunity_size="medium",
                confidence=0.85,
                recommended_action="Use Target Impression Share bid strategy for top positions",
                expected_impact="30-50% more top of page impressions",
            ))

        return gaps

    def _generate_defensive_actions(
        self,
        competitors: List[Competitor]
    ) -> List[str]:
        """Generate defensive recommendations."""
        actions = []

        # High threat competitors
        high_threats = [c for c in competitors if c.threat_level == "high"]
        if high_threats:
            actions.append(
                f"Monitor {len(high_threats)} high-threat competitors: "
                f"{', '.join(c.domain for c in high_threats[:3])}"
            )

        # Growing competitors
        growing = [c for c in competitors if c.impression_share_30d_change > 10]
        if growing:
            actions.append(
                f"Defend against {len(growing)} rapidly growing competitors"
            )

        # Position defense
        above_us = [c for c in competitors if c.position_above_rate > 60]
        if above_us:
            actions.append(
                "Increase bids on core keywords where competitors dominate position"
            )

        # Brand defense
        actions.append(
            "Ensure branded campaigns protect against competitor conquesting"
        )

        return actions

    def _generate_offensive_actions(
        self,
        competitors: List[Competitor]
    ) -> List[str]:
        """Generate offensive recommendations."""
        actions = []

        # Weak competitors to target
        weak = [c for c in competitors if c.threat_level == "low" and c.impression_share > 10]
        if weak:
            actions.append(
                f"Target market share from {len(weak)} weaker competitors"
            )

        # Declining competitors
        declining = [c for c in competitors if c.impression_share_30d_change < -10]
        if declining:
            actions.append(
                f"Capitalize on {len(declining)} declining competitors: "
                f"{', '.join(c.domain for c in declining[:3])}"
            )

        # Low overlap opportunities
        low_overlap = [c for c in competitors if c.overlap_rate < 30 and c.impression_share > 15]
        if low_overlap:
            actions.append(
                f"Expand into keyword areas where {len(low_overlap)} competitors "
                "have low overlap with us"
            )

        # General expansion
        actions.append(
            "Research competitor keywords to identify expansion opportunities"
        )

        return actions

    def discover_competitor_keywords(
        self,
        competitor_domains: List[str],
        seed_keywords: List[str]
    ) -> List[KeywordIdea]:
        """
        Discover potential keywords competitors may be targeting.

        Note: In production, this would use:
        - SEMrush/Ahrefs/SpyFu API
        - Google Ads Keyword Planner with competitor URLs
        - Search term reports showing competitor overlap

        This provides a template for the logic.
        """
        discovered_keywords = []

        # Common competitor keyword patterns
        for competitor in competitor_domains:
            competitor_name = self._format_display_name(competitor)

            # Competitor brand variations
            brand_keywords = [
                f"{competitor_name} alternative",
                f"{competitor_name} vs",
                f"better than {competitor_name}",
                f"{competitor_name} competitor",
                f"{competitor_name} reviews",
            ]

            for kw in brand_keywords:
                discovered_keywords.append(KeywordIdea(
                    keyword=kw,
                    source=KeywordSource.COMPETITOR_ANALYSIS,
                    source_keyword=competitor,
                    reasoning=f"Competitor conquesting: {competitor}",
                    intent=KeywordIntent.COMMERCIAL,
                    intent_confidence=0.8,
                ))

        # Combine with seed keywords for variations
        for seed in seed_keywords:
            for competitor in competitor_domains:
                competitor_name = self._format_display_name(competitor)

                comparison_keywords = [
                    f"{seed} vs {competitor_name}",
                    f"{competitor_name} {seed}",
                ]

                for kw in comparison_keywords:
                    discovered_keywords.append(KeywordIdea(
                        keyword=kw,
                        source=KeywordSource.COMPETITOR_ANALYSIS,
                        source_keyword=seed,
                        reasoning=f"Competitor comparison: {competitor_name}",
                        intent=KeywordIntent.COMMERCIAL,
                        intent_confidence=0.85,
                    ))

        return discovered_keywords

    def analyze_competitor_strategy(
        self,
        competitor: Competitor
    ) -> Dict[str, Any]:
        """
        Analyze a specific competitor's apparent strategy.

        Based on their auction metrics, infer their strategy.
        """
        analysis = {
            "competitor": competitor.domain,
            "analyzed_at": datetime.now().isoformat(),
            "inferred_strategy": [],
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
        }

        # High impression share = aggressive coverage
        if competitor.impression_share > 50:
            analysis["inferred_strategy"].append("Broad market coverage")
            analysis["strengths"].append("High visibility in the market")

        # High top of page rate = premium positioning
        if competitor.top_of_page_rate > 60:
            analysis["inferred_strategy"].append("Premium positioning focus")
            analysis["strengths"].append("Strong ad rank/Quality Score")

        # High outranking share = competitive bidding
        if competitor.outranking_share > 50:
            analysis["inferred_strategy"].append("Aggressive bidding strategy")
            analysis["strengths"].append("Competitive bid levels")

        # Rapid growth = expansion mode
        if competitor.impression_share_30d_change > 15:
            analysis["inferred_strategy"].append("Aggressive expansion")
            analysis["strengths"].append("Growing market presence")
            analysis["recommendations"].append(
                "Monitor closely - may be launching new campaigns or increasing budgets"
            )

        # Declining = potential vulnerability
        if competitor.impression_share_30d_change < -10:
            analysis["weaknesses"].append("Declining market presence")
            analysis["recommendations"].append(
                "Opportunity to capture their market share"
            )

        # Low top of page = budget/bid constraints
        if competitor.top_of_page_rate < 30:
            analysis["weaknesses"].append("Limited premium positions")
            analysis["recommendations"].append(
                "Compete on top positions where they're weak"
            )

        return analysis

    def generate_competitive_report(
        self,
        insight: CompetitorInsight
    ) -> str:
        """Generate a human-readable competitive analysis report."""
        lines = [
            "=" * 60,
            "COMPETITIVE INTELLIGENCE REPORT",
            f"Generated: {insight.generated_at}",
            f"Analysis Period: {insight.analysis_period_days} days",
            "=" * 60,
            "",
            "OUR POSITION",
            "-" * 40,
            f"Impression Share: {insight.our_impression_share:.1f}%",
            f"Top of Page Rate: {insight.our_top_of_page_rate:.1f}%",
            "",
            "COMPETITOR OVERVIEW",
            "-" * 40,
            f"Total Competitors Tracked: {len(insight.competitors)}",
            f"New Competitors: {len(insight.new_competitors)}",
            f"Aggressive Competitors: {len(insight.aggressive_competitors)}",
            "",
        ]

        # Top competitors table
        if insight.competitors:
            lines.append("TOP COMPETITORS")
            lines.append("-" * 40)
            lines.append(f"{'Domain':<25} {'Share':<10} {'Threat':<10}")

            for comp in insight.competitors[:5]:
                lines.append(
                    f"{comp.domain[:24]:<25} {comp.impression_share:>5.1f}%    {comp.threat_level:<10}"
                )
            lines.append("")

        # Alerts
        if insight.new_competitors:
            lines.append("⚠️  NEW COMPETITOR ALERTS")
            lines.append("-" * 40)
            for comp in insight.new_competitors:
                lines.append(f"  • {comp.domain} - {comp.impression_share:.1f}% share")
            lines.append("")

        # Gaps
        if insight.competitive_gaps:
            lines.append("IDENTIFIED GAPS & OPPORTUNITIES")
            lines.append("-" * 40)
            for gap in insight.competitive_gaps:
                lines.append(f"  [{gap.opportunity_size.upper()}] {gap.description}")
                lines.append(f"    Action: {gap.recommended_action}")
            lines.append("")

        # Recommendations
        lines.append("RECOMMENDED ACTIONS")
        lines.append("-" * 40)

        if insight.defensive_actions:
            lines.append("Defensive:")
            for action in insight.defensive_actions:
                lines.append(f"  • {action}")

        if insight.offensive_actions:
            lines.append("Offensive:")
            for action in insight.offensive_actions:
                lines.append(f"  • {action}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
