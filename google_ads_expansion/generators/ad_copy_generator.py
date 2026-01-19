"""Ad copy generator.

Generates responsive search ad (RSA) copy including:
- Headlines (up to 15, 30 chars each)
- Descriptions (up to 4, 90 chars each)
- Display paths
- Ad variations for A/B testing
"""

import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ..models.ads import (
    HeadlineIdea,
    DescriptionIdea,
    AdCopySet,
    AdVariation,
    HeadlineType,
    DescriptionType,
)
from ..models.keywords import KeywordIdea, KeywordCluster
from ..config import EXPANSION_CONFIG


@dataclass
class AdCopyContext:
    """Context for generating ad copy."""

    business_name: str
    business_type: str

    # Value propositions
    unique_selling_points: List[str]
    benefits: List[str]
    features: List[str]

    # Social proof
    years_in_business: Optional[int] = None
    customer_count: Optional[str] = None  # e.g., "10,000+"
    rating: Optional[str] = None  # e.g., "4.9/5"
    awards: List[str] = None

    # Offers
    current_offers: List[str] = None
    guarantees: List[str] = None

    # CTAs
    preferred_ctas: List[str] = None
    phone_number: Optional[str] = None

    # Brand voice
    tone: str = "professional"  # professional, friendly, urgent, luxurious

    def __post_init__(self):
        if self.awards is None:
            self.awards = []
        if self.current_offers is None:
            self.current_offers = []
        if self.guarantees is None:
            self.guarantees = []
        if self.preferred_ctas is None:
            self.preferred_ctas = ["Get Started", "Learn More", "Contact Us"]


