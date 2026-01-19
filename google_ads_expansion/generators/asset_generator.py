"""Asset variation generator.

Generates variations of ad assets for testing:
- Image asset variations
- Sitelink extensions
- Callout extensions
- Structured snippets
- Call extensions
- Price extensions
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AssetType(Enum):
    """Types of Google Ads assets."""
    SITELINK = "sitelink"
    CALLOUT = "callout"
    STRUCTURED_SNIPPET = "structured_snippet"
    CALL = "call"
    PRICE = "price"
    PROMOTION = "promotion"
    IMAGE = "image"
    LEAD_FORM = "lead_form"


@dataclass
class SitelinkAsset:
    """A sitelink extension asset."""

    link_text: str  # Max 25 chars
    description_line_1: str = ""  # Max 35 chars
    description_line_2: str = ""  # Max 35 chars
    final_url: str = ""

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self) -> bool:
        self.validation_errors = []

        if len(self.link_text) > 25:
            self.validation_errors.append(f"Link text too long: {len(self.link_text)}/25")
        if len(self.description_line_1) > 35:
            self.validation_errors.append(f"Description 1 too long: {len(self.description_line_1)}/35")
        if len(self.description_line_2) > 35:
            self.validation_errors.append(f"Description 2 too long: {len(self.description_line_2)}/35")
        if not self.final_url:
            self.validation_errors.append("Final URL required")

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "sitelink",
            "link_text": self.link_text,
            "description_1": self.description_line_1,
            "description_2": self.description_line_2,
            "final_url": self.final_url,
            "is_valid": self.is_valid,
            "errors": self.validation_errors,
        }


@dataclass
class CalloutAsset:
    """A callout extension asset."""

    text: str  # Max 25 chars

    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self) -> bool:
        self.validation_errors = []

        if len(self.text) > 25:
            self.validation_errors.append(f"Text too long: {len(self.text)}/25")
        if len(self.text) < 3:
            self.validation_errors.append("Text too short: minimum 3 characters")

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "callout",
            "text": self.text,
            "characters": f"{len(self.text)}/25",
            "is_valid": self.is_valid,
            "errors": self.validation_errors,
        }


@dataclass
class StructuredSnippetAsset:
    """A structured snippet extension asset."""

    header: str  # Predefined headers only
    values: List[str] = field(default_factory=list)  # 3-10 values, max 25 chars each

    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Valid headers per Google Ads
    VALID_HEADERS = [
        "Amenities", "Brands", "Courses", "Degree programs", "Destinations",
        "Featured hotels", "Insurance coverage", "Models", "Neighborhoods",
        "Service catalog", "Shows", "Styles", "Types"
    ]

    def __post_init__(self):
        self.validate()

    def validate(self) -> bool:
        self.validation_errors = []

        if self.header not in self.VALID_HEADERS:
            self.validation_errors.append(f"Invalid header: {self.header}")

        if len(self.values) < 3:
            self.validation_errors.append(f"Need at least 3 values (have {len(self.values)})")
        if len(self.values) > 10:
            self.validation_errors.append(f"Maximum 10 values (have {len(self.values)})")

        for i, val in enumerate(self.values):
            if len(val) > 25:
                self.validation_errors.append(f"Value {i+1} too long: {len(val)}/25")

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "structured_snippet",
            "header": self.header,
            "values": self.values,
            "is_valid": self.is_valid,
            "errors": self.validation_errors,
        }


@dataclass
class PriceAsset:
    """A price extension asset."""

    price_type: str  # "brands", "events", "locations", "neighborhoods", "product_categories", "product_tiers", "services", "service_categories", "service_tiers"
    header: str  # Max 25 chars
    description: str  # Max 25 chars
    price: str  # e.g., "$99", "$99/mo", "From $50"
    final_url: str

    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self) -> bool:
        self.validation_errors = []

        if len(self.header) > 25:
            self.validation_errors.append(f"Header too long: {len(self.header)}/25")
        if len(self.description) > 25:
            self.validation_errors.append(f"Description too long: {len(self.description)}/25")
        if not self.final_url:
            self.validation_errors.append("Final URL required")

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "price",
            "price_type": self.price_type,
            "header": self.header,
            "description": self.description,
            "price": self.price,
            "final_url": self.final_url,
            "is_valid": self.is_valid,
            "errors": self.validation_errors,
        }


@dataclass
class AssetContext:
    """Context for generating assets."""

    business_name: str
    website_url: str
    phone_number: Optional[str] = None

    # Pages on site
    pages: Dict[str, str] = None  # {"About Us": "/about", "Services": "/services"}

    # Offerings
    services: List[Dict[str, Any]] = None  # [{"name": "Service A", "price": "$99", "url": "/service-a"}]
    products: List[Dict[str, Any]] = None

    # Value props
    unique_selling_points: List[str] = None
    guarantees: List[str] = None
    features: List[str] = None

    def __post_init__(self):
        if self.pages is None:
            self.pages = {}
        if self.services is None:
            self.services = []
        if self.products is None:
            self.products = []
        if self.unique_selling_points is None:
            self.unique_selling_points = []
        if self.guarantees is None:
            self.guarantees = []
        if self.features is None:
            self.features = []


class AssetVariationGenerator:
    """Generates Google Ads extension assets."""

    def __init__(self, context: AssetContext):
        """Initialize with business context."""
        self.context = context

    def generate_all_assets(self) -> Dict[str, List[Any]]:
        """Generate all asset types."""
        return {
            "sitelinks": self.generate_sitelinks(),
            "callouts": self.generate_callouts(),
            "structured_snippets": self.generate_structured_snippets(),
            "price_extensions": self.generate_price_extensions(),
        }

    def generate_sitelinks(self, count: int = 8) -> List[SitelinkAsset]:
        """Generate sitelink extensions."""
        sitelinks = []

        # Generate from pages
        for page_name, page_path in list(self.context.pages.items())[:count]:
            url = f"{self.context.website_url.rstrip('/')}{page_path}"

            sitelink = SitelinkAsset(
                link_text=page_name[:25],
                description_line_1=f"Learn more about {page_name.lower()}"[:35],
                description_line_2=f"Visit our {page_name.lower()} page"[:35],
                final_url=url,
            )
            sitelinks.append(sitelink)

        # Generate common sitelinks if we need more
        common_sitelinks = [
            ("Contact Us", "Get in touch with our team", "We're here to help", "/contact"),
            ("About Us", "Learn about our company", "Our story and mission", "/about"),
            ("Services", "View all our services", "Find what you need", "/services"),
            ("Pricing", "See our competitive prices", "Transparent pricing", "/pricing"),
            ("Reviews", "Read customer reviews", "See what others say", "/reviews"),
            ("FAQ", "Frequently asked questions", "Get quick answers", "/faq"),
            ("Locations", "Find a location near you", "Visit us today", "/locations"),
            ("Free Quote", "Get your free quote", "No obligation", "/quote"),
        ]

        for name, desc1, desc2, path in common_sitelinks:
            if len(sitelinks) >= count:
                break
            if not any(s.link_text == name for s in sitelinks):
                sitelinks.append(SitelinkAsset(
                    link_text=name,
                    description_line_1=desc1,
                    description_line_2=desc2,
                    final_url=f"{self.context.website_url.rstrip('/')}{path}",
                ))

        return sitelinks[:count]

    def generate_callouts(self, count: int = 10) -> List[CalloutAsset]:
        """Generate callout extensions."""
        callouts = []

        # From USPs
        for usp in self.context.unique_selling_points:
            if len(usp) <= 25:
                callouts.append(CalloutAsset(text=usp))

        # From features
        for feature in self.context.features:
            if len(feature) <= 25:
                callouts.append(CalloutAsset(text=feature))

        # From guarantees
        for guarantee in self.context.guarantees:
            if len(guarantee) <= 25:
                callouts.append(CalloutAsset(text=guarantee))

        # Common callouts
        common_callouts = [
            "Free Consultation",
            "Licensed & Insured",
            "24/7 Support",
            "Same Day Service",
            "Free Estimates",
            "Satisfaction Guaranteed",
            "No Hidden Fees",
            "Family Owned",
            "Trusted Since 2010",
            "Award Winning",
            "Expert Team",
            "Fast Response",
            "Competitive Prices",
            "Quality Guaranteed",
            "Local Business",
        ]

        for callout in common_callouts:
            if len(callouts) >= count:
                break
            if not any(c.text.lower() == callout.lower() for c in callouts):
                callouts.append(CalloutAsset(text=callout))

        return callouts[:count]

    def generate_structured_snippets(self) -> List[StructuredSnippetAsset]:
        """Generate structured snippet extensions."""
        snippets = []

        # Services snippet
        if self.context.services:
            service_names = [s.get("name", "")[:25] for s in self.context.services[:10]]
            if len(service_names) >= 3:
                snippets.append(StructuredSnippetAsset(
                    header="Service catalog",
                    values=service_names,
                ))

        # Types snippet (if we have product types)
        if self.context.products:
            product_types = list(set(
                p.get("type", p.get("name", ""))[:25]
                for p in self.context.products[:10]
            ))
            if len(product_types) >= 3:
                snippets.append(StructuredSnippetAsset(
                    header="Types",
                    values=product_types[:10],
                ))

        # Amenities (for service businesses)
        amenities = [f[:25] for f in self.context.features[:10]]
        if len(amenities) >= 3:
            snippets.append(StructuredSnippetAsset(
                header="Amenities",
                values=amenities,
            ))

        return snippets

    def generate_price_extensions(self) -> List[PriceAsset]:
        """Generate price extension assets."""
        price_assets = []

        # From services
        for service in self.context.services:
            if "price" in service and "name" in service:
                price_assets.append(PriceAsset(
                    price_type="services",
                    header=service["name"][:25],
                    description=service.get("description", "Professional service")[:25],
                    price=service["price"],
                    final_url=service.get("url", self.context.website_url),
                ))

        # From products
        for product in self.context.products:
            if "price" in product and "name" in product:
                price_assets.append(PriceAsset(
                    price_type="product_categories",
                    header=product["name"][:25],
                    description=product.get("description", "Quality product")[:25],
                    price=product["price"],
                    final_url=product.get("url", self.context.website_url),
                ))

        return price_assets[:8]  # Max 8 price items

    def generate_variations(
        self,
        asset: Any,
        variation_count: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate variations of an existing asset for testing."""
        variations = []

        if isinstance(asset, SitelinkAsset):
            variations = self._generate_sitelink_variations(asset, variation_count)
        elif isinstance(asset, CalloutAsset):
            variations = self._generate_callout_variations(asset, variation_count)

        return variations

    def _generate_sitelink_variations(
        self,
        sitelink: SitelinkAsset,
        count: int
    ) -> List[Dict[str, Any]]:
        """Generate sitelink variations."""
        variations = []

        # Link text variations
        link_variations = [
            sitelink.link_text.upper(),
            sitelink.link_text.title(),
            f"Our {sitelink.link_text}",
            f"View {sitelink.link_text}",
        ]

        for i, link_text in enumerate(link_variations[:count]):
            if len(link_text) <= 25:
                variations.append({
                    "variation_id": f"sitelink_var_{i}",
                    "original": sitelink.link_text,
                    "variation": link_text,
                    "element": "link_text",
                    "hypothesis": "Testing different link text may improve CTR",
                })

        return variations

    def _generate_callout_variations(
        self,
        callout: CalloutAsset,
        count: int
    ) -> List[Dict[str, Any]]:
        """Generate callout variations."""
        variations = []

        # Text variations
        text_variations = [
            callout.text.title(),
            f"✓ {callout.text}"[:25],
            callout.text.replace(" ", " • ")[:25],
        ]

        for i, text in enumerate(text_variations[:count]):
            if len(text) <= 25:
                variations.append({
                    "variation_id": f"callout_var_{i}",
                    "original": callout.text,
                    "variation": text,
                    "element": "text",
                    "hypothesis": "Testing callout formatting may improve visibility",
                })

        return variations

    def validate_all(self, assets: Dict[str, List[Any]]) -> Dict[str, Any]:
        """Validate all generated assets."""
        results = {
            "total_assets": 0,
            "valid_assets": 0,
            "invalid_assets": 0,
            "issues": [],
        }

        for asset_type, asset_list in assets.items():
            for asset in asset_list:
                results["total_assets"] += 1

                if hasattr(asset, "is_valid"):
                    if asset.is_valid:
                        results["valid_assets"] += 1
                    else:
                        results["invalid_assets"] += 1
                        results["issues"].append({
                            "asset_type": asset_type,
                            "asset": asset.to_dict() if hasattr(asset, "to_dict") else str(asset),
                            "errors": asset.validation_errors if hasattr(asset, "validation_errors") else [],
                        })

        results["is_ready"] = results["invalid_assets"] == 0
        return results

    def to_dict(self, assets: Dict[str, List[Any]]) -> Dict[str, Any]:
        """Convert all assets to dictionary format."""
        return {
            "generated_at": datetime.now().isoformat(),
            "business": self.context.business_name,
            "assets": {
                asset_type: [
                    a.to_dict() if hasattr(a, "to_dict") else a
                    for a in asset_list
                ]
                for asset_type, asset_list in assets.items()
            },
            "validation": self.validate_all(assets),
        }
