"""Campaign data collector."""

from typing import List, Dict, Any, Optional
from datetime import date

from .base_collector import BaseCollector
from ..models import Campaign, Metrics
from ..models.entities import EntityStatus, BidStrategyType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CampaignCollector(BaseCollector):
    """Collects campaign-level data and metrics."""

    CAMPAIGN_QUERY = """
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign_budget.amount_micros,
            campaign.bidding_strategy_type,
            campaign.target_cpa.target_cpa_micros,
            campaign.target_roas.target_roas,
            campaign.start_date,
            campaign.end_date,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share,
            segments.date
        FROM campaign
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
        ORDER BY segments.date DESC
    """

    def collect(self, start_date: date, end_date: date) -> List[Campaign]:
        """
        Collect campaign data for the given date range.

        Returns:
            List of Campaign objects with metrics
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.CAMPAIGN_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting campaign data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by campaign
        campaigns_data: Dict[str, Dict] = {}
        metrics_by_campaign: Dict[str, List[Metrics]] = {}

        for row in results:
            campaign_id = str(row.campaign.id)

            if campaign_id not in campaigns_data:
                campaigns_data[campaign_id] = self._extract_campaign_data(row)
                metrics_by_campaign[campaign_id] = []

            metrics = self._extract_metrics(row)
            metrics_by_campaign[campaign_id].append(metrics)

        # Build Campaign objects
        campaigns = []
        for campaign_id, data in campaigns_data.items():
            metrics_list = metrics_by_campaign.get(campaign_id, [])

            # Aggregate metrics for the latest snapshot
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            campaign = Campaign(
                id=campaign_id,
                name=data["name"],
                status=data["status"],
                budget_amount=data["budget_amount"],
                bid_strategy_type=data["bid_strategy_type"],
                target_cpa=data.get("target_cpa"),
                target_roas=data.get("target_roas"),
                start_date=data.get("start_date"),
                metrics=aggregated,
                metrics_history=metrics_list,
            )
            campaigns.append(campaign)

        logger.info("Collected campaigns", count=len(campaigns))

        # Store metrics in database
        self._store_metrics(campaigns_data, metrics_by_campaign)

        return campaigns

    def collect_current_state(self) -> List[Campaign]:
        """Collect current campaign configuration (no metrics)."""
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign_budget.amount_micros,
                campaign.bidding_strategy_type,
                campaign.target_cpa.target_cpa_micros,
                campaign.target_roas.target_roas,
                campaign.start_date,
                campaign.end_date
            FROM campaign
            WHERE campaign.status != 'REMOVED'
        """

        results = self.api_client.execute_query(query)
        campaigns = []

        for row in results:
            data = self._extract_campaign_data(row)
            campaign = Campaign(
                id=str(row.campaign.id),
                name=data["name"],
                status=data["status"],
                budget_amount=data["budget_amount"],
                bid_strategy_type=data["bid_strategy_type"],
                target_cpa=data.get("target_cpa"),
                target_roas=data.get("target_roas"),
            )
            campaigns.append(campaign)

        return campaigns

    def _extract_campaign_data(self, row: Any) -> Dict[str, Any]:
        """Extract campaign data from API response row."""
        status_map = {
            0: EntityStatus.ENABLED,  # UNSPECIFIED
            1: EntityStatus.ENABLED,  # UNKNOWN
            2: EntityStatus.ENABLED,  # ENABLED
            3: EntityStatus.PAUSED,   # PAUSED
            4: EntityStatus.REMOVED,  # REMOVED
        }

        bid_strategy_map = {
            0: None,
            1: None,
            2: BidStrategyType.MANUAL_CPC,
            3: BidStrategyType.ENHANCED_CPC,
            5: BidStrategyType.MAXIMIZE_CONVERSIONS,
            6: BidStrategyType.MAXIMIZE_CONVERSION_VALUE,
            9: BidStrategyType.TARGET_CPA,
            10: BidStrategyType.TARGET_IMPRESSION_SHARE,
            11: BidStrategyType.TARGET_ROAS,
            12: BidStrategyType.MAXIMIZE_CLICKS,
        }

        budget_micros = self._safe_get(row, "campaign_budget", "amount_micros", default=0)
        target_cpa_micros = self._safe_get(row, "campaign", "target_cpa", "target_cpa_micros", default=0)
        bid_strategy_value = self._safe_get(row, "campaign", "bidding_strategy_type", default=0)

        return {
            "name": row.campaign.name,
            "status": status_map.get(row.campaign.status, EntityStatus.ENABLED),
            "budget_amount": self._micros_to_currency(budget_micros),
            "bid_strategy_type": bid_strategy_map.get(bid_strategy_value),
            "target_cpa": self._micros_to_currency(target_cpa_micros) if target_cpa_micros else None,
            "target_roas": self._safe_get(row, "campaign", "target_roas", "target_roas"),
            "start_date": self._safe_get(row, "campaign", "start_date"),
        }

    def _extract_metrics(self, row: Any) -> Metrics:
        """Extract metrics from API response row."""
        metrics = row.metrics
        segment_date = row.segments.date

        # Parse date string (format: YYYY-MM-DD)
        from datetime import datetime
        metric_date = datetime.strptime(segment_date, "%Y-%m-%d").date()

        return Metrics(
            date=metric_date,
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            cost=self._micros_to_currency(metrics.cost_micros),
            conversions=metrics.conversions,
            conversion_value=metrics.conversions_value,
            ctr=metrics.ctr * 100 if metrics.ctr else 0,
            cpc=self._micros_to_currency(metrics.average_cpc) if metrics.average_cpc else 0,
            impression_share=metrics.search_impression_share if metrics.search_impression_share else None,
            impression_share_lost_budget=metrics.search_budget_lost_impression_share if metrics.search_budget_lost_impression_share else None,
            impression_share_lost_rank=metrics.search_rank_lost_impression_share if metrics.search_rank_lost_impression_share else None,
        )

    def _aggregate_metrics(self, metrics_list: List[Metrics]) -> Metrics:
        """Aggregate a list of daily metrics into a summary."""
        if not metrics_list:
            return None

        total_impressions = sum(m.impressions for m in metrics_list)
        total_clicks = sum(m.clicks for m in metrics_list)
        total_cost = sum(m.cost for m in metrics_list)
        total_conversions = sum(m.conversions for m in metrics_list)
        total_conversion_value = sum(m.conversion_value for m in metrics_list)

        # Average impression share (where available)
        is_values = [m.impression_share for m in metrics_list if m.impression_share is not None]
        avg_impression_share = sum(is_values) / len(is_values) if is_values else None

        return Metrics(
            date=metrics_list[0].date,  # Most recent date
            impressions=total_impressions,
            clicks=total_clicks,
            cost=total_cost,
            conversions=total_conversions,
            conversion_value=total_conversion_value,
            impression_share=avg_impression_share,
        )

    def _store_metrics(
        self,
        campaigns_data: Dict[str, Dict],
        metrics_by_campaign: Dict[str, List[Metrics]],
    ) -> None:
        """Store campaign metrics in database."""
        records = []

        for campaign_id, metrics_list in metrics_by_campaign.items():
            campaign_data = campaigns_data.get(campaign_id, {})

            for metrics in metrics_list:
                record = {
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_data.get("name", ""),
                    "date": metrics.date,
                    "impressions": metrics.impressions,
                    "clicks": metrics.clicks,
                    "cost": metrics.cost,
                    "conversions": metrics.conversions,
                    "conversion_value": metrics.conversion_value,
                    "ctr": metrics.ctr,
                    "cpc": metrics.cpc,
                    "cpa": metrics.cpa if metrics.cpa else None,
                    "roas": metrics.roas if metrics.roas else None,
                    "impression_share": metrics.impression_share,
                    "impression_share_lost_budget": metrics.impression_share_lost_budget,
                    "impression_share_lost_rank": metrics.impression_share_lost_rank,
                    "budget_amount": campaign_data.get("budget_amount"),
                    "bid_strategy_type": str(campaign_data.get("bid_strategy_type")) if campaign_data.get("bid_strategy_type") else None,
                }
                records.append(record)

        if records:
            self.data_store.save_campaign_metrics(records)
