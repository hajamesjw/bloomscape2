"""Device performance data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import DevicePerformance, Metrics
from ..models.entities import DeviceType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DeviceCollector(BaseCollector):
    """Collects device-level performance data."""

    DEVICE_QUERY = """
        SELECT
            campaign.id,
            campaign.name,
            segments.device,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cross_device_conversions,
            segments.date
        FROM campaign
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
        ORDER BY campaign.id, segments.device, segments.date
    """

    def collect(self, start_date: date, end_date: date) -> List[DevicePerformance]:
        """
        Collect device performance data.

        Returns:
            List of DevicePerformance objects by campaign
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.DEVICE_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting device data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by campaign + device
        device_data: Dict[str, Dict] = {}
        metrics_by_device: Dict[str, List[Metrics]] = {}
        cross_device_by_key: Dict[str, float] = {}

        for row in results:
            campaign_id = str(row.campaign.id)
            device = self._get_device_type(row.segments.device)
            device_key = f"{campaign_id}|{device.value}"

            if device_key not in device_data:
                device_data[device_key] = {
                    "device": device,
                    "campaign_id": campaign_id,
                }
                metrics_by_device[device_key] = []
                cross_device_by_key[device_key] = 0

            metrics = self._extract_metrics(row)
            metrics_by_device[device_key].append(metrics)

            # Track cross-device conversions
            cross_device = self._safe_get(row, "metrics", "cross_device_conversions", default=0)
            cross_device_by_key[device_key] += cross_device

        # Build DevicePerformance objects
        devices = []
        for device_key, data in device_data.items():
            metrics_list = metrics_by_device.get(device_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            device_perf = DevicePerformance(
                device=data["device"],
                campaign_id=data["campaign_id"],
                metrics=aggregated,
                assisted_conversions=cross_device_by_key.get(device_key, 0),
            )
            devices.append(device_perf)

        logger.info("Collected device data", count=len(devices))
        return devices

    def analyze_device_performance(
        self,
        devices: List[DevicePerformance],
    ) -> List[DevicePerformance]:
        """
        Analyze device performance and recommend bid modifiers.

        Key insight: Mobile often looks bad on last-click but drives assists.
        """
        # Group by campaign
        by_campaign: Dict[str, List[DevicePerformance]] = {}
        for device in devices:
            if device.campaign_id not in by_campaign:
                by_campaign[device.campaign_id] = []
            by_campaign[device.campaign_id].append(device)

        # Analyze each campaign
        for campaign_id, campaign_devices in by_campaign.items():
            # Calculate campaign totals
            total_cost = sum(d.metrics.cost for d in campaign_devices if d.metrics)
            total_conversions = sum(d.metrics.conversions for d in campaign_devices if d.metrics)
            total_assisted = sum(d.assisted_conversions for d in campaign_devices)

            if total_cost == 0 or total_conversions == 0:
                continue

            avg_cpa = total_cost / total_conversions

            for device in campaign_devices:
                if device.metrics is None or device.metrics.cost == 0:
                    continue

                # Calculate true value including assists
                device_conversions = device.metrics.conversions
                device_assists = device.assisted_conversions

                # Give partial credit for assists (50% credit)
                adjusted_conversions = device_conversions + (device_assists * 0.5)

                if adjusted_conversions > 0:
                    adjusted_cpa = device.metrics.cost / adjusted_conversions
                else:
                    adjusted_cpa = float("inf")

                # Calculate recommended modifier
                if adjusted_cpa > 0 and avg_cpa > 0:
                    performance_ratio = avg_cpa / adjusted_cpa

                    if performance_ratio > 1.2:
                        # Performing better than average
                        device.recommended_bid_modifier = min(50, (performance_ratio - 1) * 100)
                    elif performance_ratio < 0.8:
                        # Performing worse than average
                        device.recommended_bid_modifier = max(-50, (performance_ratio - 1) * 100)

        return devices

    def _get_device_type(self, device_value: int) -> DeviceType:
        """Convert device enum value to DeviceType."""
        device_map = {
            0: DeviceType.DESKTOP,  # UNSPECIFIED
            1: DeviceType.DESKTOP,  # UNKNOWN
            2: DeviceType.MOBILE,
            3: DeviceType.TABLET,
            4: DeviceType.CONNECTED_TV,
            5: DeviceType.DESKTOP,  # OTHER
        }
        return device_map.get(device_value, DeviceType.DESKTOP)

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
