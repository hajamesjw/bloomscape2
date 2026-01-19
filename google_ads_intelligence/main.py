"""Main orchestration module for Google Ads Intelligence System."""

from typing import Optional, Dict, Any
from datetime import date, timedelta
from pathlib import Path

from .config import Config, DEFAULT_CONFIG
from .core.api_client import GoogleAdsClient
from .core.data_store import DataStore
from .collectors import (
    CampaignCollector,
    KeywordCollector,
    SearchTermCollector,
    GeoCollector,
    AudienceCollector,
    DeviceCollector,
    ScheduleCollector,
    ChangeCollector,
)
from .analyzers import LearningPhaseDetector
from .executors import RecommendationEngine, SafeExecutor
from .reports import ReportGenerator
from .utils.logging import get_logger, setup_logging
from .utils.dates import get_date_range

logger = get_logger(__name__)


class GoogleAdsIntelligence:
    """
    Main orchestration class for the Google Ads Intelligence System.

    This is the primary entry point for:
    - Running analysis
    - Generating recommendations
    - Executing approved changes
    - Producing reports
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        api_client: Optional[GoogleAdsClient] = None,
        data_store: Optional[DataStore] = None,
    ):
        """
        Initialize the intelligence system.

        Args:
            config: Configuration (uses defaults if not provided)
            api_client: Google Ads API client (creates new if not provided)
            data_store: Data storage (creates new if not provided)
        """
        self.config = config or Config.from_env()
        self.api_client = api_client or GoogleAdsClient(self.config)
        self.data_store = data_store or DataStore(self.config)

        # Initialize collectors
        self.campaign_collector = CampaignCollector(self.api_client, self.data_store, self.config)
        self.keyword_collector = KeywordCollector(self.api_client, self.data_store, self.config)
        self.search_term_collector = SearchTermCollector(self.api_client, self.data_store, self.config)
        self.geo_collector = GeoCollector(self.api_client, self.data_store, self.config)
        self.audience_collector = AudienceCollector(self.api_client, self.data_store, self.config)
        self.device_collector = DeviceCollector(self.api_client, self.data_store, self.config)
        self.schedule_collector = ScheduleCollector(self.api_client, self.data_store, self.config)
        self.change_collector = ChangeCollector(self.api_client, self.data_store, self.config)

        # Initialize analyzers and executors
        self.learning_detector = LearningPhaseDetector(self.data_store, self.config)
        self.recommendation_engine = RecommendationEngine(self.data_store, self.config)
        self.safe_executor = SafeExecutor(self.api_client, self.data_store, self.config)
        self.report_generator = ReportGenerator(self.config)

        logger.info("Google Ads Intelligence System initialized")

    def run_full_analysis(
        self,
        days: int = 30,
        include_geo: bool = True,
        include_audience: bool = True,
        include_device: bool = True,
        include_schedule: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a full analysis of the account.

        Args:
            days: Number of days to analyze
            include_geo: Include geographic analysis
            include_audience: Include audience analysis
            include_device: Include device analysis
            include_schedule: Include ad schedule analysis

        Returns:
            Complete analysis results
        """
        logger.info("Starting full analysis", days=days)

        start_date, end_date = get_date_range(days)

        # Collect data
        logger.info("Collecting campaign data...")
        campaigns = self.campaign_collector.collect(start_date, end_date)

        logger.info("Collecting keyword data...")
        keywords = self.keyword_collector.collect(start_date, end_date)

        logger.info("Collecting search term data...")
        search_terms = self.search_term_collector.collect(start_date, end_date)

        # Optional collectors
        geo_data = None
        audience_data = None
        device_data = None
        schedule_data = None

        if include_geo:
            logger.info("Collecting geo data...")
            geo_data = self.geo_collector.collect(start_date, end_date)

        if include_audience:
            logger.info("Collecting audience data...")
            audience_data = self.audience_collector.collect(start_date, end_date)

        if include_device:
            logger.info("Collecting device data...")
            device_data = self.device_collector.collect(start_date, end_date)

        if include_schedule:
            logger.info("Collecting schedule data...")
            schedule_data = self.schedule_collector.collect(start_date, end_date)

        # Collect change history
        logger.info("Collecting change history...")
        changes = self.change_collector.collect(start_date, end_date)

        # Identify entities in learning
        learning_entities = []
        for campaign in campaigns:
            status = self.learning_detector.is_in_learning("campaign", campaign.id)
            if status.is_in_learning:
                campaign.is_in_learning = True
                campaign.learning_reason = status.reason
                learning_entities.append({
                    "type": "campaign",
                    "id": campaign.id,
                    "name": campaign.name,
                    "reason": status.reason,
                    "days_remaining": status.days_remaining,
                })

        # Generate recommendations
        logger.info("Generating recommendations...")
        recommendations = self.recommendation_engine.generate_recommendations(
            campaigns=campaigns,
            keywords=keywords,
            search_terms=search_terms,
            geo_data=geo_data,
            audience_data=audience_data,
        )

        # Calculate account health
        account_health = self._calculate_account_health(campaigns, recommendations)

        # Generate report
        logger.info("Generating report...")
        report = self.report_generator.generate_daily_report(
            campaigns=campaigns,
            recommendations=recommendations,
            learning_status=learning_entities,
            account_health_score=account_health,
        )

        logger.info(
            "Analysis complete",
            campaigns=len(campaigns),
            keywords=len(keywords),
            search_terms=len(search_terms),
            recommendations=len(recommendations.recommendations),
        )

        return {
            "report": report,
            "data": {
                "campaigns": campaigns,
                "keywords": keywords,
                "search_terms": search_terms,
                "geo": geo_data,
                "audience": audience_data,
                "device": device_data,
                "schedule": schedule_data,
            },
            "recommendations": recommendations,
            "learning_entities": learning_entities,
            "account_health": account_health,
        }

    def run_quick_check(self) -> Dict[str, Any]:
        """
        Run a quick check (7 days, essential metrics only).

        Faster than full analysis, good for daily monitoring.
        """
        return self.run_full_analysis(
            days=7,
            include_geo=False,
            include_audience=False,
            include_device=False,
            include_schedule=False,
        )

    def execute_recommendations(
        self,
        recommendations: list,
        dry_run: bool = True,
        max_executions: int = None,
    ) -> list:
        """
        Execute approved recommendations.

        Args:
            recommendations: List of Recommendation objects to execute
            dry_run: If True, simulate without making changes
            max_executions: Maximum to execute (default: from config)

        Returns:
            List of ExecutionResults
        """
        return self.safe_executor.execute_batch(
            recommendations=recommendations,
            dry_run=dry_run,
            max_executions=max_executions,
        )

    def save_report(
        self,
        report: Dict[str, Any],
        output_dir: Path = None,
    ) -> Dict[str, Path]:
        """
        Save report to files.

        Args:
            report: Report data
            output_dir: Output directory

        Returns:
            Paths to saved files
        """
        return self.report_generator.save_report(report, output_dir)

    def print_report(self, report: Dict[str, Any]) -> None:
        """Print human-readable report to console."""
        text = self.report_generator.generate_human_readable(report)
        print(text)

    def _calculate_account_health(
        self,
        campaigns: list,
        recommendations,
    ) -> int:
        """Calculate overall account health score (0-100)."""
        score = 100

        # Penalize for campaigns in learning
        in_learning = sum(1 for c in campaigns if c.is_in_learning)
        if in_learning > 0:
            score -= min(20, in_learning * 5)

        # Penalize for high-risk recommendations
        from .models.recommendations import RiskLevel
        high_risk = sum(
            1 for r in recommendations.recommendations
            if r.risk_level == RiskLevel.HIGH
        )
        if high_risk > 0:
            score -= min(15, high_risk * 5)

        # Penalize for low conversion rates
        total_clicks = sum(c.metrics.clicks for c in campaigns if c.metrics)
        total_conv = sum(c.metrics.conversions for c in campaigns if c.metrics)
        if total_clicks > 0:
            conv_rate = total_conv / total_clicks * 100
            if conv_rate < 1:
                score -= 15
            elif conv_rate < 2:
                score -= 5

        return max(0, score)


def create_system(
    customer_id: str = None,
    developer_token: str = None,
    client_id: str = None,
    client_secret: str = None,
    refresh_token: str = None,
) -> GoogleAdsIntelligence:
    """
    Factory function to create a configured intelligence system.

    Args:
        customer_id: Google Ads customer ID
        developer_token: API developer token
        client_id: OAuth client ID
        client_secret: OAuth client secret
        refresh_token: OAuth refresh token

    Returns:
        Configured GoogleAdsIntelligence instance
    """
    config = Config.from_env()

    # Override with provided values
    if customer_id:
        config.customer_id = customer_id
    if developer_token:
        config.developer_token = developer_token
    if client_id:
        config.client_id = client_id
    if client_secret:
        config.client_secret = client_secret
    if refresh_token:
        config.refresh_token = refresh_token

    return GoogleAdsIntelligence(config=config)
