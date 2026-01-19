"""Change history collector."""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta

from .base_collector import BaseCollector
from ..models import ChangeEvent, ChangeType
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ChangeCollector(BaseCollector):
    """Collects change history from Google Ads."""

    CHANGE_EVENT_QUERY = """
        SELECT
            change_event.resource_name,
            change_event.change_date_time,
            change_event.change_resource_type,
            change_event.change_resource_name,
            change_event.client_type,
            change_event.user_email,
            change_event.old_resource,
            change_event.new_resource,
            change_event.resource_change_operation,
            change_event.changed_fields
        FROM change_event
        WHERE change_event.change_date_time >= '{start_date}'
            AND change_event.change_date_time <= '{end_date}'
        ORDER BY change_event.change_date_time DESC
        LIMIT 1000
    """

    def collect(self, start_date: date, end_date: date) -> List[ChangeEvent]:
        """
        Collect change history for the date range.

        Returns:
            List of ChangeEvent objects
        """
        # Format dates for query
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

        query = self.CHANGE_EVENT_QUERY.format(
            start_date=start_str,
            end_date=end_str,
        )

        logger.info(
            "Collecting change history",
            start_date=start_str,
            end_date=end_str,
        )

        try:
            results = self.api_client.execute_query(query)
        except Exception as e:
            logger.warning("Change event query failed", error=str(e))
            return []

        changes = []
        for row in results:
            change = self._parse_change_event(row)
            if change:
                changes.append(change)

        logger.info("Collected change events", count=len(changes))
        return changes

    def get_entity_changes(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30,
    ) -> List[ChangeEvent]:
        """Get changes for a specific entity from the database."""
        return self.data_store.get_recent_changes(entity_type, entity_id, days)

    def get_last_significant_change(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Optional[ChangeEvent]:
        """Get the most recent significant change that would trigger learning."""
        changes = self.data_store.get_recent_changes(entity_type, entity_id, days=30)

        for change_dict in changes:
            if change_dict.get("triggers_learning"):
                return self._dict_to_change_event(change_dict)

        return None

    def days_since_last_change(
        self,
        entity_type: str,
        entity_id: str,
        change_type: Optional[str] = None,
    ) -> int:
        """Get days since last change of specified type."""
        last_change = self.data_store.get_last_change(entity_type, entity_id, change_type)

        if not last_change:
            return 999  # No changes found

        change_time = last_change.get("timestamp")
        if isinstance(change_time, str):
            change_time = datetime.fromisoformat(change_time)

        if change_time:
            delta = datetime.utcnow() - change_time
            return delta.days

        return 999

    def _parse_change_event(self, row: Any) -> Optional[ChangeEvent]:
        """Parse a change event from API response."""
        try:
            event = row.change_event

            # Determine change type
            change_type = self._determine_change_type(event)
            if not change_type:
                return None

            # Extract entity info from resource name
            entity_type, entity_id = self._parse_resource_name(event.change_resource_name)

            # Parse timestamp
            timestamp = datetime.strptime(
                event.change_date_time,
                "%Y-%m-%d %H:%M:%S"
            )

            # Determine triggerer
            triggered_by = "manual"
            if event.client_type == 2:  # API
                triggered_by = "system"
            elif event.user_email:
                triggered_by = f"user:{event.user_email}"

            # Determine if this triggers learning
            triggers_learning = self._triggers_learning(change_type, event)
            learning_days = self._get_learning_days(change_type) if triggers_learning else 0

            import uuid
            return ChangeEvent(
                id=str(uuid.uuid4()),
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name="",  # Would need additional query to get name
                change_type=change_type,
                old_value=str(event.old_resource)[:500] if event.old_resource else None,
                new_value=str(event.new_resource)[:500] if event.new_resource else None,
                timestamp=timestamp,
                triggered_by=triggered_by,
                triggers_learning=triggers_learning,
                learning_days=learning_days,
            )

        except Exception as e:
            logger.debug("Failed to parse change event", error=str(e))
            return None

    def _determine_change_type(self, event: Any) -> Optional[ChangeType]:
        """Determine the type of change from the event."""
        resource_type = event.change_resource_type
        changed_fields = event.changed_fields.paths if event.changed_fields else []

        # Resource type to change type mapping
        type_map = {
            3: ChangeType.BUDGET,  # CAMPAIGN_BUDGET
            2: None,  # CAMPAIGN - check changed fields
            5: None,  # AD_GROUP - check changed fields
            6: None,  # AD_GROUP_CRITERION (keyword)
            8: ChangeType.CREATIVE,  # AD_GROUP_AD
        }

        change_type = type_map.get(resource_type)

        if change_type is None and resource_type == 2:  # CAMPAIGN
            # Check what changed on the campaign
            for field in changed_fields:
                if "budget" in field.lower():
                    return ChangeType.BUDGET
                if "bidding_strategy" in field.lower():
                    return ChangeType.BID_STRATEGY
                if "target_cpa" in field.lower() or "target_roas" in field.lower():
                    return ChangeType.BID_STRATEGY
                if "geo_target" in field.lower():
                    return ChangeType.GEO_TARGETING

        if change_type is None and resource_type == 5:  # AD_GROUP
            for field in changed_fields:
                if "cpc_bid" in field.lower():
                    return ChangeType.BID_AMOUNT

        if change_type is None and resource_type == 6:  # KEYWORD
            operation = event.resource_change_operation
            if operation == 1:  # CREATE
                return ChangeType.KEYWORD_ADDED
            elif operation == 3:  # REMOVE
                return ChangeType.KEYWORD_REMOVED

        return change_type

    def _parse_resource_name(self, resource_name: str) -> tuple:
        """Parse resource name to get entity type and ID."""
        # Format: customers/123/campaigns/456
        parts = resource_name.split("/")

        if len(parts) >= 4:
            entity_type = parts[-2].rstrip("s")  # Remove plural 's'
            entity_id = parts[-1]
            return entity_type, entity_id

        return "unknown", ""

    def _triggers_learning(self, change_type: ChangeType, event: Any) -> bool:
        """Determine if this change triggers a learning period."""
        learning_triggers = {
            ChangeType.BUDGET,
            ChangeType.BID_STRATEGY,
            ChangeType.CREATIVE,
            ChangeType.TARGETING,
            ChangeType.CONVERSION_ACTION,
            ChangeType.GEO_TARGETING,
            ChangeType.AUDIENCE_TARGETING,
        }

        if change_type in learning_triggers:
            # For budget changes, check if significant (>20%)
            if change_type == ChangeType.BUDGET:
                # Would need to parse old/new values to determine
                return True

            return True

        return False

    def _get_learning_days(self, change_type: ChangeType) -> int:
        """Get learning period days for a change type."""
        learning_days = {
            ChangeType.BUDGET: 7,
            ChangeType.BID_STRATEGY: 14,
            ChangeType.CREATIVE: 7,
            ChangeType.TARGETING: 7,
            ChangeType.CONVERSION_ACTION: 14,
            ChangeType.GEO_TARGETING: 7,
            ChangeType.AUDIENCE_TARGETING: 7,
        }
        return learning_days.get(change_type, 7)

    def _dict_to_change_event(self, d: Dict[str, Any]) -> ChangeEvent:
        """Convert dictionary to ChangeEvent."""
        return ChangeEvent(
            id=d.get("change_id", ""),
            entity_type=d.get("entity_type", ""),
            entity_id=d.get("entity_id", ""),
            entity_name=d.get("entity_name", ""),
            change_type=ChangeType(d.get("change_type", "budget")),
            old_value=d.get("old_value"),
            new_value=d.get("new_value"),
            timestamp=d.get("timestamp", datetime.utcnow()),
            triggered_by=d.get("triggered_by", "unknown"),
            triggers_learning=d.get("triggers_learning", False),
            learning_days=d.get("learning_days", 0),
        )
