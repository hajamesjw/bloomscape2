"""Ad extension data collector."""

from typing import List, Dict, Any
from datetime import date

from .base_collector import BaseCollector
from ..models import Extension, Metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ExtensionCollector(BaseCollector):
    """Collects ad extension performance data."""

    # Asset (extension) performance query
    ASSET_QUERY = """
        SELECT
            asset.id,
            asset.name,
            asset.type,
            asset.text_asset.text,
            asset.sitelink_asset.link_text,
            asset.sitelink_asset.description1,
            asset.call_asset.phone_number,
            asset.callout_asset.callout_text,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            segments.date
        FROM asset_performance_label
        WHERE {date_filter}
            AND asset.type IN ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION')
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
    """

    # Sitelink-specific query (more detailed)
    SITELINK_QUERY = """
        SELECT
            asset.id,
            asset.sitelink_asset.link_text,
            asset.sitelink_asset.description1,
            asset.sitelink_asset.description2,
            asset.final_urls,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            segments.date
        FROM ad_group_asset
        WHERE {date_filter}
            AND ad_group_asset.field_type = 'SITELINK'
            AND metrics.impressions > 0
        ORDER BY metrics.clicks DESC
    """

    def collect(self, start_date: date, end_date: date) -> List[Extension]:
        """
        Collect extension performance data.

        Note: Extension data availability varies by account setup.
        """
        # Try collecting sitelink data specifically
        extensions = self._collect_sitelinks(start_date, end_date)

        logger.info("Collected extensions", count=len(extensions))
        return extensions

    def _collect_sitelinks(self, start_date: date, end_date: date) -> List[Extension]:
        """Collect sitelink extension data."""
        date_filter = self._build_date_filter(start_date, end_date)
        query = self.SITELINK_QUERY.format(date_filter=date_filter)

        try:
            results = self.api_client.execute_query(query)
        except Exception as e:
            logger.warning("Sitelink query failed", error=str(e))
            return []

        extension_data: Dict[str, Dict] = {}
        metrics_by_ext: Dict[str, List[Metrics]] = {}

        for row in results:
            ext_id = str(row.asset.id)

            if ext_id not in extension_data:
                sitelink = row.asset.sitelink_asset
                extension_data[ext_id] = {
                    "id": ext_id,
                    "extension_type": "sitelink",
                    "text": sitelink.link_text if sitelink else None,
                    "campaign_id": str(row.campaign.id),
                    "ad_group_id": str(row.ad_group.id) if row.ad_group.id else None,
                }
                metrics_by_ext[ext_id] = []

            metrics = self._extract_metrics(row)
            metrics_by_ext[ext_id].append(metrics)

        extensions = []
        for ext_id, data in extension_data.items():
            metrics_list = metrics_by_ext.get(ext_id, [])
            aggregated = self._aggregate_metrics(metrics_list) if metrics_list else None

            extension = Extension(
                id=data["id"],
                extension_type=data["extension_type"],
                text=data.get("text"),
                campaign_id=data.get("campaign_id"),
                ad_group_id=data.get("ad_group_id"),
                metrics=aggregated,
            )
            extensions.append(extension)

        return extensions

    def analyze_extension_performance(
        self,
        extensions: List[Extension],
    ) -> List[Extension]:
        """
        Analyze extension performance.

        Calculate CTR lift and identify under/over performers.
        """
        # Group by campaign to calculate baselines
        by_campaign: Dict[str, List[Extension]] = {}
        for ext in extensions:
            if ext.campaign_id not in by_campaign:
                by_campaign[ext.campaign_id] = []
            by_campaign[ext.campaign_id].append(ext)

        for campaign_id, campaign_exts in by_campaign.items():
            # Calculate average CTR for this campaign's extensions
            total_impressions = sum(e.metrics.impressions for e in campaign_exts if e.metrics)
            total_clicks = sum(e.metrics.clicks for e in campaign_exts if e.metrics)

            if total_impressions == 0:
                continue

            avg_ctr = (total_clicks / total_impressions) * 100

            for ext in campaign_exts:
                if ext.metrics and ext.metrics.impressions > 0:
                    ext_ctr = ext.metrics.ctr
                    if avg_ctr > 0:
                        ext.ctr_lift = ((ext_ctr - avg_ctr) / avg_ctr) * 100

        return extensions

    def get_top_sitelinks(
        self,
        extensions: List[Extension],
        campaign_id: str = None,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get top performing sitelinks."""
        sitelinks = [e for e in extensions if e.extension_type == "sitelink"]

        if campaign_id:
            sitelinks = [s for s in sitelinks if s.campaign_id == campaign_id]

        # Filter to those with clicks
        with_clicks = [s for s in sitelinks if s.metrics and s.metrics.clicks > 0]

        # Sort by CTR
        with_clicks.sort(
            key=lambda s: s.metrics.ctr if s.metrics else 0,
            reverse=True
        )

        return [
            {
                "text": s.text,
                "impressions": s.metrics.impressions,
                "clicks": s.metrics.clicks,
                "ctr": round(s.metrics.ctr, 2),
                "ctr_lift": round(s.ctr_lift, 1) if s.ctr_lift else None,
            }
            for s in with_clicks[:top_n]
        ]

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
            conversions=metrics.conversions if hasattr(metrics, 'conversions') else 0,
            conversion_value=0,
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
