"""Ad copy data models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class HeadlineType(Enum):
    """Types of headlines for different purposes."""
    KEYWORD_FOCUSED = "keyword_focused"      # Contains target keyword
    BENEFIT_FOCUSED = "benefit_focused"      # Highlights benefit
    CTA_FOCUSED = "cta_focused"              # Call to action
    SOCIAL_PROOF = "social_proof"            # Reviews, trust signals
    URGENCY = "urgency"                       # Limited time, scarcity
    QUESTION = "question"                     # Asks a question
    STATISTIC = "statistic"                   # Numbers, data
    BRAND = "brand"                           # Brand name focused


class DescriptionType(Enum):
    """Types of descriptions."""
    FEATURES = "features"
    BENEFITS = "benefits"
    SOCIAL_PROOF = "social_proof"
    CTA = "cta"
    OFFER = "offer"


@dataclass
class HeadlineIdea:
    """A single headline idea."""

    text: str
    headline_type: HeadlineType

    # Validation
    character_count: int = 0
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Quality metrics
    keyword_included: bool = False
    estimated_ctr_impact: str = "neutral"  # positive, neutral, negative

    # Source
    generated_by: str = "manual"  # manual, ai, template

    def __post_init__(self):
        self.character_count = len(self.text)
        self._validate()

    def _validate(self) -> None:
        """Validate headline against Google Ads requirements."""
        self.validation_errors = []

        if self.character_count > 30:
            self.validation_errors.append(f"Too long: {self.character_count}/30 chars")

        if self.character_count < 5:
            self.validation_errors.append("Too short: minimum 5 characters")

        # Check for prohibited content
        prohibited = ["click here", "!!!!", "FREE!!!", "$$$$"]
        for p in prohibited:
            if p.lower() in self.text.lower():
                self.validation_errors.append(f"Prohibited content: '{p}'")

        self.is_valid = len(self.validation_errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.headline_type.value,
            "characters": f"{self.character_count}/30",
            "is_valid": self.is_valid,
            "errors": self.validation_errors,
        }


@dataclass
class DescriptionIdea:
    """A single description idea."""

    text: str
    description_type: DescriptionType

    # Validation
    character_count: int = 0
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Quality
    includes_cta: bool = False
    generated_by: str = "manual"

    def __post_init__(self):
        self.character_count = len(self.text)
        self._validate()
        self._check_cta()

    def _validate(self) -> None:
        """Validate description against Google Ads requirements."""
        self.validation_errors = []

        if self.character_count > 90:
            self.validation_errors.append(f"Too long: {self.character_count}/90 chars")

        if self.character_count < 10:
            self.validation_errors.append("Too short: minimum 10 characters")

        self.is_valid = len(self.validation_errors) == 0

    def _check_cta(self) -> None:
        """Check if description includes a call to action."""
        cta_phrases = [
            "call", "contact", "get", "request", "schedule", "book",
            "learn more", "find out", "discover", "try", "start",
            "sign up", "subscribe", "download", "shop", "buy", "order"
        ]
        self.includes_cta = any(cta in self.text.lower() for cta in cta_phrases)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.description_type.value,
            "characters": f"{self.character_count}/90",
            "is_valid": self.is_valid,
            "includes_cta": self.includes_cta,
            "errors": self.validation_errors,
        }


@dataclass
class AdCopySet:
    """A complete set of ad copy (headlines + descriptions)."""

    name: str
    target_keyword: str

    headlines: List[HeadlineIdea] = field(default_factory=list)
    descriptions: List[DescriptionIdea] = field(default_factory=list)

    # URLs
    final_url: str = ""
    path1: str = ""  # Max 15 chars
    path2: str = ""  # Max 15 chars

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate the complete ad copy set."""
        self.validation_errors = []

        # Check headline count
        valid_headlines = [h for h in self.headlines if h.is_valid]
        if len(valid_headlines) < 3:
            self.validation_errors.append(f"Need at least 3 valid headlines (have {len(valid_headlines)})")
        if len(valid_headlines) > 15:
            self.validation_errors.append(f"Maximum 15 headlines (have {len(valid_headlines)})")

        # Check description count
        valid_descriptions = [d for d in self.descriptions if d.is_valid]
        if len(valid_descriptions) < 2:
            self.validation_errors.append(f"Need at least 2 valid descriptions (have {len(valid_descriptions)})")
        if len(valid_descriptions) > 4:
            self.validation_errors.append(f"Maximum 4 descriptions (have {len(valid_descriptions)})")

        # Check URL paths
        if len(self.path1) > 15:
            self.validation_errors.append(f"Path 1 too long: {len(self.path1)}/15")
        if len(self.path2) > 15:
            self.validation_errors.append(f"Path 2 too long: {len(self.path2)}/15")

        # Check for keyword in headlines
        keyword_in_headline = any(
            self.target_keyword.lower() in h.text.lower()
            for h in self.headlines
        )
        if not keyword_in_headline:
            self.validation_errors.append("Target keyword not found in any headline")

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "name": self.name,
            "target_keyword": self.target_keyword,
            "final_url": self.final_url,
            "display_path": f"/{self.path1}/{self.path2}".rstrip("/"),
            "headlines": [h.to_dict() for h in self.headlines],
            "descriptions": [d.to_dict() for d in self.descriptions],
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "stats": {
                "valid_headlines": len([h for h in self.headlines if h.is_valid]),
                "valid_descriptions": len([d for d in self.descriptions if d.is_valid]),
            },
        }


@dataclass
class AdVariation:
    """A variation of an ad for A/B testing."""

    variation_id: str
    base_ad_name: str
    variation_type: str  # "headline_test", "description_test", "cta_test"

    # What changed
    changed_element: str
    original_text: str
    new_text: str

    # Hypothesis
    hypothesis: str
    expected_impact: str

    # Full ad copy
    ad_copy: Optional[AdCopySet] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variation_id": self.variation_id,
            "base_ad": self.base_ad_name,
            "variation_type": self.variation_type,
            "change": {
                "element": self.changed_element,
                "original": self.original_text,
                "new": self.new_text,
            },
            "hypothesis": self.hypothesis,
            "expected_impact": self.expected_impact,
        }
