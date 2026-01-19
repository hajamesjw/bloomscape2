"""Ad schedule / dayparting data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import HourlyPerformance, Metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ScheduleCollector(BaseCollector):
    """Collects ad schedule / hour-of-day performance data."""

    HOURLY_QUERY = """
        SELECT
            campaign.id,
            campaign.name,
            segments.hour,
            segments.day_of_week,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM campaign
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
        ORDER BY campaign.id, segments.day_of_week, segments.hour
    """

    def collect(self, start_date: date, end_date: date) -> List[HourlyPerformance]:
        """
        Collect hourly performance data.

        Returns:
            List of HourlyPerformance objects
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.HOURLY_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting schedule data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by campaign + hour + day_of_week
        schedule_data: Dict[str, Dict] = {}
        metrics_by_schedule: Dict[str, List[Metrics]] = {}

        for row in results:
            campaign_id = str(row.campaign.id)
            hour = row.segments.hour
            day_of_week = self._get_day_of_week(row.segments.day_of_week)

            schedule_key = f"{campaign_id}|{day_of_week}|{hour}"

            if schedule_key not in schedule_data:
                schedule_data[schedule_key] = {
                    "hour": hour,
                    "day_of_week": day_of_week,
                    "campaign_id": campaign_id,
                }
                metrics_by_schedule[schedule_key] = []

            metrics = self._extract_metrics(row)
            metrics_by_schedule[schedule_key].append(metrics)

        # Build HourlyPerformance objects
        schedules = []
        for schedule_key, data in schedule_data.items():
            metrics_list = metrics_by_schedule.get(schedule_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            schedule = HourlyPerformance(
                hour=data["hour"],
                day_of_week=data["day_of_week"],
                campaign_id=data["campaign_id"],
                metrics=aggregated,
            )
            schedules.append(schedule)

        logger.info("Collected schedule data", count=len(schedules))
        return schedules

    def analyze_schedule_performance(
        self,
        schedules: List[HourlyPerformance],
    ) -> List[HourlyPerformance]:
        """
        Analyze schedule performance and recommend bid modifiers.

        Finds hours/days with significantly better or worse performance.
        """
        # Group by campaign
        by_campaign: Dict[str, List[HourlyPerformance]] = {}
        for schedule in schedules:
            if schedule.campaign_id not in by_campaign:
                by_campaign[schedule.campaign_id] = []
            by_campaign[schedule.campaign_id].append(schedule)

        # Analyze each campaign
        for campaign_id, campaign_schedules in by_campaign.items():
            # Calculate campaign totals
            total_cost = sum(s.metrics.cost for s in campaign_schedules if s.metrics)
            total_conversions = sum(s.metrics.conversions for s in campaign_schedules if s.metrics)

            if total_cost == 0 or total_conversions == 0:
                continue

            avg_cpa = total_cost / total_conversions

            for schedule in campaign_schedules:
                if schedule.metrics is None or schedule.metrics.cost == 0:
                    continue

                if schedule.metrics.conversions > 0:
                    schedule_cpa = schedule.metrics.cost / schedule.metrics.conversions

                    # Calculate performance vs average
                    schedule.performance_vs_average = (
                        (avg_cpa - schedule_cpa) / avg_cpa
                    ) * 100

                    # Recommend bid modifier (only with sufficient data)
                    if schedule.metrics.clicks >= 20:
                        if schedule.performance_vs_average > 30:
                            # Strong time slot
                            schedule.recommended_bid_modifier = min(
                                50, schedule.performance_vs_average
                            )
                        elif schedule.performance_vs_average < -40:
                            # Weak time slot
                            schedule.recommended_bid_modifier = max(
                                -80, schedule.performance_vs_average
                            )

        return schedules

    def get_best_hours(
        self,
        campaign_id: str,
        schedules: List[HourlyPerformance],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get the best performing hours for a campaign."""
        campaign_schedules = [s for s in schedules if s.campaign_id == campaign_id]

        # Filter to those with conversions
        with_conversions = [
            s for s in campaign_schedules
            if s.metrics and s.metrics.conversions > 0
        ]

        # Sort by CPA (lowest first)
        with_conversions.sort(key=lambda s: s.metrics.cpa if s.metrics.cpa else float("inf"))

        best = []
        for schedule in with_conversions[:top_n]:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            best.append({
                "day": day_names[schedule.day_of_week],
                "hour": schedule.hour,
                "cpa": schedule.metrics.cpa,
                "conversions": schedule.metrics.conversions,
                "cost": schedule.metrics.cost,
            })

        return best

    def get_worst_hours(
        self,
        campaign_id: str,
        schedules: List[HourlyPerformance],
        min_cost: float = 50,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get the worst performing hours for a campaign."""
        campaign_schedules = [s for s in schedules if s.campaign_id == campaign_id]

        # Filter to those with sufficient spend but poor performance
        poor_performers = [
            s for s in campaign_schedules
            if s.metrics and s.metrics.cost >= min_cost and (
                s.metrics.conversions == 0 or
                (s.metrics.cpa and s.metrics.cpa > s.metrics.cost / max(s.metrics.conversions, 0.1) * 1.5)
            )
        ]

        # Sort by cost (highest wasted spend first)
        poor_performers.sort(key=lambda s: s.metrics.cost if s.metrics else 0, reverse=True)

        worst = []
        for schedule in poor_performers[:top_n]:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            worst.append({
                "day": day_names[schedule.day_of_week],
                "hour": schedule.hour,
                "cost": schedule.metrics.cost,
                "conversions": schedule.metrics.conversions,
                "cpa": schedule.metrics.cpa if schedule.metrics.cpa else None,
            })

        return worst

    def _get_day_of_week(self, day_value: int) -> int:
        """Convert day of week enum to 0-6 (Monday=0)."""
        # Google Ads: MONDAY=2, TUESDAY=3, ..., SUNDAY=8
        day_map = {
            0: 0,  # UNSPECIFIED
            1: 0,  # UNKNOWN
            2: 0,  # MONDAY
            3: 1,  # TUESDAY
            4: 2,  # WEDNESDAY
            5: 3,  # THURSDAY
            6: 4,  # FRIDAY
            7: 5,  # SATURDAY
            8: 6,  # SUNDAY
        }
        return day_map.get(day_value, 0)

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
