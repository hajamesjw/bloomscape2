"""
Command-line interface for the Google Ads Expansion System.

Usage:
    python -m google_ads_expansion.cli expand --keywords "plumber,plumbing services" --business "ABC Plumbing"
    python -m google_ads_expansion.cli keywords --seed "landscaping"
    python -m google_ads_expansion.cli ads --keyword "lawn care services" --url "https://example.com"
"""

import argparse
import json
import sys
from typing import List

from .main import ExpansionEngine, BusinessContext


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Google Ads Expansion System - Create new keywords, ads, and campaigns"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Expand command (full expansion plan)
    expand_parser = subparsers.add_parser(
        "expand",
        help="Create a complete expansion plan"
    )
    expand_parser.add_argument(
        "--keywords", "-k",
        required=True,
        help="Comma-separated seed keywords"
    )
    expand_parser.add_argument(
        "--business", "-b",
        required=True,
        help="Business name"
    )
    expand_parser.add_argument(
        "--type", "-t",
        default="service",
        help="Business type (default: service)"
    )
    expand_parser.add_argument(
        "--url", "-u",
        default="https://example.com",
        help="Website URL"
    )
    expand_parser.add_argument(
        "--budget",
        type=float,
        default=3000,
        help="Monthly budget in dollars (default: 3000)"
    )
    expand_parser.add_argument(
        "--structure",
        choices=["single", "by_intent", "by_theme"],
        default="single",
        help="Campaign structure (default: single)"
    )
    expand_parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON)"
    )

    # Keywords-only command
    kw_parser = subparsers.add_parser(
        "keywords",
        help="Expand keywords only (research mode)"
    )
    kw_parser.add_argument(
        "--seed", "-s",
        required=True,
        help="Comma-separated seed keywords"
    )
    kw_parser.add_argument(
        "--strategies",
        default="modifier,question,intent,semantic",
        help="Expansion strategies (comma-separated)"
    )
    kw_parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON)"
    )

    # Ads-only command
    ads_parser = subparsers.add_parser(
        "ads",
        help="Generate ad copy for keywords"
    )
    ads_parser.add_argument(
        "--keyword", "-k",
        required=True,
        help="Target keyword for ad copy"
    )
    ads_parser.add_argument(
        "--url", "-u",
        required=True,
        help="Final URL for the ad"
    )
    ads_parser.add_argument(
        "--business", "-b",
        default="Your Business",
        help="Business name"
    )
    ads_parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON)"
    )

    # Assets command
    assets_parser = subparsers.add_parser(
        "assets",
        help="Generate ad assets (extensions)"
    )
    assets_parser.add_argument(
        "--business", "-b",
        required=True,
        help="Business name"
    )
    assets_parser.add_argument(
        "--url", "-u",
        required=True,
        help="Website URL"
    )
    assets_parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON)"
    )

    return parser.parse_args()


def create_minimal_context(
    business_name: str,
    business_type: str = "service",
    website_url: str = "https://example.com",
    monthly_budget: float = 3000
) -> BusinessContext:
    """Create a minimal business context with defaults."""
    return BusinessContext(
        business_name=business_name,
        business_type=business_type,
        website_url=website_url,
        monthly_budget=monthly_budget,
        target_locations=["United States"],
        target_languages=["English"],
        # Defaults
        unique_selling_points=["Quality Service", "Fast Response"],
        benefits=["Save Time", "Save Money", "Peace of Mind"],
        features=["Professional Team", "Licensed & Insured", "Free Estimates"],
        guarantees=["Satisfaction Guaranteed"],
    )


def cmd_expand(args):
    """Handle the expand command."""
    print(f"\n{'='*60}")
    print("GOOGLE ADS EXPANSION SYSTEM")
    print(f"{'='*60}\n")

    # Parse keywords
    seed_keywords = [k.strip() for k in args.keywords.split(",")]
    print(f"Seed Keywords: {seed_keywords}")
    print(f"Business: {args.business}")
    print(f"Monthly Budget: ${args.budget:,.0f}")
    print(f"Campaign Structure: {args.structure}")
    print()

    # Create context and engine
    context = create_minimal_context(
        business_name=args.business,
        business_type=args.type,
        website_url=args.url,
        monthly_budget=args.budget,
    )
    engine = ExpansionEngine(context)

    # Generate plan
    result = engine.create_expansion_plan(
        seed_keywords=seed_keywords,
        campaign_structure=args.structure,
        include_competitor_analysis=False,  # No competitors in CLI mode
    )

    # Print report
    print("\n" + engine.generate_report(result))

    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(result.to_json())
        print(f"\nPlan saved to: {args.output}")

    return 0 if result.is_ready else 1


