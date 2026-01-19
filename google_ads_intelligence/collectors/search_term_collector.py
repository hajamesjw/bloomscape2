"""Search term data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import SearchTerm, Metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SearchTermCollector(BaseCollector):
    """Collects search term report data."""

    SEARCH_TERM_QUERY = """
        SELECT
            search_term_view.search_term,
            search_term_view.status,
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
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
        FROM search_term_view
        WHERE {date_filter}
            AND campaign.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 10000
    """

    def collect(self, start_date: date, end_date: date) -> List[SearchTerm]:
        """
        Collect search term data for the given date range.

        Returns:
            List of SearchTerm objects with metrics
        """
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.SEARCH_TERM_QUERY.format(date_filter=date_filter)

        logger.info(
            "Collecting search term data",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        results = self.api_client.execute_query(query)

        # Group by search term + keyword combination
        terms_data: Dict[str, Dict] = {}
        metrics_by_term: Dict[str, List[Metrics]] = {}

        for row in results:
            # Create unique key for term-keyword combo
            term_key = f"{row.search_term_view.search_term}|{row.ad_group_criterion.criterion_id}"

            if term_key not in terms_data:
                terms_data[term_key] = self._extract_term_data(row)
                metrics_by_term[term_key] = []

            metrics = self._extract_metrics(row)
            metrics_by_term[term_key].append(metrics)

        # Build SearchTerm objects
        search_terms = []
        for term_key, data in terms_data.items():
            metrics_list = metrics_by_term.get(term_key, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            search_term = SearchTerm(
                query=data["query"],
                keyword_id=data["keyword_id"],
                keyword_text=data["keyword_text"],
                ad_group_id=data["ad_group_id"],
                campaign_id=data["campaign_id"],
                metrics=aggregated,
            )
            search_terms.append(search_term)

        logger.info("Collected search terms", count=len(search_terms))
        return search_terms

    def collect_negative_candidates(
        self,
        start_date: date,
        end_date: date,
        min_cost: float = 50.0,
        min_clicks: int = 20,
        max_conversions: float = 0.0,
    ) -> List[SearchTerm]:
        """
        Collect search terms that are candidates for negative keywords.

        Criteria:
        - Minimum spend threshold
        - Minimum clicks threshold
        - Zero or very few conversions
        """
        all_terms = self.collect(start_date, end_date)

        candidates = []
        for term in all_terms:
            if term.metrics is None:
                continue

            if (
                term.metrics.cost >= min_cost
                and term.metrics.clicks >= min_clicks
                and term.metrics.conversions <= max_conversions
            ):
                term.is_negative_candidate = True
                candidates.append(term)

        logger.info(
            "Found negative keyword candidates",
            count=len(candidates),
            criteria={"min_cost": min_cost, "min_clicks": min_clicks, "max_conversions": max_conversions},
        )

        return candidates

    def collect_promotion_candidates(
        self,
        start_date: date,
        end_date: date,
        min_conversions: float = 3.0,
        min_conversion_rate: float = 2.0,
    ) -> List[SearchTerm]:
        """
        Collect high-performing search terms that could be promoted to exact match.

        Criteria:
        - Minimum conversions
        - Strong conversion rate
        """
        all_terms = self.collect(start_date, end_date)

        candidates = []
        for term in all_terms:
            if term.metrics is None:
                continue

            if (
                term.metrics.conversions >= min_conversions
                and term.metrics.conversion_rate >= min_conversion_rate
            ):
                term.is_promotion_candidate = True
                candidates.append(term)

        logger.info(
            "Found promotion candidates",
            count=len(candidates),
        )

        return candidates

    def _extract_term_data(self, row: Any) -> Dict[str, Any]:
        """Extract search term data from API response row."""
        return {
            "query": row.search_term_view.search_term,
            "keyword_id": str(row.ad_group_criterion.criterion_id),
            "keyword_text": row.ad_group_criterion.keyword.text,
            "ad_group_id": str(row.ad_group.id),
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
