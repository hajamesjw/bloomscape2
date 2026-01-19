"""Keyword data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import Keyword, Metrics
from ..models.entities import EntityStatus, MatchType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class KeywordCollector(BaseCollector):
    """Collects keyword-level data and metrics."""

    KEYWORD_QUERY = """
        SELECT
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.status,
            ad_group_criterion.effective_cpc_bid_micros,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr,
            ad_group_criterion.quality_info.post_click_quality_score,
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
        FROM keyword_view
        WHERE {date_filter}
            AND ad_group_criterion.status != 'REMOVED'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """

    def collect(self, start_date: date, end_date: date) -> List[Keyword]:
        """
        Collect keyword data for the given date range.

        Returns:
            List of Keyword objects with metrics
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.KEYWORD_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting keyword data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by keyword
        keywords_data: Dict[str, Dict] = {}
        metrics_by_keyword: Dict[str, List[Metrics]] = {}

        for row in results:
            keyword_id = str(row.ad_group_criterion.criterion_id)

            if keyword_id not in keywords_data:
                keywords_data[keyword_id] = self._extract_keyword_data(row)
                metrics_by_keyword[keyword_id] = []

            metrics = self._extract_metrics(row)
            metrics_by_keyword[keyword_id].append(metrics)

        # Build Keyword objects
        keywords = []
        for keyword_id, data in keywords_data.items():
            metrics_list = metrics_by_keyword.get(keyword_id, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            keyword = Keyword(
                id=keyword_id,
                ad_group_id=data["ad_group_id"],
                campaign_id=data["campaign_id"],
                text=data["text"],
                match_type=data["match_type"],
                status=data["status"],
                cpc_bid=data.get("cpc_bid"),
                quality_score=data.get("quality_score"),
                expected_ctr=data.get("expected_ctr"),
                ad_relevance=data.get("ad_relevance"),
                landing_page_experience=data.get("landing_page_experience"),
                metrics=aggregated,
                metrics_history=metrics_list,
            )
            keywords.append(keyword)

        logger.info("Collected keywords", count=len(keywords))
        return keywords

    def _extract_keyword_data(self, row: Any) -> Dict[str, Any]:
        """Extract keyword data from API response row."""
        criterion = row.ad_group_criterion

        status_map = {
            0: EntityStatus.ENABLED,
            1: EntityStatus.ENABLED,
            2: EntityStatus.ENABLED,
            3: EntityStatus.PAUSED,
            4: EntityStatus.REMOVED,
        }

        match_type_map = {
            0: MatchType.BROAD,
            1: MatchType.BROAD,
            2: MatchType.EXACT,
            3: MatchType.PHRASE,
            4: MatchType.BROAD,
        }

        quality_info = self._safe_get(criterion, "quality_info")

        return {
            "text": criterion.keyword.text,
            "match_type": match_type_map.get(criterion.keyword.match_type, MatchType.BROAD),
            "status": status_map.get(criterion.status, EntityStatus.ENABLED),
            "ad_group_id": str(row.ad_group.id),
            "campaign_id": str(row.campaign.id),
            "cpc_bid": self._micros_to_currency(criterion.effective_cpc_bid_micros) if criterion.effective_cpc_bid_micros else None,
            "quality_score": quality_info.quality_score if quality_info else None,
            "expected_ctr": self._quality_score_label(quality_info.search_predicted_ctr) if quality_info else None,
            "ad_relevance": self._quality_score_label(quality_info.creative_quality_score) if quality_info else None,
            "landing_page_experience": self._quality_score_label(quality_info.post_click_quality_score) if quality_info else None,
        }

    def _quality_score_label(self, value: int) -> str:
        """Convert quality score enum to label."""
        labels = {
            0: "UNSPECIFIED",
            1: "UNKNOWN",
            2: "BELOW_AVERAGE",
            3: "AVERAGE",
            4: "ABOVE_AVERAGE",
        }
        return labels.get(value, "UNKNOWN")

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