class AdCopyGenerator:
    """Generates Google Ads responsive search ad copy."""

    # CTA templates by tone
    CTA_TEMPLATES = {
        "professional": [
            "Get Your Free Quote",
            "Schedule a Consultation",
            "Request Information",
            "Contact Our Team",
            "Learn More Today",
        ],
        "friendly": [
            "Let's Get Started!",
            "Talk to Us Today",
            "See How We Can Help",
            "Get in Touch",
            "Start Your Journey",
        ],
        "urgent": [
            "Act Now - Limited Time",
            "Don't Wait - Call Today",
            "Limited Availability",
            "Book Now Before It's Gone",
            "Hurry - Offer Ends Soon",
        ],
        "luxurious": [
            "Experience Excellence",
            "Discover the Difference",
            "Elevate Your Experience",
            "Request Private Consultation",
            "Join Our Exclusive Clientele",
        ],
    }

    # Headline templates by type
    HEADLINE_TEMPLATES = {
        HeadlineType.KEYWORD_FOCUSED: [
            "{keyword}",
            "Quality {keyword}",
            "{keyword} Services",
            "Expert {keyword}",
            "Professional {keyword}",
        ],
        HeadlineType.BENEFIT_FOCUSED: [
            "{benefit}",
            "Get {benefit}",
            "Enjoy {benefit}",
            "{benefit} Guaranteed",
        ],
        HeadlineType.CTA_FOCUSED: [
            "{cta}",
            "{cta} Today",
            "{cta} Now",
        ],
        HeadlineType.SOCIAL_PROOF: [
            "{rating} Star Rated",
            "Trusted by {customer_count}",
            "{years} Years Experience",
            "Award-Winning Service",
        ],
        HeadlineType.URGENCY: [
            "Limited Time Offer",
            "Book Today - Save {discount}",
            "Don't Miss Out",
            "Act Fast",
        ],
        HeadlineType.BRAND: [
            "{business_name}",
            "{business_name} - {tagline}",
            "Official {business_name}",
        ],
    }

    def __init__(self, context: AdCopyContext):
        """Initialize with business context."""
        self.context = context
        self.config = EXPANSION_CONFIG["ad_copy_generation"]

    def generate_ad_copy_set(
        self,
        target_keyword: str,
        final_url: str,
        num_headlines: int = 15,
        num_descriptions: int = 4
    ) -> AdCopySet:
        """
        Generate a complete ad copy set for a keyword.

        Args:
            target_keyword: Primary keyword to target
            final_url: Landing page URL
            num_headlines: Number of headlines to generate (max 15)
            num_descriptions: Number of descriptions to generate (max 4)

        Returns:
            Complete AdCopySet with headlines and descriptions
        """
        headlines = self._generate_headlines(
            target_keyword,
            min(num_headlines, 15)
        )

        descriptions = self._generate_descriptions(
            target_keyword,
            min(num_descriptions, 4)
        )

        # Generate display paths from keyword
        path1, path2 = self._generate_display_paths(target_keyword)

        ad_copy = AdCopySet(
            name=f"RSA - {target_keyword[:30]}",
            target_keyword=target_keyword,
            headlines=headlines,
            descriptions=descriptions,
            final_url=final_url,
            path1=path1,
            path2=path2,
        )

        ad_copy.validate()
        return ad_copy

    def generate_for_cluster(
        self,
        cluster: KeywordCluster,
        final_url: str
    ) -> List[AdCopySet]:
        """Generate ad copy sets for all keywords in a cluster."""
        ad_sets = []

        # Generate for top keywords in cluster (by opportunity score)
        top_keywords = sorted(
            cluster.keywords,
            key=lambda k: k.opportunity_score,
            reverse=True
        )[:3]  # Top 3 keywords get dedicated ads

        for kw in top_keywords:
            ad_set = self.generate_ad_copy_set(
                target_keyword=kw.keyword,
                final_url=final_url
            )
            ad_sets.append(ad_set)

        return ad_sets

    def _generate_headlines(
        self,
        keyword: str,
        count: int
    ) -> List[HeadlineIdea]:
        """Generate diverse headlines for an ad."""
        headlines = []

        # Distribution of headline types (for variety)
        type_distribution = [
            (HeadlineType.KEYWORD_FOCUSED, 4),
            (HeadlineType.BENEFIT_FOCUSED, 3),
            (HeadlineType.CTA_FOCUSED, 3),
            (HeadlineType.SOCIAL_PROOF, 2),
            (HeadlineType.URGENCY, 2),
            (HeadlineType.BRAND, 1),
        ]

        for headline_type, type_count in type_distribution:
            type_headlines = self._generate_headlines_by_type(
                keyword,
                headline_type,
                type_count
            )
            headlines.extend(type_headlines)

            if len(headlines) >= count:
                break

        return headlines[:count]

    def _generate_headlines_by_type(
        self,
        keyword: str,
        headline_type: HeadlineType,
        count: int
    ) -> List[HeadlineIdea]:
        """Generate headlines of a specific type."""
        headlines = []
        templates = self.HEADLINE_TEMPLATES.get(headline_type, [])

        for template in templates[:count]:
            text = self._fill_headline_template(template, keyword)

            # Skip if too long
            if len(text) > 30:
                text = self._shorten_headline(text)

            if len(text) <= 30 and len(text) >= 5:
                headline = HeadlineIdea(
                    text=text,
                    headline_type=headline_type,
                    keyword_included=keyword.lower() in text.lower(),
                    generated_by="ai",
                )
                headlines.append(headline)

        return headlines

    def _fill_headline_template(self, template: str, keyword: str) -> str:
        """Fill in template placeholders with actual values."""
        text = template

        # Replace placeholders
        replacements = {
            "{keyword}": keyword.title(),
            "{business_name}": self.context.business_name,
            "{rating}": self.context.rating or "5",
            "{customer_count}": self.context.customer_count or "1000s",
            "{years}": str(self.context.years_in_business or 10),
            "{tagline}": self.context.unique_selling_points[0] if self.context.unique_selling_points else "Quality Service",
            "{discount}": "20%" if self.context.current_offers else "",
        }

        # Fill benefits
        if "{benefit}" in text and self.context.benefits:
            replacements["{benefit}"] = random.choice(self.context.benefits)

        # Fill CTAs
        if "{cta}" in text:
            ctas = self.CTA_TEMPLATES.get(
                self.context.tone,
                self.CTA_TEMPLATES["professional"]
            )
            replacements["{cta}"] = random.choice(ctas)

        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))

        return text

    def _shorten_headline(self, text: str) -> str:
        """Attempt to shorten a headline to fit 30 char limit."""
        # Remove common filler words
        fillers = [" the ", " a ", " an ", " our ", " your "]
        for filler in fillers:
            text = text.replace(filler, " ")

        # Abbreviate common words
        abbreviations = {
            "Professional": "Pro",
            "Services": "Svc",
            "Consultation": "Consult",
            "Experience": "Exp",
        }
        for full, abbrev in abbreviations.items():
            if len(text) > 30:
                text = text.replace(full, abbrev)

        return text.strip()

    def _generate_descriptions(
        self,
        keyword: str,
        count: int
    ) -> List[DescriptionIdea]:
        """Generate descriptions for an ad."""
        descriptions = []

        # Type distribution for variety
        type_distribution = [
            DescriptionType.BENEFITS,
            DescriptionType.FEATURES,
            DescriptionType.SOCIAL_PROOF,
            DescriptionType.CTA,
        ]

        for i, desc_type in enumerate(type_distribution[:count]):
            desc = self._generate_description_by_type(keyword, desc_type)
            if desc:
                descriptions.append(desc)

        return descriptions

    def _generate_description_by_type(
        self,
        keyword: str,
        desc_type: DescriptionType
    ) -> Optional[DescriptionIdea]:
        """Generate a single description of a specific type."""
        text = ""

        if desc_type == DescriptionType.BENEFITS:
            benefits = self.context.benefits[:2] if self.context.benefits else ["Quality", "Value"]
            text = f"Experience {benefits[0].lower()} and {benefits[1].lower()} with our {keyword.lower()} services. Contact us today!"

        elif desc_type == DescriptionType.FEATURES:
            features = self.context.features[:2] if self.context.features else ["Expert team", "Fast service"]
            text = f"{features[0]}. {features[1]}. Get the best {keyword.lower()} for your needs."

        elif desc_type == DescriptionType.SOCIAL_PROOF:
            if self.context.rating:
                text = f"Rated {self.context.rating} by our customers. Trusted by {self.context.customer_count or 'thousands'}. Professional {keyword.lower()} you can rely on."
            else:
                text = f"Trusted by {self.context.customer_count or 'thousands'} of satisfied customers. Professional {keyword.lower()} services."

        elif desc_type == DescriptionType.CTA:
            ctas = self.context.preferred_ctas or ["Contact us today"]
            guarantees = self.context.guarantees[0] if self.context.guarantees else "satisfaction guaranteed"
            text = f"{ctas[0]} for expert {keyword.lower()}. {guarantees.capitalize()}. Free consultation available."

        elif desc_type == DescriptionType.OFFER:
            if self.context.current_offers:
                text = f"{self.context.current_offers[0]} Get quality {keyword.lower()} at great prices. Limited time offer!"
            else:
                text = f"Competitive pricing on {keyword.lower()}. Get a free quote today. No obligation."

        # Validate length
        if len(text) > 90:
            text = text[:87] + "..."

        if len(text) >= 10:
            return DescriptionIdea(
                text=text,
                description_type=desc_type,
                generated_by="ai",
            )

        return None

    def _generate_display_paths(self, keyword: str) -> tuple:
        """Generate display URL paths from keyword."""
        # Clean keyword for URL
        cleaned = keyword.lower().replace(" ", "-")
        words = cleaned.split("-")

        # Path 1: First meaningful word (max 15 chars)
        path1 = words[0][:15] if words else ""

        # Path 2: Second word or business type
        if len(words) > 1:
            path2 = words[1][:15]
        else:
            path2 = self.context.business_type.lower().replace(" ", "-")[:15]

        return path1, path2

    def generate_variations(
        self,
        base_ad: AdCopySet,
        variation_count: int = 3
    ) -> List[AdVariation]:
        """
        Generate A/B test variations of an ad.

        Creates variations by testing different:
        - Headlines
        - Descriptions
        - CTAs
        """
        variations = []

        # Headline variation
        if len(base_ad.headlines) > 0:
            original_headline = base_ad.headlines[0]
            new_headline = self._create_headline_variant(original_headline)

            variations.append(AdVariation(
                variation_id=f"var_h_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                base_ad_name=base_ad.name,
                variation_type="headline_test",
                changed_element="headline_1",
                original_text=original_headline.text,
                new_text=new_headline.text,
                hypothesis="Testing different headline angle may improve CTR",
                expected_impact="5-15% CTR change",
            ))

        # Description variation
        if len(base_ad.descriptions) > 0:
            original_desc = base_ad.descriptions[0]
            new_desc = self._create_description_variant(original_desc)

            variations.append(AdVariation(
                variation_id=f"var_d_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                base_ad_name=base_ad.name,
                variation_type="description_test",
                changed_element="description_1",
                original_text=original_desc.text,
                new_text=new_desc.text,
                hypothesis="Testing different value proposition may improve conversion",
                expected_impact="3-10% conversion change",
            ))

        # CTA variation
        cta_variation = self._create_cta_variant(base_ad)
        if cta_variation:
            variations.append(cta_variation)

        return variations[:variation_count]

    def _create_headline_variant(
        self,
        original: HeadlineIdea
    ) -> HeadlineIdea:
        """Create a variant of a headline."""
        # Try different angle based on original type
        if original.headline_type == HeadlineType.KEYWORD_FOCUSED:
            # Switch to benefit
            new_type = HeadlineType.BENEFIT_FOCUSED
            benefit = self.context.benefits[0] if self.context.benefits else "Quality"
            text = f"Get {benefit}"
        elif original.headline_type == HeadlineType.BENEFIT_FOCUSED:
            # Switch to social proof
            new_type = HeadlineType.SOCIAL_PROOF
            text = f"{self.context.rating or '5'} Star Rated"
        else:
            # Switch to CTA
            new_type = HeadlineType.CTA_FOCUSED
            text = "Get Started Today"

        return HeadlineIdea(
            text=text[:30],
            headline_type=new_type,
            generated_by="ai",
        )

    def _create_description_variant(
        self,
        original: DescriptionIdea
    ) -> DescriptionIdea:
        """Create a variant of a description."""
        # Different angle
        if original.description_type == DescriptionType.BENEFITS:
            new_type = DescriptionType.SOCIAL_PROOF
            text = f"Join {self.context.customer_count or 'thousands'} of satisfied customers. See why we're rated {self.context.rating or '5 stars'}."
        else:
            new_type = DescriptionType.BENEFITS
            benefits = self.context.benefits[:2] if self.context.benefits else ["Quality", "Value"]
            text = f"Experience {benefits[0].lower()}. Get {benefits[1].lower()}. Contact us for a free consultation today!"

        if len(text) > 90:
            text = text[:87] + "..."

        return DescriptionIdea(
            text=text,
            description_type=new_type,
            generated_by="ai",
        )

    def _create_cta_variant(self, base_ad: AdCopySet) -> Optional[AdVariation]:
        """Create a CTA variation."""
        # Find descriptions with CTAs
        cta_descs = [d for d in base_ad.descriptions if d.includes_cta]

        if not cta_descs:
            return None

        original = cta_descs[0]

        # Generate alternative CTA
        alt_ctas = [
            "Get Your Free Quote Today",
            "Schedule Your Consultation",
            "Request a Callback Now",
            "Start Your Free Trial",
        ]

        # Find a CTA not in the original
        for cta in alt_ctas:
            if cta.lower() not in original.text.lower():
                new_text = original.text
                # Try to replace the CTA phrase
                for existing_cta in ["Contact us", "Get started", "Learn more", "Call now"]:
                    if existing_cta.lower() in new_text.lower():
                        new_text = new_text.replace(existing_cta, cta.split()[0] + " us")
                        break

                return AdVariation(
                    variation_id=f"var_cta_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    base_ad_name=base_ad.name,
                    variation_type="cta_test",
                    changed_element="cta",
                    original_text=original.text,
                    new_text=new_text[:90],
                    hypothesis="Testing different CTA may improve click-through",
                    expected_impact="5-20% CTR change",
                )

        return None

    def validate_ad_policy(self, ad_copy: AdCopySet) -> Dict[str, Any]:
        """
        Check ad copy against Google Ads policies.

        Returns validation results and warnings.
        """
        issues = []
        warnings = []

        # Check all text
        all_text = (
            [h.text for h in ad_copy.headlines] +
            [d.text for d in ad_copy.descriptions]
        )

        for text in all_text:
            # Excessive capitalization
            if sum(1 for c in text if c.isupper()) / max(len(text), 1) > 0.5:
                warnings.append(f"Excessive caps: '{text[:30]}...'")

            # Excessive punctuation
            if text.count("!") > 1:
                issues.append(f"Multiple exclamation marks: '{text[:30]}...'")

            # Prohibited phrases
            prohibited = [
                "click here", "click now", "#1", "number one",
                "best in the world", "guaranteed results"
            ]
            for phrase in prohibited:
                if phrase.lower() in text.lower():
                    issues.append(f"Prohibited phrase '{phrase}' in: '{text[:30]}...'")

            # Trademarked terms (common examples)
            trademarks = ["google", "facebook", "amazon", "apple", "microsoft"]
            for tm in trademarks:
                if tm in text.lower():
                    warnings.append(f"Possible trademark '{tm}' in: '{text[:30]}...'")

        return {
            "is_compliant": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendation": "Fix all issues before submitting" if issues else "Ready to submit",
        }
