"""Base collector class with common functionality."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import date

from ..core.api_client import GoogleAdsClient
from ..core.data_store import DataStore
from ..config import Config, DEFAULT_CONFIG
from ..utils.logging import get_logger
from ..utils.dates import date_to_string

logger = get_logger(__name__)


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(
        self,
        api_client: GoogleAdsClient,
        data_store: DataStore,
        config: Optional[Config] = None,
    ):
        self.api_client = api_client
        self.data_store = data_store
        self.config = config or DEFAULT_CONFIG

    @abstractmethod
    def collect(self, start_date: date, end_date: date) -> List[Any]:
        """Collect data for the given date range."""
        pass

    def _format_date(self, d: date) -> str:
        """Format date for GAQL query."""
        return date_to_string(d)

    def _build_date_filter(self, start_date: date, end_date: date) -> str:
        """Build date filter for GAQL query."""
        return f"segments.date BETWEEN '{self._format_date(start_date)}' AND '{self._format_date(end_date)}'"

    def _safe_get(self, obj: Any, *attrs: str, default: Any = None) -> Any:
        """Safely get nested attributes."""
        for attr in attrs:
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                return default
        return obj

    def _micros_to_currency(self, micros: int) -> float:
        """Convert micros to currency value."""
        return micros / 1_000_000 if micros else 0.0

    def _extract_id(self, resource_name: str) -> str:
        """Extract ID from resource name."""
        # Format: customers/123/campaigns/456 -> 456
        if resource_name:
            return resource_name.split("/")[-1]
        return ""
