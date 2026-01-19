"""Data collectors for Google Ads API."""

from .campaign_collector import CampaignCollector
from .keyword_collector import KeywordCollector
from .search_term_collector import SearchTermCollector
from .geo_collector import GeoCollector
from .audience_collector import AudienceCollector
from .device_collector import DeviceCollector
from .schedule_collector import ScheduleCollector
from .extension_collector import ExtensionCollector
from .change_collector import ChangeCollector

__all__ = [
    "CampaignCollector",
    "KeywordCollector",
    "SearchTermCollector",
    "GeoCollector",
    "AudienceCollector",
    "DeviceCollector",
    "ScheduleCollector",
    "ExtensionCollector",
    "ChangeCollector",
]
