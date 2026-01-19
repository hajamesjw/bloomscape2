"""Performance analysis module.

Analyzes trends across multiple time windows to distinguish:
- Normal volatility vs structural problems
- Temporary dips vs sustained decline
- Seasonal patterns vs real degradation
"""

from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from dataclasses import dataclass
import statistics

from ..config import Config, DEFAULT_CONFIG
from ..models import (
    Metrics,
    TrendAnalysis,
    TrendDirection,
    PatternType,
    Anomaly,
    SignificanceResult,
)
from ..utils.logging import get_logger
from ..utils.dates import get_date_range

logger = get_logger(__name__)


class PerformanceAnalyzer:
    """
    Time-aware performance analysis.

    Key principle: Never trust single-day performance.
    Always use 7+ day windows for decisions.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or DEFAULT_CONFIG
        self.time_windows = self.config.analysis.TIME_WINDOWS  # [1, 3, 7, 14, 30, 60, 90]

    def analyze_trend(
        self,
        metrics_history: List[Metrics],
        metric_name: str,
        entity_type: str = "campaign",
        entity_id: str = "",
    ) -> TrendAnalysis:
        """
        Analyze trend for a specific metric.

        Args:
            metrics_history: List of daily metrics (sorted by date descending)
            metric_name: Metric to analyze (e.g., "cpa", "conversion_rate", "roas")
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            TrendAnalysis with direction, confidence, and recommendation
        """
        if not metrics_history:
            return TrendAnalysis(
                entity_type=entity_type,
                entity_id=entity_id,
                metric=metric_name,
                direction=TrendDirection.STABLE,
                confidence=0.0,
                pattern=PatternType.RANDOM,
                recommendation="wait",
            )

        # Extract metric values by time window
        values_by_window = {}
        for window in self.time_windows:
            window_metrics = [m for m in metrics_history if self._is_within_window(m.date, window)]
            if window_metrics:
                values = [getattr(m, metric_name, 0) or 0 for m in window_metrics]
                values_by_window[window] = sum(values) / len(values) if values else 0

        if len(values_by_window) < 2:
            return TrendAnalysis(
                entity_type=entity_type,
                entity_id=entity_id,
                metric=metric_name,
                direction=TrendDirection.STABLE,
                confidence=0.0,
                pattern=PatternType.RANDOM,
                recommendation="wait",
                values_by_period=values_by_window,
            )

        # Calculate percent changes between windows
        percent_changes = {}
        sorted_windows = sorted(values_by_window.keys())
        for i in range(1, len(sorted_windows)):
            prev_window = sorted_windows[i - 1]
            curr_window = sorted_windows[i]
            prev_val = values_by_window[prev_window]
            curr_val = values_by_window[curr_window]

            if prev_val != 0:
                pct_change = ((curr_val - prev_val) / prev_val) * 100
                percent_changes[curr_window] = pct_change

        # Determine trend direction
        direction, confidence = self._determine_trend_direction(percent_changes, values_by_window)

        # Detect pattern
        pattern = self._detect_pattern(metrics_history, metric_name)

        # Generate recommendation
        recommendation = self._generate_recommendation(direction, confidence, pattern)

        # Calculate statistics
        all_values = [getattr(m, metric_name, 0) or 0 for m in metrics_history]
        mean_val = statistics.mean(all_values) if all_values else 0
        std_dev = statistics.stdev(all_values) if len(all_values) > 1 else 0
        cv = (std_dev / mean_val * 100) if mean_val != 0 else 0

        return TrendAnalysis(
            entity_type=entity_type,
            entity_id=entity_id,
            metric=metric_name,
            direction=direction,
            confidence=confidence,
            pattern=pattern,
            recommendation=recommendation,
            values_by_period=values_by_window,
            percent_changes=percent_changes,
            mean=mean_val,
            std_dev=std_dev,
            coefficient_of_variation=cv,
        )

    def detect_anomalies(
        self,
        metrics_history: List[Metrics],
        metric_name: str,
        entity_type: str = "campaign",
        entity_id: str = "",
        threshold_std: float = 2.0,
    ) -> List[Anomaly]:
        """
        Detect statistical anomalies in metric values.

        Args:
            metrics_history: List of daily metrics
            metric_name: Metric to analyze
            threshold_std: Number of standard deviations for anomaly detection

        Returns:
            List of detected anomalies
        """
        if len(metrics_history) < 7:
            return []

        values = [getattr(m, metric_name, 0) or 0 for m in metrics_history]
        dates = [m.date for m in metrics_history]

        mean_val = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0

        if std_dev == 0:
            return []

        anomalies = []
        for i, (value, metric_date) in enumerate(zip(values, dates)):
            deviation = abs(value - mean_val) / std_dev

            if deviation >= threshold_std:
                is_positive = value > mean_val

                # Determine severity
                if deviation >= 3:
                    severity = "critical"
                elif deviation >= 2.5:
                    severity = "warning"
                else:
                    severity = "info"

                # Identify possible causes
                causes = self._identify_possible_causes(
                    metrics_history, i, metric_name, is_positive
                )

                anomaly = Anomaly(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    metric=metric_name,
                    detected_at=metric_date,
                    value=value,
                    expected_value=mean_val,
                    deviation_std=deviation,
                    severity=severity,
                    is_positive=is_positive,
                    possible_causes=causes,
                )
                anomalies.append(anomaly)

        return anomalies

    def calculate_statistical_significance(
        self,
        values_before: List[float],
        values_after: List[float],
        min_practical_significance: float = 10.0,
    ) -> SignificanceResult:
        """
        Test statistical significance of a change.

        Args:
            values_before: Values before the change
            values_after: Values after the change
            min_practical_significance: Minimum % change to be practically significant

        Returns:
            SignificanceResult with p-value and effect size
        """
        if len(values_before) < 3 or len(values_after) < 3:
            return SignificanceResult(
                is_significant=False,
                p_value=1.0,
                effect_size=0.0,
                test_used="insufficient_data",
                sample_size_a=len(values_before),
                sample_size_b=len(values_after),
            )

        try:
            from scipy import stats

            # Use Mann-Whitney U test (non-parametric, doesn't assume normal distribution)
            statistic, p_value = stats.mannwhitneyu(
                values_before, values_after, alternative='two-sided'
            )
            test_used = "mann-whitney"

        except ImportError:
            # Fallback to simple t-test approximation
            mean_before = statistics.mean(values_before)
            mean_after = statistics.mean(values_after)
            std_before = statistics.stdev(values_before) if len(values_before) > 1 else 0
            std_after = statistics.stdev(values_after) if len(values_after) > 1 else 0

            # Simple z-score approximation
            pooled_std = ((std_before ** 2 + std_after ** 2) / 2) ** 0.5
            if pooled_std > 0:
                z_score = abs(mean_after - mean_before) / pooled_std
                # Approximate p-value
                p_value = max(0.001, 1 - min(0.999, z_score / 3))
            else:
                p_value = 1.0

            test_used = "z-approximation"

        # Calculate effect size (percentage change)
        mean_before = statistics.mean(values_before)
        mean_after = statistics.mean(values_after)

        if mean_before != 0:
            effect_size = ((mean_after - mean_before) / mean_before) * 100
        else:
            effect_size = 0.0

        # Significance requires both statistical AND practical significance
        is_significant = (
            p_value < 0.05
            and abs(effect_size) >= min_practical_significance
        )

        return SignificanceResult(
            is_significant=is_significant,
            p_value=p_value,
            effect_size=effect_size,
            test_used=test_used,
            sample_size_a=len(values_before),
            sample_size_b=len(values_after),
        )

    def compare_periods(
        self,
        metrics_history: List[Metrics],
        metric_name: str,
        period_1_days: int = 7,
        period_2_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Compare performance between two periods.

        Args:
            metrics_history: List of daily metrics (most recent first)
            metric_name: Metric to compare
            period_1_days: Days in recent period
            period_2_days: Days in comparison period

        Returns:
            Comparison results with significance test
        """
        # Split metrics into two periods
        period_1 = [m for m in metrics_history if self._is_within_window(m.date, period_1_days)]
        period_2_start = period_1_days
        period_2_end = period_1_days + period_2_days
        period_2 = [
            m for m in metrics_history
            if period_2_start < (date.today() - m.date).days <= period_2_end
        ]

        values_1 = [getattr(m, metric_name, 0) or 0 for m in period_1]
        values_2 = [getattr(m, metric_name, 0) or 0 for m in period_2]

        if not values_1 or not values_2:
            return {
                "comparison_valid": False,
                "reason": "Insufficient data in one or both periods",
            }

        significance = self.calculate_statistical_significance(values_2, values_1)

        mean_1 = statistics.mean(values_1)
        mean_2 = statistics.mean(values_2)

        return {
            "comparison_valid": True,
            "period_1": {
                "days": period_1_days,
                "mean": round(mean_1, 2),
                "data_points": len(values_1),
            },
            "period_2": {
                "days": period_2_days,
                "mean": round(mean_2, 2),
                "data_points": len(values_2),
            },
            "change_percent": round(significance.effect_size, 1),
            "is_significant": significance.is_significant,
            "p_value": round(significance.p_value, 4),
            "test_used": significance.test_used,
        }

    def _is_within_window(self, metric_date: date, window_days: int) -> bool:
        """Check if a date is within the specified window."""
        days_ago = (date.today() - metric_date).days
        return days_ago <= window_days

    def _determine_trend_direction(
        self,
        percent_changes: Dict[int, float],
        values_by_window: Dict[int, float],
    ) -> tuple:
        """Determine trend direction and confidence."""
        if not percent_changes:
            return TrendDirection.STABLE, 0.0

        changes = list(percent_changes.values())
        avg_change = sum(changes) / len(changes)

        # Calculate variance to detect volatility
        if len(changes) > 1:
            variance = sum((c - avg_change) ** 2 for c in changes) / len(changes)
        else:
            variance = 0

        # High variance indicates volatility
        if variance > 400:  # Threshold for volatility
            return TrendDirection.VOLATILE, 0.5

        # Determine direction based on average change
        if avg_change > 5:
            confidence = min(0.9, 0.5 + (avg_change / 30))
            return TrendDirection.IMPROVING, confidence
        elif avg_change < -5:
            confidence = min(0.9, 0.5 + (abs(avg_change) / 30))
            return TrendDirection.DECLINING, confidence
        else:
            return TrendDirection.STABLE, 0.7

    def _detect_pattern(
        self,
        metrics_history: List[Metrics],
        metric_name: str,
    ) -> PatternType:
        """Detect pattern in the data."""
        if len(metrics_history) < 14:
            return PatternType.RANDOM

        # Check for day-of-week pattern
        by_dow: Dict[int, List[float]] = {i: [] for i in range(7)}
        for m in metrics_history:
            dow = m.date.weekday()
            value = getattr(m, metric_name, 0) or 0
            by_dow[dow].append(value)

        # Calculate coefficient of variation across days
        dow_means = [statistics.mean(v) for v in by_dow.values() if v]
        if len(dow_means) >= 5:
            overall_mean = statistics.mean(dow_means)
            if overall_mean > 0:
                dow_cv = statistics.stdev(dow_means) / overall_mean if len(dow_means) > 1 else 0
                if dow_cv > 0.3:  # Significant day-of-week variation
                    return PatternType.DAY_OF_WEEK

        # Check for structural change (significant shift in level)
        if len(metrics_history) >= 30:
            first_half = [getattr(m, metric_name, 0) or 0 for m in metrics_history[:15]]
            second_half = [getattr(m, metric_name, 0) or 0 for m in metrics_history[15:30]]

            mean_first = statistics.mean(first_half) if first_half else 0
            mean_second = statistics.mean(second_half) if second_half else 0

            if mean_second > 0:
                change = abs(mean_first - mean_second) / mean_second
                if change > 0.3:  # 30% level shift
                    return PatternType.STRUCTURAL

        return PatternType.RANDOM

    def _generate_recommendation(
        self,
        direction: TrendDirection,
        confidence: float,
        pattern: PatternType,
    ) -> str:
        """Generate recommendation based on analysis."""
        if confidence < 0.5:
            return "wait"

        if direction == TrendDirection.VOLATILE:
            return "investigate"

        if direction == TrendDirection.DECLINING and confidence >= 0.7:
            if pattern == PatternType.STRUCTURAL:
                return "act"
            return "investigate"

        if direction == TrendDirection.IMPROVING and confidence >= 0.7:
            return "wait"  # Don't mess with what's working

        return "wait"

    def _identify_possible_causes(
        self,
        metrics_history: List[Metrics],
        anomaly_index: int,
        metric_name: str,
        is_positive: bool,
    ) -> List[str]:
        """Identify possible causes for an anomaly."""
        causes = []

        # Check if it's a weekend/holiday effect
        anomaly_date = metrics_history[anomaly_index].date
        if anomaly_date.weekday() >= 5:
            causes.append("Weekend effect")

        # Check if correlated with other metrics
        anomaly_metrics = metrics_history[anomaly_index]

        if metric_name == "cpa" and anomaly_metrics.clicks < 10:
            causes.append("Low click volume (statistical noise)")

        if metric_name == "conversion_rate" and anomaly_metrics.clicks < 50:
            causes.append("Insufficient click volume for reliable rate")

        if is_positive:
            causes.append("Possible positive external factor")
        else:
            causes.append("Possible negative external factor")

        return causes