def cmd_keywords(args):
    """Handle the keywords command."""
    print("\nKEYWORD EXPANSION")
    print("-" * 40)

    seed_keywords = [k.strip() for k in args.seed.split(",")]
    strategies = [s.strip() for s in args.strategies.split(",")]

    print(f"Seeds: {seed_keywords}")
    print(f"Strategies: {strategies}")
    print()

    # Create minimal context
    context = create_minimal_context(
        business_name="Research",
        business_type="service",
    )
    engine = ExpansionEngine(context)

    # Expand keywords
    plan = engine.expand_keywords_only(
        seed_keywords=seed_keywords,
        strategies=strategies,
    )

    # Print results
    print(f"\nGenerated {len(plan.new_keywords)} keywords:\n")

    for cluster in plan.clusters:
        print(f"\nCluster: {cluster.name}")
        print(f"  Theme: {cluster.theme}")
        print(f"  Keywords: {len(cluster.keywords)}")
        for kw in cluster.keywords[:5]:  # Show first 5
            print(f"    - {kw.keyword}")
        if len(cluster.keywords) > 5:
            print(f"    ... and {len(cluster.keywords) - 5} more")

    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(plan.to_dict(), f, indent=2)
        print(f"\nKeywords saved to: {args.output}")

    return 0


def cmd_ads(args):
    """Handle the ads command."""
    print("\nAD COPY GENERATION")
    print("-" * 40)

    print(f"Keyword: {args.keyword}")
    print(f"URL: {args.url}")
    print()

    context = create_minimal_context(
        business_name=args.business,
    )
    engine = ExpansionEngine(context)

    # Generate ads
    ads = engine.generate_ads_only(
        keywords=[args.keyword],
        final_url=args.url,
    )

    # Print results
    for ad in ads:
        print(f"\nAd: {ad.name}")
        print(f"Target Keyword: {ad.target_keyword}")
        print(f"Display URL: {args.url}{ad.path1}/{ad.path2}")

        print("\nHeadlines:")
        for h in ad.headlines[:5]:
            status = "✓" if h.is_valid else "✗"
            print(f"  {status} {h.text} ({h.character_count}/30)")

        print("\nDescriptions:")
        for d in ad.descriptions:
            status = "✓" if d.is_valid else "✗"
            print(f"  {status} {d.text} ({d.character_count}/90)")

    # Save to file if requested
    if args.output:
        output = [ad.to_dict() for ad in ads]
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nAd copy saved to: {args.output}")

    return 0


def cmd_assets(args):
    """Handle the assets command."""
    print("\nASSET GENERATION")
    print("-" * 40)

    print(f"Business: {args.business}")
    print(f"Website: {args.url}")
    print()

    context = create_minimal_context(
        business_name=args.business,
        website_url=args.url,
    )
    engine = ExpansionEngine(context)

    # Generate assets
    assets = engine.generate_assets_only()

    # Print results
    print("\nGenerated Assets:")

    for asset_type, asset_list in assets.get("assets", {}).items():
        print(f"\n{asset_type.upper()}:")
        for asset in asset_list[:3]:  # Show first 3
            if isinstance(asset, dict):
                if "link_text" in asset:
                    print(f"  - {asset['link_text']}")
                elif "text" in asset:
                    print(f"  - {asset['text']}")
                elif "header" in asset:
                    print(f"  - {asset['header']}: {', '.join(asset.get('values', [])[:3])}...")

    validation = assets.get("validation", {})
    print(f"\nTotal: {validation.get('total_assets', 0)} assets")
    print(f"Valid: {validation.get('valid_assets', 0)}")

    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(assets, f, indent=2)
        print(f"\nAssets saved to: {args.output}")

    return 0


def main():
    """Main entry point."""
    args = parse_args()

    if args.command == "expand":
        return cmd_expand(args)
    elif args.command == "keywords":
        return cmd_keywords(args)
    elif args.command == "ads":
        return cmd_ads(args)
    elif args.command == "assets":
        return cmd_assets(args)
    else:
        print("Please specify a command. Use --help for options.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
