"""Validation utilities for Google Ads entities."""

from typing import List, Dict, Any
import re

from ..models.keywords import KeywordIdea
from ..models.ads import AdCopySet, HeadlineIdea, DescriptionIdea
from ..models.campaigns import CampaignBlueprint


def validate_keywords(keywords: List[KeywordIdea]) -> Dict[str, Any]:
    """
    Validate a list of keywords against Google Ads requirements.

    Returns validation summary with issues and warnings.
    """
    issues = []
    warnings = []
    valid_count = 0

    for i, kw in enumerate(keywords):
        kw_issues = []

        # Check length (max 80 characters)
        if len(kw.keyword) > 80:
            kw_issues.append(f"Keyword too long: {len(kw.keyword)}/80 chars")

        # Check for special characters
        invalid_chars = re.findall(r'[!@#$%^&*()=+\[\]{}|\\;:\'"<>?/]', kw.keyword)
        if invalid_chars:
            kw_issues.append(f"Invalid characters: {invalid_chars}")

        # Check for excessive words (10 word limit)
        word_count = len(kw.keyword.split())
        if word_count > 10:
            kw_issues.append(f"Too many words: {word_count}/10")

        # Check match type
        valid_match_types = ["EXACT", "PHRASE", "BROAD"]
        if kw.match_type not in valid_match_types:
            kw_issues.append(f"Invalid match type: {kw.match_type}")

        if kw_issues:
            issues.append({
                "keyword": kw.keyword,
                "issues": kw_issues,
            })
        else:
            valid_count += 1

        # Warnings (not blocking)
        if len(kw.keyword) < 3:
            warnings.append(f"Very short keyword: '{kw.keyword}'")

        if kw.keyword.isupper():
            warnings.append(f"All caps keyword: '{kw.keyword}'")

    return {
        "total_keywords": len(keywords),
        "valid_keywords": valid_count,
        "invalid_keywords": len(issues),
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_ad_copy(ad_copy: AdCopySet) -> Dict[str, Any]:
    """
    Validate ad copy against Google Ads policies and requirements.

    Returns detailed validation results.
    """
    issues = []
    warnings = []

    # Validate headlines
    valid_headlines = 0
    for h in ad_copy.headlines:
        h_issues = _validate_headline(h)
        if h_issues:
            issues.append({
                "type": "headline",
                "text": h.text,
                "issues": h_issues,
            })
        else:
            valid_headlines += 1

    # Validate descriptions
    valid_descriptions = 0
    for d in ad_copy.descriptions:
        d_issues = _validate_description(d)
        if d_issues:
            issues.append({
                "type": "description",
                "text": d.text,
                "issues": d_issues,
            })
        else:
            valid_descriptions += 1

    # Check minimum requirements
    if valid_headlines < 3:
        issues.append({
            "type": "structure",
            "text": "headlines",
            "issues": [f"Need at least 3 valid headlines (have {valid_headlines})"],
        })

    if valid_descriptions < 2:
        issues.append({
            "type": "structure",
            "text": "descriptions",
            "issues": [f"Need at least 2 valid descriptions (have {valid_descriptions})"],
        })

    # Validate paths
    if len(ad_copy.path1) > 15:
        issues.append({
            "type": "path",
            "text": ad_copy.path1,
            "issues": [f"Path 1 too long: {len(ad_copy.path1)}/15"],
        })

    if len(ad_copy.path2) > 15:
        issues.append({
            "type": "path",
            "text": ad_copy.path2,
            "issues": [f"Path 2 too long: {len(ad_copy.path2)}/15"],
        })

    # Check URL
    if not ad_copy.final_url:
        issues.append({
            "type": "url",
            "text": "final_url",
            "issues": ["Final URL is required"],
        })
    elif not ad_copy.final_url.startswith(("http://", "https://")):
        warnings.append("Final URL should include protocol (https://)")

    # Policy checks
    policy_issues = _check_ad_policies(ad_copy)
    issues.extend(policy_issues)

    return {
        "is_valid": len([i for i in issues if i["type"] != "warning"]) == 0,
        "valid_headlines": valid_headlines,
        "valid_descriptions": valid_descriptions,
        "issues": issues,
        "warnings": warnings,
        "recommendation": _get_ad_recommendation(valid_headlines, valid_descriptions),
    }


def _validate_headline(headline: HeadlineIdea) -> List[str]:
    """Validate a single headline."""
    issues = []

    # Length check
    if len(headline.text) > 30:
        issues.append(f"Too long: {len(headline.text)}/30 chars")

    if len(headline.text) < 3:
        issues.append("Too short: minimum 3 characters")

    # Prohibited content
    prohibited = [
        ("click here", "Prohibited phrase"),
        ("!!!", "Excessive punctuation"),
        ("???", "Excessive punctuation"),
        ("FREE!!!", "Prohibited promotional style"),
        ("$$$", "Prohibited symbols"),
        ("###", "Prohibited symbols"),
    ]

    for phrase, reason in prohibited:
        if phrase.lower() in headline.text.lower():
            issues.append(f"{reason}: '{phrase}'")

    # Check for all caps (more than 50% uppercase, excluding short words)
    words = headline.text.split()
    caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps_words > len(words) / 2 and len(words) > 2:
        issues.append("Excessive capitalization")

    return issues


def _validate_description(description: DescriptionIdea) -> List[str]:
    """Validate a single description."""
    issues = []

    # Length check
    if len(description.text) > 90:
        issues.append(f"Too long: {len(description.text)}/90 chars")

    if len(description.text) < 10:
        issues.append("Too short: minimum 10 characters")

    # Prohibited content
    prohibited = [
        ("click here", "Prohibited phrase"),
        ("!!!", "Excessive punctuation"),
        ("buy now!!!", "Prohibited promotional style"),
    ]

    for phrase, reason in prohibited:
        if phrase.lower() in description.text.lower():
            issues.append(f"{reason}: '{phrase}'")

    return issues


def _check_ad_policies(ad_copy: AdCopySet) -> List[Dict[str, Any]]:
    """Check ad copy against Google Ads policies."""
    issues = []

    all_text = (
        [h.text for h in ad_copy.headlines] +
        [d.text for d in ad_copy.descriptions]
    )

    # Trademark check (common examples)
    trademarks = ["google", "facebook", "amazon", "apple", "microsoft", "iphone", "android"]
    for text in all_text:
        for tm in trademarks:
            if tm in text.lower():
                issues.append({
                    "type": "policy",
                    "text": text[:30] + "...",
                    "issues": [f"Possible trademark issue: '{tm}'"],
                })

    # Superlative claims check
    superlatives = ["best in the world", "#1", "number one", "guaranteed results", "100% success"]
    for text in all_text:
        for sup in superlatives:
            if sup.lower() in text.lower():
                issues.append({
                    "type": "policy",
                    "text": text[:30] + "...",
                    "issues": [f"Unverifiable claim: '{sup}'"],
                })

    return issues


def _get_ad_recommendation(valid_headlines: int, valid_descriptions: int) -> str:
    """Get recommendation based on ad asset counts."""
    if valid_headlines >= 10 and valid_descriptions >= 4:
        return "Excellent - maximum assets for optimal performance"
    elif valid_headlines >= 5 and valid_descriptions >= 3:
        return "Good - consider adding more headlines for better testing"
    elif valid_headlines >= 3 and valid_descriptions >= 2:
        return "Minimum met - strongly recommend adding more assets"
    else:
        return "Insufficient assets - add more headlines and descriptions"


def validate_campaign(campaign: CampaignBlueprint) -> Dict[str, Any]:
    """
    Validate a campaign blueprint before implementation.

    Returns comprehensive validation results.
    """
    issues = []
    warnings = []

    # Budget validation
    if campaign.daily_budget < 1:
        issues.append({
            "field": "daily_budget",
            "issue": "Daily budget must be at least $1",
        })
    elif campaign.daily_budget < 10:
        warnings.append("Daily budget below $10 may limit performance")

    # Ad groups validation
    if len(campaign.ad_groups) == 0:
        issues.append({
            "field": "ad_groups",
            "issue": "Campaign must have at least one ad group",
        })
    elif len(campaign.ad_groups) > 100:
        warnings.append(f"High ad group count ({len(campaign.ad_groups)}). Consider splitting campaign.")

    # Validate each ad group
    ad_group_issues = []
    for ag in campaign.ad_groups:
        ag_valid = ag.validate()
        if not ag_valid:
            ad_group_issues.append({
                "ad_group": ag.name,
                "issues": ag.validation_errors,
            })

    if ad_group_issues:
        issues.append({
            "field": "ad_groups",
            "issue": f"{len(ad_group_issues)} ad groups have validation errors",
            "details": ad_group_issues,
        })

    # Location validation
    if len(campaign.locations) == 0:
        issues.append({
            "field": "locations",
            "issue": "At least one target location required",
        })

    # Bid strategy validation
    if campaign.bid_strategy.value == "TARGET_CPA" and not campaign.target_cpa:
        issues.append({
            "field": "target_cpa",
            "issue": "Target CPA bid strategy requires target_cpa value",
        })

    if campaign.bid_strategy.value == "TARGET_ROAS" and not campaign.target_roas:
        issues.append({
            "field": "target_roas",
            "issue": "Target ROAS bid strategy requires target_roas value",
        })

    # Calculate totals
    total_keywords = sum(len(ag.keywords) for ag in campaign.ad_groups)
    total_ads = sum(len(ag.ads) for ag in campaign.ad_groups)

    if total_keywords == 0:
        issues.append({
            "field": "keywords",
            "issue": "Campaign has no keywords",
        })

    if total_ads == 0:
        issues.append({
            "field": "ads",
            "issue": "Campaign has no ads",
        })

    return {
        "is_valid": len(issues) == 0,
        "campaign_name": campaign.name,
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "ad_groups": len(campaign.ad_groups),
            "keywords": total_keywords,
            "ads": total_ads,
            "daily_budget": f"${campaign.daily_budget:.2f}",
        },
        "ready_to_implement": len(issues) == 0,
    }
