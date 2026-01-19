"""Report generation module.

Generates human-readable and JSON reports.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pathlib import Path
import json

from ..config import Config, DEFAULT_CONFIG
from ..models import Campaign, Metrics, LearningStatus
from ..models.recommendations import RecommendationBatch, Recommendation, RiskLevel
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """
    Generates comprehensive reports in multiple formats.

    Output formats:
    - JSON (for automation)
    - Human-readable text (for review)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG

    def generate_daily_report(
        self,
        campaigns: List[Campaign],
        recommendations: RecommendationBatch,
        learning_status: List[Dict[str, Any]],
        account_health_score: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive daily intelligence report.

        Args:
            campaigns: Campaign data with metrics
            recommendations: Generated recommendations
            learning_status: Entities currently in learning
            account_health_score: Overall account health (0-100)

        Returns:
            Report data structure
        """
        # Calculate key metrics
        total_spend_7d = sum(
            c.metrics.cost for c in campaigns if c.metrics
        )
        total_conv_7d = sum(
            c.metrics.conversions for c in campaigns if c.metrics
        )
        total_value_7d = sum(
            c.metrics.conversion_value for c in campaigns if c.metrics
        )

        cpa_7d = total_spend_7d / total_conv_7d if total_conv_7d > 0 else 0
        roas_7d = total_value_7d / total_spend_7d if total_spend_7d > 0 else 0

        report = {
            "report_date": date.today().isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "account_health": {
                "overall_score": account_health_score,
                "trend": self._determine_trend(campaigns),
                "alerts": self._generate_alerts(campaigns, recommendations),
            },
            "key_metrics_summary": {
                "spend_7d": round(total_spend_7d, 2),
                "conversions_7d": round(total_conv_7d, 1),
                "cpa_7d": round(cpa_7d, 2),
                "roas_7d": round(roas_7d, 2),
                "conversion_value_7d": round(total_value_7d, 2),
            },
            "learning_status": {
                "campaigns_in_learning": [
                    {
                        "name": ls.get("name", ""),
                        "reason": ls.get("reason", ""),
                        "days_remaining": ls.get("days_remaining", 0),
                    }
                    for ls in learning_status
                ],
                "count": len(learning_status),
            },
            "campaign_performance": [
                self._format_campaign_summary(c) for c in campaigns if c.metrics
            ],
            "recommendations": recommendations.to_dict(),
            "top_recommendations": [
                r.to_dict() for r in recommendations.recommendations[:5]
            ],
        }

        return report

    def generate_human_readable(
        self,
        report: Dict[str, Any],
    ) -> str:
        """
        Generate a human-readable text report.

        Args:
            report: Report data from generate_daily_report

        Returns:
            Formatted text report
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("    GOOGLE ADS DAILY INTELLIGENCE REPORT")
        lines.append("=" * 60)
        lines.append(f"Date: {report['report_date']}")
        lines.append(f"Account Health: {report['account_health']['overall_score']}/100 ({report['account_health']['trend']})")
        lines.append("")

        # Key Metrics
        metrics = report["key_metrics_summary"]
        lines.append("7-DAY PERFORMANCE")
        lines.append("-" * 40)
        lines.append(f"   Spend:           ${metrics['spend_7d']:,.2f}")
        lines.append(f"   Conversions:     {metrics['conversions_7d']:,.1f}")
        lines.append(f"   CPA:             ${metrics['cpa_7d']:,.2f}")
        lines.append(f"   ROAS:            {metrics['roas_7d']:.2f}x")
        lines.append("")

        # Learning Status
        learning = report["learning_status"]
        if learning["count"] > 0:
            lines.append("LEARNING STATUS")
            lines.append("-" * 40)
            for campaign in learning["campaigns_in_learning"]:
                lines.append(f"   * {campaign['name']}")
                lines.append(f"     Reason: {campaign['reason']}")
                lines.append(f"     Days remaining: {campaign['days_remaining']}")
            lines.append("")

        # Alerts
        alerts = report["account_health"]["alerts"]
        if alerts:
            lines.append("ALERTS")
            lines.append("-" * 40)
            for alert in alerts:
                lines.append(f"   [{alert['severity'].upper()}] {alert['message']}")
            lines.append("")

        # Top Recommendations
        lines.append("TOP RECOMMENDATIONS")
        lines.append("-" * 40)

        for i, rec in enumerate(report.get("top_recommendations", [])[:5], 1):
            risk = rec.get("risk_level", "unknown").upper()
            lines.append(f"")
            lines.append(f"   {i}. [{risk} RISK] {rec['action']}")
            lines.append(f"      Entity: {rec['entity']['name']} ({rec['entity']['type']})")
            if rec.get("expected_impact"):
                impact = rec["expected_impact"]
                lines.append(f"      Expected: {impact['change_percent']:+.1f}% {impact['metric']}")
            lines.append(f"      Confidence: {rec['confidence']:.0%}")
            lines.append(f"      Why: {rec['rationale'][:80]}...")

        lines.append("")

        # Campaign Performance Table
        lines.append("CAMPAIGN PERFORMANCE")
        lines.append("-" * 40)
        lines.append(f"{'Campaign':<30} {'Spend':>10} {'Conv':>8} {'CPA':>10}")
        lines.append("-" * 60)

        for camp in report.get("campaign_performance", [])[:10]:
            name = camp["name"][:28] + ".." if len(camp["name"]) > 30 else camp["name"]
            lines.append(
                f"{name:<30} ${camp['cost']:>8,.0f} {camp['conversions']:>8,.1f} ${camp['cpa']:>8,.2f}"
            )

        lines.append("")
        lines.append("=" * 60)
        lines.append("                    END REPORT")
        lines.append("=" * 60)

        return "\n".join(lines)

    def save_report(
        self,
        report: Dict[str, Any],
        output_dir: Path = None,
    ) -> Dict[str, Path]:
        """
        Save report to files.

        Args:
            report: Report data
            output_dir: Output directory (default: config reports_dir)

        Returns:
            Paths to saved files
        """
        output_dir = output_dir or self.config.reports_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        report_date = report["report_date"]
        timestamp = datetime.utcnow().strftime("%H%M%S")

        # Save JSON
        json_path = output_dir / f"report_{report_date}_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        # Save human-readable
        text_report = self.generate_human_readable(report)
        text_path = output_dir / f"report_{report_date}_{timestamp}.txt"
        with open(text_path, "w") as f:
            f.write(text_report)

        logger.info(
            "Reports saved",
            json_path=str(json_path),
            text_path=str(text_path),
        )

        return {
            "json": json_path,
            "text": text_path,
        }

    def _format_campaign_summary(self, campaign: Campaign) -> Dict[str, Any]:
        """Format campaign data for report."""
        metrics = campaign.metrics

        return {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status.value,
            "budget": campaign.budget_amount,
            "impressions": metrics.impressions if metrics else 0,
            "clicks": metrics.clicks if metrics else 0,
            "cost": metrics.cost if metrics else 0,
            "conversions": metrics.conversions if metrics else 0,
            "cpa": metrics.cpa if metrics and metrics.cpa else 0,
            "roas": metrics.roas if metrics and metrics.roas else 0,
            "ctr": metrics.ctr if metrics else 0,
            "is_in_learning": campaign.is_in_learning,
        }

    def _determine_trend(self, campaigns: List[Campaign]) -> str:
        """Determine overall account trend."""
        # Simple implementation - could be more sophisticated
        improving = 0
        declining = 0

        for campaign in campaigns:
            if not campaign.metrics_history or len(campaign.metrics_history) < 14:
                continue

            recent = campaign.metrics_history[:7]
            older = campaign.metrics_history[7:14]

            recent_cpa = sum(m.cpa or 0 for m in recent) / len(recent) if recent else 0
            older_cpa = sum(m.cpa or 0 for m in older) / len(older) if older else 0

            if older_cpa > 0:
                if recent_cpa < older_cpa * 0.9:
                    improving += 1
                elif recent_cpa > older_cpa * 1.1:
                    declining += 1

        if improving > declining:
            return "improving"
        elif declining > improving:
            return "declining"
        return "stable"

    def _generate_alerts(
        self,
        campaigns: List[Campaign],
        recommendations: RecommendationBatch,
    ) -> List[Dict[str, Any]]:
        """Generate alert messages for the report."""
        alerts = []

        # Check for high-risk recommendations
        high_risk = [
            r for r in recommendations.recommendations
            if r.risk_level == RiskLevel.HIGH
        ]
        if high_risk:
            alerts.append({
                "severity": "warning",
                "message": f"{len(high_risk)} high-risk recommendations require manual review",
            })

        # Check for campaigns with sudden drops
        for campaign in campaigns:
            if not campaign.metrics_history or len(campaign.metrics_history) < 7:
                continue

            recent_conv = sum(m.conversions for m in campaign.metrics_history[:3])
            prior_conv = sum(m.conversions for m in campaign.metrics_history[3:7])

            if prior_conv > 0 and recent_conv < prior_conv * 0.5:
                alerts.append({
                    "severity": "critical",
                    "message": f"Campaign '{campaign.name}' conversions dropped >50% in last 3 days",
                })

        return alerts
