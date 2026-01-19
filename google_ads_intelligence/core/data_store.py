"""Data storage layer for persisting metrics and analysis results."""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pathlib import Path
import json

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Date, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from ..config import Config, DEFAULT_CONFIG
from ..utils.logging import get_logger
from ..models import ChangeEvent, ChangeType

logger = get_logger(__name__)

Base = declarative_base()


class CampaignMetricsRecord(Base):
    """Campaign metrics storage."""

    __tablename__ = "campaign_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(50), index=True)
    campaign_name = Column(String(255))
    date = Column(Date, index=True)

    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Float, default=0.0)
    conversion_value = Column(Float, default=0.0)

    ctr = Column(Float, default=0.0)
    cpc = Column(Float, default=0.0)
    cpa = Column(Float)
    roas = Column(Float)

    impression_share = Column(Float)
    impression_share_lost_budget = Column(Float)
    impression_share_lost_rank = Column(Float)

    budget_amount = Column(Float)
    bid_strategy_type = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow)


class KeywordMetricsRecord(Base):
    """Keyword metrics storage."""

    __tablename__ = "keyword_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(String(50), index=True)
    keyword_text = Column(String(255))
    match_type = Column(String(20))
    ad_group_id = Column(String(50), index=True)
    campaign_id = Column(String(50), index=True)
    date = Column(Date, index=True)

    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Float, default=0.0)
    conversion_value = Column(Float, default=0.0)

    quality_score = Column(Integer)
    expected_ctr = Column(String(20))
    ad_relevance = Column(String(20))
    landing_page_experience = Column(String(20))

    created_at = Column(DateTime, default=datetime.utcnow)


class SearchTermRecord(Base):
    """Search term report storage."""

    __tablename__ = "search_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(500), index=True)
    keyword_id = Column(String(50))
    keyword_text = Column(String(255))
    ad_group_id = Column(String(50))
    campaign_id = Column(String(50), index=True)
    date = Column(Date, index=True)

    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Float, default=0.0)
    conversion_value = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class GeoMetricsRecord(Base):
    """Geographic performance storage."""

    __tablename__ = "geo_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(String(50), index=True)
    location_name = Column(String(255))
    location_type = Column(String(50))
    campaign_id = Column(String(50), index=True)
    date = Column(Date, index=True)

    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Float, default=0.0)
    conversion_value = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class AudienceMetricsRecord(Base):
    """Audience performance storage."""

    __tablename__ = "audience_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audience_id = Column(String(50), index=True)
    audience_name = Column(String(255))
    audience_type = Column(String(50))
    campaign_id = Column(String(50), index=True)
    ad_group_id = Column(String(50))
    date = Column(Date, index=True)

    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Float, default=0.0)
    conversion_value = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class ChangeLogRecord(Base):
    """Change history storage."""

    __tablename__ = "change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    change_id = Column(String(50), unique=True, index=True)
    entity_type = Column(String(50), index=True)
    entity_id = Column(String(50), index=True)
    entity_name = Column(String(255))
    change_type = Column(String(50))
    old_value = Column(Text)
    new_value = Column(Text)
    timestamp = Column(DateTime, index=True)
    triggered_by = Column(String(100))
    triggers_learning = Column(Boolean, default=False)
    learning_days = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)


