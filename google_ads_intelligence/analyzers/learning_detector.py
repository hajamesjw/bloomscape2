"""Learning phase detection module.

Critical for avoiding optimization during learning periods.
"""

from typing import Optional, Dict, List, Any
from datetime import date, datetime, timedelta
from dataclasses import dataclass

from ..config import Config, DEFAULT_CONFIG
from ..core.data_store import DataStore
from ..models import LearningStatus, DataSufficiency, ChangeEvent, ChangeType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class LearningPhaseDetector:
    """
    Detects when campaigns, ad groups, or keywords are in learning phase.

    CRITICAL: Never optimize entities in learning phase.

    Learning is triggered by:
    - Budget changes >= 20%
    - Bid strategy changes
    - Significant creative changes
    - Targeting changes
    - Conversion action changes
    """

    def __init__(self, data_store: DataStore, config: Optional[Config] = None):
        self.data_store = data_store
        self.config = config or DEFAULT_CONFIG

    def is_in_learning(
        self,
        entity_type: str,
        entity_id: str,
    ) -> LearningStatus:
        """
        Check if an entity is currently in learning phase.

        Args:
            entity_type: "campaign", "ad_group", "keyword"
            entity_id: Entity ID

        Returns:
            LearningStatus with details
        """
        # Get recent changes for this entity
        changes = self.data_store.get_recent_changes(
            entity_type=entity_type,
            entity_id=entity_id,
            days=30,
        )

        if not changes:
            return LearningStatus(is_in_learning=False)

        # Find the most recent learning-triggering change
        for change in changes:
            if not change.get("triggers_learning"):
                continue

            change_time = change.get("timestamp")
            if isinstance(change_time, str):
                change_time = datetime.fromisoformat(change_time)

            learning_days = change.get("learning_days", 7)
            learning_end = change_time + timedelta(days=learning_days)

            if datetime.utcnow() < learning_end:
                days_remaining = (learning_end - datetime.utcnow()).days

                return LearningStatus(
                    is_in_learning=True,
                    reason=change.get("change_type"),
                    triggered_at=change_time,
                    expected_completion=learning_end.date(),
                    days_remaining=days_remaining,
                )

        return LearningStatus(is_in_learning=False)

    def has_sufficient_data(
        self,
        entity_type: str,
        clicks: int,
        conversions: float,
        days_of_data: int,
    ) -> DataSufficiency:
        """
        Check if an entity has sufficient data for analysis.

        Args:
            entity_type: "campaign", "ad_group", "keyword", "ad"
            clicks: Total clicks
            conversions: Total conversions
            days_of_data: Days of data available

        Returns:
            DataSufficiency assessment
        """
        thresholds = self.config.analysis.MIN_DATA_THRESHOLDS.get(
            entity_type,
            {"clicks": 100, "conversions": 10, "days": 14}
        )

        required_clicks = thresholds["clicks"]
        required_conversions = thresholds["conversions"]
        required_days = thresholds["days"]

        # Calculate sufficiency score (0-1)
        click_score = min(1.0, clicks / required_clicks)
        conv_score = min(1.0, conversions / required_conversions)
        days_score = min(1.0, days_of_data / required_days)

        sufficiency_score = (click_score + conv_score + days_score) / 3

        is_sufficient = (
            clicks >= required_clicks
            and conversions >= required_conversions
            and days_of_data >= required_days
        )

        return DataSufficiency(
            is_sufficient=is_sufficient,
            clicks=clicks,
            conversions=conversions,
            days_of_data=days_of_data,
            required_clicks=required_clicks,
            required_conversions=required_conversions,
            required_days=required_days,
            sufficiency_score=sufficiency_score,
        )

    def get_days_since_last_change(
        self,
        entity_type: str,
        entity_id: str,
        change_type: Optional[str] = None,
    ) -> int:
        """
        Get days since last change for an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            change_type: Optional specific change type

        Returns:
            Days since last change (999 if no changes found)
        """
        last_change = self.data_store.get_last_change(
            entity_type=entity_type,
            entity_id=entity_id,
            change_type=change_type,
        )

        if not last_change:
            return 999

        change_time = last_change.get("timestamp")
        if isinstance(change_time, str):
            change_time = datetime.fromisoformat(change_time)

        if change_time:
            return (datetime.utcnow() - change_time).days

        return 999

    def can_make_changes(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        """
        Check if changes can be made to an entity.

        Returns a comprehensive assessment including:
        - Learning status
        - Data sufficiency
        - Days since last change
        - Whether changes are allowed
        """
        learning_status = self.is_in_learning(entity_type, entity_id)
        days_since_change = self.get_days_since_last_change(entity_type, entity_id)

        # Minimum stability window
        min_days = self.config.budget.MIN_DAYS_BETWEEN_CHANGES

        can_change = (
            not learning_status.is_in_learning
            and days_since_change >= min_days
        )

        reasons = []
        if learning_status.is_in_learning:
            reasons.append(f"In learning ({learning_status.days_remaining} days remaining)")
        if days_since_change < min_days:
            reasons.append(f"Recent change ({days_since_change} days ago, need {min_days})")

        return {
            "can_change": can_change,
            "learning_status": learning_status.to_dict(),
            "days_since_last_change": days_since_change,
            "reasons": reasons,
        }

    def get_entities_in_learning(
        self,
        entities: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Get all entities currently in learning phase.

        Args:
            entities: List of {"type": ..., "id": ..., "name": ...}

        Returns:
            List of entities in learning with details
        """
        in_learning = []

        for entity in entities:
            status = self.is_in_learning(entity["type"], entity["id"])
            if status.is_in_learning:
                in_learning.append({
                    "type": entity["type"],
                    "id": entity["id"],
                    "name": entity.get("name", ""),
                    "reason": status.reason,
                    "days_remaining": status.days_remaining,
                    "expected_completion": status.expected_completion.isoformat() if status.expected_completion else None,
                })

        return in_learning

    def estimate_learning_impact(
        self,
        change_type: ChangeType,
        entity_type: str,
        current_conversions: float,
    ) -> Dict[str, Any]:
        """
        Estimate the impact of triggering a learning phase.

        Args:
            change_type: Type of change being considered
            entity_type: Entity type
            current_conversions: Current daily conversion rate

        Returns:
            Estimated impact during learning period
        """
        learning_days = self.config.analysis.LEARNING_TRIGGERS.get(
            change_type.value,
            {"learning_days": 7}
        ).get("learning_days", 7)

        # During learning, expect ~20-30% performance degradation
        degradation_rate = 0.25
        estimated_lost_conversions = current_conversions * learning_days * degradation_rate

        return {
            "learning_days": learning_days,
            "expected_degradation_rate": degradation_rate,
            "estimated_lost_conversions": round(estimated_lost_conversions, 1),
            "recommendation": "Only make this change if expected long-term benefit exceeds short-term loss",
        }
