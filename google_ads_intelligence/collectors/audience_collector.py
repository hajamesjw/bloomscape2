"""Audience performance data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import AudiencePerformance, Metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AudienceCollector(BaseCollector):
    """Collects audience segment performance data."""

    AUDIENCE_QUERY = """
        SELECT
            ad_group_audience_view.resource_name,
            ad_group_criterion.criterion_id,
            ad_group_criterion.display_name,
            ad_group_criterion.type,
            ad_group.id,
            ad_group.name,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM ad_group_audience_view
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
            AND ad_group.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """

    # Campaign-level audience targeting
    CAMPAIGN_AUDIENCE_QUERY = """
        SELECT
            campaign_audience_view.resource_name,
            campaign_criterion.criterion_id,
            campaign_criterion.display_name,
            campaign_criterion.type,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM campaign_audience_view
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """

    def collect(self, start_date: date, end_date: date) -> List[AudiencePerformance]:
        """
        Collect audience performance data at ad group level.

        Returns:
            List of AudiencePerformance objects
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.AUDIENCE_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting audience data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        try:
            results = self.api_client.execute_query(query)
        except Exception as e:
            logger.warning("Audience query failed, may not have audience targeting", error=str(e))
            return []

        # Group by audience + ad group
        audience_data: Dict[str, Dict] = {}
        metrics_by_audience: Dict[str, List[Metrics]] = {}

        for row in results:
            audience_id = str(row.ad_group_criterion.criterion_id)
            ad_group_id = str(row.ad_group.id)
            audience_key = f"{audience_id}|{ad_group_id}"

            if audience_key not in audience_data:
                audience_data[audience_key] = self._extract_audience_data(row)
                metrics_by_audience[audience_key] = []

            metrics = self._extract_metrics(row)
            metrics_by_audience[audience_key].append(metrics)

        # Build AudiencePerformance objects
        audiences = []
        for audience_key, data in audience_data.items():
            metrics_list = metrics_by_audience.get(audience_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            audience = AudiencePerformance(
                audience_id=data["audience_id"],
                audience_name=data["audience_name"],
                audience_type=data["audience_type"],
                campaign_id=data["campaign_id"],
                ad_group_id=data.get("ad_group_id"),
                metrics=aggregated,
            )
            audiences.append(audience)

        logger.info("Collected audiences", count=len(audiences))
        return audiences

    def collect_campaign_audiences(self, start_date: date, end_date: date) -> List[AudiencePerformance]:
        """Collect audience performance at campaign level."""
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.CAMPAIGN_AUDIENCE_QUERY.format(date_filter=date_filter)

        try:
            results = self.api_client.execute_query(query)
        except Exception as e:
            logger.warning("Campaign audience query failed", error=str(e))
            return []

        audience_data: Dict[str, Dict] = {}
        metrics_by_audience: Dict[str, List[Metrics]] = {}

        for row in results:
            audience_id = str(row.campaign_criterion.criterion_id)
            campaign_id = str(row.campaign.id)
            audience_key = f"{audience_id}|{campaign_id}"

            if audience_key not in audience_data:
                audience_data[audience_key] = {
                    "audience_id": audience_id,
                    "audience_name": row.campaign_criterion.display_name or "Unknown",
                    "audience_type": self._get_audience_type(row.campaign_criterion.type),
                    "campaign_id": campaign_id,
                }
                metrics_by_audience[audience_key] = []

            metrics = self._extract_metrics(row)
            metrics_by_audience[audience_key].append(metrics)

        audiences = []
        for audience_key, data in audience_data.items():
            metrics_list = metrics_by_audience.get(audience_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            audience = AudiencePerformance(
                audience_id=data["audience_id"],
                audience_name=data["audience_name"],
                audience_type=data["audience_type"],
                campaign_id=data["campaign_id"],
                metrics=aggregated,
            )
            audiences.append(audience)

        return audiences

    def analyze_audience_performance(
        self,
        audiences: List[AudiencePerformance],
        baseline_cpa: float,
    ) -> List[AudiencePerformance]:
        """
        Analyze audience performance vs baseline.

        Args:
            audiences: List of audience performance data
            baseline_cpa: Account or campaign baseline CPA

        Returns:
            Audiences with analysis results added
        """
        for audience in audiences:
            if audience.metrics is None or audience.metrics.cost == 0:
                continue

            if audience.metrics.cpa and baseline_cpa > 0:
                # Calculate performance vs baseline
                audience.performance_vs_baseline = (
                    (baseline_cpa - audience.metrics.cpa) / baseline_cpa
                ) * 100

                # Recommend bid modifier based on performance
                if audience.metrics.conversions >= 3:  # Minimum data
                    if audience.performance_vs_baseline > 20:
                        # Strong performer - increase bids
                        audience.recommended_bid_modifier = min(
                            50, audience.performance_vs_baseline
                        )
                    elif audience.performance_vs_baseline < -30:
                        # Weak performer - decrease bids
                        audience.recommended_bid_modifier = max(
                            -50, audience.performance_vs_baseline
                        )

        return audiences

    def _extract_audience_data(self, row: Any) -> Dict[str, Any]:
        """Extract audience data from API response row."""
        criterion = row.ad_group_criterion

        return {
            "audience_id": str(criterion.criterion_id),
            "audience_name": criterion.display_name or "Unknown",
            "audience_type": self._get_audience_type(criterion.type),
            "campaign_id": str(row.campaign.id),
            "ad_group_id": str(row.ad_group.id),
        }

    def _get_audience_type(self, type_value: int) -> str:
        """Convert criterion type to audience type string."""
        type_map = {
            0: "unknown",
            3: "keyword",
            4: "placement",
            6: "custom_affinity",
            7: "custom_intent",
            8: "age_range",
            9: "gender",
            10: "income_range",
            11: "parental_status",
            12: "remarketing",
            13: "in_market",
            14: "affinity",
            15: "similar_users",
            16: "combined_audience",
        }
        return type_map.get(type_value, "unknown")

    def _extract_metrics(self, row: Any) -> Metrics:
        """Extract metrics from API response row."""
        metrics = row.metrics
        segment_date = row.segments.date

        from datetime import datetime
        metric_date = datetime.strptime(segment_date, "%Y-%m-%d").date()

        return Metrics(
            date=metric_date,
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            cost=self._micros_to_currency(metrics.cost_micros),
            conversions=metrics.conversions,
            conversion_value=metrics.conversions_value,
        )

    def _aggregate_metrics(self, metrics_list: List[Metrics]) -> Metrics:
        """Aggregate metrics."""
        if not metrics_list:
            return None

        return Metrics(
            date=metrics_list[0].date,
            impressions=sum(m.impressions for m in metrics_list),
            clicks=sum(m.clicks for m in metrics_list),
            cost=sum(m.cost for m in metrics_list),
            conversions=sum(m.conversions for m in metrics_list),
            conversion_value=sum(m.conversion_value for m in metrics_list),
        )