class RecommendationRecord(Base):
    """Recommendation history storage."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(String(50), unique=True, index=True)
    category = Column(String(50))
    action = Column(Text)
    entity_type = Column(String(50))
    entity_id = Column(String(50))
    entity_name = Column(String(255))

    confidence = Column(Float)
    risk_level = Column(String(20))
    expected_impact_json = Column(Text)
    rationale = Column(Text)

    created_at = Column(DateTime, index=True)
    executed = Column(Boolean, default=False)
    executed_at = Column(DateTime)
    execution_result = Column(Text)

    # Outcome tracking
    follow_up_date = Column(Date)
    outcome_measured = Column(Boolean, default=False)
    actual_impact_json = Column(Text)


class DataStore:
    """
    Data persistence layer.

    Handles storage and retrieval of:
    - Historical metrics
    - Change events
    - Recommendations and outcomes
    """

    def __init__(self, config: Optional[Config] = None, db_path: Optional[str] = None):
        self.config = config or DEFAULT_CONFIG

        if db_path:
            self.db_url = f"sqlite:///{db_path}"
        else:
            data_dir = self.config.data_dir
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_url = f"sqlite:///{data_dir}/google_ads_intelligence.db"

        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info("DataStore initialized", db_url=self.db_url)

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    # Campaign metrics
    def save_campaign_metrics(self, metrics: List[Dict[str, Any]]) -> int:
        """Save campaign metrics records."""
        session = self.get_session()
        try:
            for m in metrics:
                record = CampaignMetricsRecord(**m)
                session.add(record)
            session.commit()
            logger.info("Saved campaign metrics", count=len(metrics))
            return len(metrics)
        finally:
            session.close()

    def get_campaign_metrics(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Get campaign metrics for a date range."""
        session = self.get_session()
        try:
            records = (
                session.query(CampaignMetricsRecord)
                .filter(
                    CampaignMetricsRecord.campaign_id == campaign_id,
                    CampaignMetricsRecord.date >= start_date,
                    CampaignMetricsRecord.date <= end_date,
                )
                .order_by(CampaignMetricsRecord.date)
                .all()
            )
            return [self._record_to_dict(r) for r in records]
        finally:
            session.close()

    # Change log
    def save_change_event(self, event: ChangeEvent) -> None:
        """Save a change event."""
        session = self.get_session()
        try:
            record = ChangeLogRecord(
                change_id=event.id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                entity_name=event.entity_name,
                change_type=event.change_type.value,
                old_value=str(event.old_value),
                new_value=str(event.new_value),
                timestamp=event.timestamp,
                triggered_by=event.triggered_by,
                triggers_learning=event.triggers_learning,
                learning_days=event.learning_days,
            )
            session.add(record)
            session.commit()
            logger.info("Saved change event", change_id=event.id)
        finally:
            session.close()

    def get_recent_changes(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get recent changes for an entity."""
        session = self.get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            records = (
                session.query(ChangeLogRecord)
                .filter(
                    ChangeLogRecord.entity_type == entity_type,
                    ChangeLogRecord.entity_id == entity_id,
                    ChangeLogRecord.timestamp >= cutoff,
                )
                .order_by(ChangeLogRecord.timestamp.desc())
                .all()
            )
            return [self._record_to_dict(r) for r in records]
        finally:
            session.close()

    def get_last_change(
        self,
        entity_type: str,
        entity_id: str,
        change_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent change for an entity."""
        session = self.get_session()
        try:
            query = session.query(ChangeLogRecord).filter(
                ChangeLogRecord.entity_type == entity_type,
                ChangeLogRecord.entity_id == entity_id,
            )
            if change_type:
                query = query.filter(ChangeLogRecord.change_type == change_type)

            record = query.order_by(ChangeLogRecord.timestamp.desc()).first()
            return self._record_to_dict(record) if record else None
        finally:
            session.close()

    # Recommendations
    def save_recommendation(self, recommendation: Dict[str, Any]) -> None:
        """Save a recommendation."""
        session = self.get_session()
        try:
            record = RecommendationRecord(
                recommendation_id=recommendation["id"],
                category=recommendation["category"],
                action=recommendation["action"],
                entity_type=recommendation["entity"]["type"],
                entity_id=recommendation["entity"]["id"],
                entity_name=recommendation["entity"]["name"],
                confidence=recommendation["confidence"],
                risk_level=recommendation["risk_level"],
                expected_impact_json=json.dumps(recommendation.get("expected_impact")),
                rationale=recommendation["rationale"],
                created_at=datetime.utcnow(),
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def mark_recommendation_executed(
        self,
        recommendation_id: str,
        result: str,
    ) -> None:
        """Mark a recommendation as executed."""
        session = self.get_session()
        try:
            record = (
                session.query(RecommendationRecord)
                .filter(RecommendationRecord.recommendation_id == recommendation_id)
                .first()
            )
            if record:
                record.executed = True
                record.executed_at = datetime.utcnow()
                record.execution_result = result
                session.commit()
        finally:
            session.close()

    def _record_to_dict(self, record) -> Dict[str, Any]:
        """Convert a SQLAlchemy record to dictionary."""
        if record is None:
            return {}
        return {
            c.name: getattr(record, c.name)
            for c in record.__table__.columns
        }


# Import timedelta at module level
from datetime import timedelta
