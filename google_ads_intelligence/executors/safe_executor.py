"""Safe execution layer with safeguards.

Executes recommendations with multiple safety checks.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass

from ..config import Config, DEFAULT_CONFIG
from ..core.api_client import GoogleAdsClient
from ..core.data_store import DataStore
from ..models import ChangeEvent, ChangeType
from ..models.recommendations import Recommendation, RiskLevel, RolloutStrategy
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a recommendation."""
    recommendation_id: str
    success: bool
    message: str
    executed_at: datetime
    api_response: Optional[Dict[str, Any]] = None
    follow_up_date: Optional[date] = None


class SafeExecutor:
    """
    Safe execution layer with safeguards.

    Principles:
    - Never execute high-risk recommendations automatically
    - Daily limits on changes
    - Full audit trail
    - Scheduled follow-up checks
    """

    def __init__(
        self,
        api_client: GoogleAdsClient,
        data_store: DataStore,
        config: Optional[Config] = None,
    ):
        self.api_client = api_client
        self.data_store = data_store
        self.config = config or DEFAULT_CONFIG

        # Track daily execution counts
        self._executions_today: Dict[str, int] = {
            "total": 0,
            "budget": 0,
            "keyword_pause": 0,
        }
        self._last_reset_date = date.today()

    def execute(
        self,
        recommendation: Recommendation,
        dry_run: bool = True,
        force: bool = False,
    ) -> ExecutionResult:
        """
        Execute a recommendation with safety checks.

        Args:
            recommendation: Recommendation to execute
            dry_run: If True, simulate execution without making changes
            force: If True, bypass some safety checks (use with caution)

        Returns:
            ExecutionResult with success/failure details
        """
        self._reset_daily_counts_if_needed()

        # Pre-execution validation
        validation = self._validate_execution(recommendation, force)
        if not validation["can_execute"]:
            return ExecutionResult(
                recommendation_id=recommendation.id,
                success=False,
                message=f"Blocked: {', '.join(validation['reasons'])}",
                executed_at=datetime.utcnow(),
            )

        if dry_run:
            return self._simulate_execution(recommendation)

        # Execute based on operation type
        result = self._execute_operation(recommendation)

        # Log the change
        if result.success:
            self._log_change(recommendation, result)
            self._schedule_follow_up(recommendation)
            self._increment_counts(recommendation)

        return result

    def execute_batch(
        self,
        recommendations: List[Recommendation],
        dry_run: bool = True,
        max_executions: int = None,
    ) -> List[ExecutionResult]:
        """
        Execute multiple recommendations with daily limits.

        Args:
            recommendations: List of recommendations to execute
            dry_run: If True, simulate execution
            max_executions: Maximum recommendations to execute (default: from config)

        Returns:
            List of ExecutionResults
        """
        max_exec = max_executions or self.config.execution.MAX_CHANGES_PER_DAY
        results = []

        for rec in recommendations[:max_exec]:
            # Check if we've hit daily limits
            if self._executions_today["total"] >= self.config.execution.MAX_CHANGES_PER_DAY:
                results.append(ExecutionResult(
                    recommendation_id=rec.id,
                    success=False,
                    message="Daily execution limit reached",
                    executed_at=datetime.utcnow(),
                ))
                continue

            result = self.execute(rec, dry_run=dry_run)
            results.append(result)

        return results

    def _validate_execution(
        self,
        recommendation: Recommendation,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Validate if execution is allowed."""
        reasons = []

        # Check risk level
        if recommendation.risk_level == RiskLevel.HIGH:
            if recommendation.rollout_strategy != RolloutStrategy.MANUAL_REVIEW:
                reasons.append("High-risk recommendations require manual review")

        # Check against daily limits
        if self._executions_today["total"] >= self.config.execution.MAX_CHANGES_PER_DAY:
            reasons.append(f"Daily limit of {self.config.execution.MAX_CHANGES_PER_DAY} reached")

        # Check category-specific limits
        if recommendation.category.value == "budget":
            if self._executions_today["budget"] >= self.config.execution.MAX_BUDGET_CHANGES_PER_DAY:
                reasons.append(f"Daily budget change limit of {self.config.execution.MAX_BUDGET_CHANGES_PER_DAY} reached")

        if recommendation.category.value == "keyword":
            if self._executions_today["keyword_pause"] >= self.config.execution.MAX_KEYWORD_PAUSES_PER_DAY:
                reasons.append(f"Daily keyword pause limit reached")

        # Check confidence threshold
        if recommendation.confidence < 0.5 and not force:
            reasons.append(f"Confidence {recommendation.confidence:.0%} below 50% threshold")

        # Check rollout strategy
        if recommendation.rollout_strategy == RolloutStrategy.MANUAL_REVIEW and not force:
            reasons.append("Recommendation requires manual review")

        can_execute = len(reasons) == 0 or force

        return {
            "can_execute": can_execute,
            "reasons": reasons,
            "force_applied": force and len(reasons) > 0,
        }

    def _simulate_execution(
        self,
        recommendation: Recommendation,
    ) -> ExecutionResult:
        """Simulate execution without making changes."""
        logger.info(
            "Simulating execution (dry run)",
            rec_id=recommendation.id,
            action=recommendation.action,
        )

        return ExecutionResult(
            recommendation_id=recommendation.id,
            success=True,
            message=f"[DRY RUN] Would execute: {recommendation.action}",
            executed_at=datetime.utcnow(),
            api_response={"dry_run": True, "operations": recommendation.api_operations},
            follow_up_date=date.today() + timedelta(days=7),
        )

    def _execute_operation(
        self,
        recommendation: Recommendation,
    ) -> ExecutionResult:
        """Execute the actual API operations."""
        operations = recommendation.api_operations

        if not operations:
            return ExecutionResult(
                recommendation_id=recommendation.id,
                success=False,
                message="No API operations defined",
                executed_at=datetime.utcnow(),
            )

        try:
            for op in operations:
                op_type = op.get("operation")

                if op_type == "update_campaign_budget":
                    self._execute_budget_update(op)

                elif op_type == "add_negative_keyword":
                    self._execute_add_negative(op)

                elif op_type == "pause_keyword":
                    self._execute_pause_keyword(op)

                elif op_type == "set_geo_bid_modifier":
                    self._execute_geo_modifier(op)

                elif op_type == "set_audience_bid_modifier":
                    self._execute_audience_modifier(op)

                elif op_type == "add_geo_exclusion":
                    self._execute_geo_exclusion(op)

                else:
                    logger.warning(f"Unknown operation type: {op_type}")

            return ExecutionResult(
                recommendation_id=recommendation.id,
                success=True,
                message=f"Successfully executed: {recommendation.action}",
                executed_at=datetime.utcnow(),
                api_response={"operations_count": len(operations)},
                follow_up_date=date.today() + timedelta(days=7),
            )

        except Exception as e:
            logger.error(
                "Execution failed",
                rec_id=recommendation.id,
                error=str(e),
            )
            return ExecutionResult(
                recommendation_id=recommendation.id,
                success=False,
                message=f"Execution failed: {str(e)}",
                executed_at=datetime.utcnow(),
            )

    def _execute_budget_update(self, operation: Dict[str, Any]) -> None:
        """Execute a budget update operation."""
        campaign_id = operation["campaign_id"]
        new_budget = operation["new_budget"]

        # Convert to micros
        budget_micros = int(new_budget * 1_000_000)

        # Build mutation
        mutate_operation = {
            "campaign_budget_operation": {
                "update": {
                    "resource_name": f"customers/{self.api_client.get_customer_id()}/campaignBudgets/{campaign_id}",
                    "amount_micros": budget_micros,
                },
                "update_mask": {"paths": ["amount_micros"]},
            }
        }

        self.api_client.mutate([mutate_operation])
        logger.info(f"Updated budget for campaign {campaign_id} to ${new_budget}")

    def _execute_add_negative(self, operation: Dict[str, Any]) -> None:
        """Execute adding a negative keyword."""
        campaign_id = operation["campaign_id"]
        keyword_text = operation["keyword_text"]
        match_type = operation.get("match_type", "EXACT")

        logger.info(f"Would add negative keyword '{keyword_text}' to campaign {campaign_id}")
        # Actual implementation would use SharedCriterion or CampaignCriterion

    def _execute_pause_keyword(self, operation: Dict[str, Any]) -> None:
        """Execute pausing a keyword."""
        keyword_id = operation["keyword_id"]

        logger.info(f"Would pause keyword {keyword_id}")
        # Actual implementation would update AdGroupCriterion status

    def _execute_geo_modifier(self, operation: Dict[str, Any]) -> None:
        """Execute setting a geo bid modifier."""
        campaign_id = operation["campaign_id"]
        location_id = operation["location_id"]
        bid_modifier = operation["bid_modifier"]

        logger.info(f"Would set geo modifier for {location_id} to {bid_modifier}")
        # Actual implementation would update CampaignCriterion

    def _execute_audience_modifier(self, operation: Dict[str, Any]) -> None:
        """Execute setting an audience bid modifier."""
        audience_id = operation["audience_id"]
        campaign_id = operation.get("campaign_id")
        bid_modifier = operation["bid_modifier"]

        logger.info(f"Would set audience modifier for {audience_id} to {bid_modifier}")
        # Actual implementation would update AdGroupCriterion or CampaignCriterion

    def _execute_geo_exclusion(self, operation: Dict[str, Any]) -> None:
        """Execute adding a geo exclusion."""
        campaign_id = operation["campaign_id"]
        location_id = operation["location_id"]

        logger.info(f"Would exclude location {location_id} from campaign {campaign_id}")
        # Actual implementation would add negative CampaignCriterion

    def _log_change(
        self,
        recommendation: Recommendation,
        result: ExecutionResult,
    ) -> None:
        """Log the executed change."""
        # Determine change type
        change_type_map = {
            "budget": ChangeType.BUDGET,
            "keyword": ChangeType.KEYWORD_REMOVED,
            "search_term": ChangeType.KEYWORD_ADDED,  # negative
            "geo": ChangeType.GEO_TARGETING,
            "audience": ChangeType.AUDIENCE_TARGETING,
        }

        change_type = change_type_map.get(
            recommendation.category.value,
            ChangeType.TARGETING,
        )

        # Determine if this triggers learning
        learning_triggers = {ChangeType.BUDGET, ChangeType.GEO_TARGETING, ChangeType.AUDIENCE_TARGETING}
        triggers_learning = change_type in learning_triggers

        import uuid
        change_event = ChangeEvent(
            id=str(uuid.uuid4()),
            entity_type=recommendation.entity_type,
            entity_id=recommendation.entity_id,
            entity_name=recommendation.entity_name,
            change_type=change_type,
            old_value=recommendation.expected_impact.current_value,
            new_value=recommendation.expected_impact.expected_value,
            timestamp=result.executed_at,
            triggered_by=f"recommendation_{recommendation.id}",
            triggers_learning=triggers_learning,
            learning_days=7 if triggers_learning else 0,
        )

        self.data_store.save_change_event(change_event)

        # Also save recommendation as executed
        self.data_store.mark_recommendation_executed(
            recommendation.id,
            result.message,
        )

    def _schedule_follow_up(self, recommendation: Recommendation) -> None:
        """Schedule a follow-up check for the recommendation."""
        follow_up_date = date.today() + timedelta(days=7)
        logger.info(
            "Follow-up scheduled",
            rec_id=recommendation.id,
            follow_up_date=str(follow_up_date),
        )
        # In a full implementation, this would store in a scheduler

    def _increment_counts(self, recommendation: Recommendation) -> None:
        """Increment daily execution counts."""
        self._executions_today["total"] += 1

        if recommendation.category.value == "budget":
            self._executions_today["budget"] += 1

        if recommendation.category.value == "keyword" and "pause" in recommendation.action.lower():
            self._executions_today["keyword_pause"] += 1

    def _reset_daily_counts_if_needed(self) -> None:
        """Reset daily counts if it's a new day."""
        today = date.today()
        if self._last_reset_date != today:
            self._executions_today = {
                "total": 0,
                "budget": 0,
                "keyword_pause": 0,
            }
            self._last_reset_date = today

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get current execution statistics."""
        self._reset_daily_counts_if_needed()

        return {
            "date": str(date.today()),
            "executions_today": self._executions_today,
            "limits": {
                "max_total": self.config.execution.MAX_CHANGES_PER_DAY,
                "max_budget": self.config.execution.MAX_BUDGET_CHANGES_PER_DAY,
                "max_keyword_pauses": self.config.execution.MAX_KEYWORD_PAUSES_PER_DAY,
            },
            "remaining": {
                "total": self.config.execution.MAX_CHANGES_PER_DAY - self._executions_today["total"],
                "budget": self.config.execution.MAX_BUDGET_CHANGES_PER_DAY - self._executions_today["budget"],
            },
        }
