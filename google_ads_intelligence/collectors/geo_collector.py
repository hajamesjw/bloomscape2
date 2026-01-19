"""Geographic performance data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import GeoPerformance, Metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GeoCollector(BaseCollector):
    """Collects geographic performance data."""

    GEO_QUERY = """
        SELECT
            geographic_view.country_criterion_id,
            geographic_view.location_type,
            geo_target_constant.name,
            geo_target_constant.canonical_name,
            geo_target_constant.target_type,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM geographic_view
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """

    # More detailed location query (by user location)
    USER_LOCATION_QUERY = """
        SELECT
            user_location_view.country_criterion_id,
            user_location_view.targeting_location,
            geo_target_constant.name,
            geo_target_constant.canonical_name,
            geo_target_constant.target_type,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM user_location_view
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """

    def collect(self, start_date: date, end_date: date) -> List[GeoPerformance]:
        """
        Collect geographic performance data.

        Returns:
            List of GeoPerformance objects
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.GEO_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting geo data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by location + campaign
        geo_data: Dict[str, Dict] = {}
        metrics_by_geo: Dict[str, List[Metrics]] = {}

        for row in results:
            location_id = str(row.geographic_view.country_criterion_id)
            campaign_id = str(row.campaign.id)
            geo_key = f"{location_id}|{campaign_id}"

            if geo_key not in geo_data:
                geo_data[geo_key] = self._extract_geo_data(row)
                metrics_by_geo[geo_key] = []

            metrics = self._extract_metrics(row)
            metrics_by_geo[geo_key].append(metrics)

        # Build GeoPerformance objects
        geo_performances = []
        for geo_key, data in geo_data.items():
            metrics_list = metrics_by_geo.get(geo_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            geo_perf = GeoPerformance(
                location_id=data["location_id"],
                location_name=data["location_name"],
                location_type=data["location_type"],
                campaign_id=data["campaign_id"],
                metrics=aggregated,
            )
            geo_performances.append(geo_perf)

        logger.info("Collected geo data", count=len(geo_performances))
        return geo_performances

    def collect_by_campaign(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> List[GeoPerformance]:
        """Collect geo data for a specific campaign."""
        all_geo = self.collect(start_date, end_date)
        return [g for g in all_geo if g.campaign_id == campaign_id]

    def analyze_geo_performance(
        self,
        geo_performances: List[GeoPerformance],
    ) -> List[GeoPerformance]:
        """
        Analyze geo performance and flag candidates for exclusion or expansion.

        Adds analysis results to each GeoPerformance object.
        """
        if not geo_performances:
            return geo_performances

        # Calculate campaign averages
        campaign_metrics: Dict[str, Dict[str, float]] = {}

        for geo in geo_performances:
            if geo.metrics is None:
                continue

            if geo.campaign_id not in campaign_metrics:
                campaign_metrics[geo.campaign_id] = {
                    "total_cost": 0,
                    "total_conversions": 0,
                    "count": 0,
                }

            campaign_metrics[geo.campaign_id]["total_cost"] += geo.metrics.cost
            campaign_metrics[geo.campaign_id]["total_conversions"] += geo.metrics.conversions
            campaign_metrics[geo.campaign_id]["count"] += 1

        # Calculate average CPA by campaign
        campaign_avg_cpa: Dict[str, float] = {}
        for campaign_id, data in campaign_metrics.items():
            if data["total_conversions"] > 0:
                campaign_avg_cpa[campaign_id] = data["total_cost"] / data["total_conversions"]
            else:
                campaign_avg_cpa[campaign_id] = float("inf")

        # Analyze each geo
        for geo in geo_performances:
            if geo.metrics is None or geo.metrics.cost == 0:
                continue

            avg_cpa = campaign_avg_cpa.get(geo.campaign_id, 0)

            if avg_cpa > 0 and geo.metrics.cpa:
                geo.performance_vs_average = ((geo.metrics.cpa - avg_cpa) / avg_cpa) * 100

                # Flag for exclusion if CPA is 2x+ average with sufficient data
                if (
                    geo.metrics.cpa > avg_cpa * 2
                    and geo.metrics.cost >= 50
                    and geo.metrics.clicks >= 30
                ):
                    geo.is_exclusion_candidate = True

                # Flag for expansion if CPA is significantly better
                if geo.metrics.cpa < avg_cpa * 0.7 and geo.metrics.conversions >= 3:
                    geo.is_expansion_candidate = True

                    # Suggest bid modifier
                    improvement = (avg_cpa - geo.metrics.cpa) / avg_cpa
                    geo.recommended_bid_modifier = min(30, improvement * 50)  # Cap at +30%

        return geo_performances

    def _extract_geo_data(self, row: Any) -> Dict[str, Any]:
        """Extract geo data from API response row."""
        location_name = self._safe_get(row, "geo_target_constant", "canonical_name", default="Unknown")
        location_type = self._safe_get(row, "geo_target_constant", "target_type", default="UNKNOWN")

        # Convert location type enum
        type_map = {
            0: "unknown",
            1: "unknown",
            2: "country",
            3: "region",
            4: "city",
            5: "postal_code",
            6: "county",
            7: "metro",
            8: "neighborhood",
            9: "airport",
            10: "university",
        }

        return {
            "location_id": str(row.geographic_view.country_criterion_id),
            "location_name": location_name,
            "location_type": type_map.get(location_type, "unknown"),
            "campaign_id": str(row.campaign.id),
        }

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
