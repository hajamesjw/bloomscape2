"""Change tracking data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Dict
from enum import Enum


class ChangeType(Enum):
    """Types of changes that can trigger learning."""
    BUDGET = "budget"
    BID_STRATEGY = "bid_strategy"
    BID_AMOUNT = "bid_amount"
    CREATIVE = "creative"
    TARGETING = "targeting"
    STATUS = "status"
    CONVERSION_ACTION = "conversion_action"
    GEO_TARGETING = "geo_targeting"
    AUDIENCE_TARGETING = "audience_targeting"
    KEYWORD_ADDED = "keyword_added"
    KEYWORD_REMOVED = "keyword_removed"
    AD_ADDED = "ad_added"
    AD_REMOVED = "ad_removed"


@dataclass
class ChangeEvent:
    """Record of a change made to an entity."""

    id: str
    entity_type: str
    entity_id: str
    entity_name: str
    change_type: ChangeType
    old_value: Any
    new_value: Any
    timestamp: datetime
    triggered_by: str  # "manual", "system", "recommendation_{id}"

    # Impact assessment
    triggers_learning: bool = False
    learning_days: int = 0

    # Outcome tracking
    follow_up_date: Optional[datetime] = None
    outcome_measured: bool = False
    actual_impact: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity": {
                "type": self.entity_type,
                "id": self.entity_id,
                "name": self.entity_name,
            },
            "change_type": self.change_type.value,
            "old_value": str(self.old_value),
            "new_value": str(self.new_value),
            "timestamp": self.timestamp.isoformat(),
            "triggered_by": self.triggered_by,
            "triggers_learning": self.triggers_learning,
            "learning_days": self.learning_days,
        }

    @classmethod
    def from_budget_change(
        cls,
        campaign_id: str,
        campaign_name: str,
        old_budget: float,
        new_budget: float,
        triggered_by: str = "system",
    ) -> "ChangeEvent":
        """Create a budget change event."""
        import uuid

        pct_change = abs((new_budget - old_budget) / old_budget * 100) if old_budget > 0 else 100
        triggers_learning = pct_change >= 20

        return cls(
            id=str(uuid.uuid4()),
            entity_type="campaign",
            entity_id=campaign_id,
            entity_name=campaign_name,
            change_type=ChangeType.BUDGET,
            old_value=old_budget,
            new_value=new_budget,
            timestamp=datetime.utcnow(),
            triggered_by=triggered_by,
            triggers_learning=triggers_learning,
            learning_days=7 if triggers_learning else 0,
        )
