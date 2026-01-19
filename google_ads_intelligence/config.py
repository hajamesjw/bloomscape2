"""
Configuration and constants for the Google Ads Intelligence System.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path


@dataclass
class AnalysisConfig:
    """Configuration for analysis parameters."""

    # Time windows for analysis (in days)
    TIME_WINDOWS: List[int] = field(default_factory=lambda: [1, 3, 7, 14, 30, 60, 90])

    # Minimum data thresholds before analysis is valid
    MIN_DATA_THRESHOLDS: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "campaign": {"clicks": 100, "conversions": 10, "days": 14},
        "ad_group": {"clicks": 50, "conversions": 5, "days": 14},
        "keyword": {"clicks": 30, "conversions": 3, "days": 21},
        "ad": {"impressions": 1000, "clicks": 50, "days": 14},
        "audience": {"clicks": 50, "conversions": 3, "days": 14},
        "geo": {"clicks": 30, "cost": 50, "days": 14},
    })

    # Events that trigger learning reset
    LEARNING_TRIGGERS: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "budget_change": {"threshold_pct": 20, "learning_days": 7},
        "bid_strategy_change": {"threshold_pct": 0, "learning_days": 14},
        "creative_change": {"threshold_pct": 0, "learning_days": 7},
        "targeting_change": {"threshold_pct": 0, "learning_days": 7},
        "conversion_action_change": {"threshold_pct": 0, "learning_days": 14},
    })


@dataclass
class BudgetConfig:
    """Configuration for budget change limits."""

    MAX_INCREASE_PCT: float = 20.0
    MAX_DECREASE_PCT: float = 15.0
    MIN_DAYS_BETWEEN_CHANGES: int = 7
    MIN_BUDGET_FLOOR: float = 10.0


@dataclass
class ExecutionConfig:
    """Configuration for safe execution limits."""

    MAX_CHANGES_PER_DAY: int = 10
    MAX_BUDGET_CHANGES_PER_DAY: int = 3
    MAX_KEYWORD_PAUSES_PER_DAY: int = 5
    REQUIRE_APPROVAL_ABOVE_RISK: str = "medium"  # auto-execute only "low" risk
    DRY_RUN_DEFAULT: bool = True


@dataclass
class APIConfig:
    """Configuration for Google Ads API."""

    # Rate limiting
    MAX_OPERATIONS_PER_DAY: int = 15000
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 60.0

    # Batch sizes
    MAX_BATCH_SIZE: int = 10000

    # Cache settings
    CACHE_TTL_SECONDS: int = 3600  # 1 hour


@dataclass
class Config:
    """Main configuration container."""

    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    api: APIConfig = field(default_factory=APIConfig)

    # Paths
    data_dir: Path = Path("./data")
    logs_dir: Path = Path("./logs")
    reports_dir: Path = Path("./reports")

    # Google Ads credentials
    customer_id: str = ""
    developer_token: str = ""
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    login_customer_id: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        import os

        config = cls()
        config.customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
        config.developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        config.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
        config.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
        config.refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
        config.login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

        return config


# Global default config
DEFAULT_CONFIG = Config()
