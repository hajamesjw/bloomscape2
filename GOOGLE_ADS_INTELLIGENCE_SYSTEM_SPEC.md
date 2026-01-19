# Google Ads Intelligence System — Technical Specification

## Role Context

You are implementing an automated Google Ads intelligence system. Assume the expertise of:
- A **senior data engineer** with production ML pipeline experience
- A **senior Google Ads specialist** with 10+ years managing high-spend accounts
- A **risk-aware systems architect** who prioritizes stability over short-term gains

---

## System Overview

### Account Context
- **Daily spend**: ~$1,000/day ($30K/month)
- **API access**: Full read/write via Google Ads API (v17+)
- **Risk tolerance**: Conservative — this is real money, not a sandbox

### Core Philosophy
This system must behave like a **cautious, experienced account manager**, not an aggressive optimizer. The Google Ads algorithm needs time and data stability to learn. Our job is to:

1. **Observe** patterns across meaningful time horizons
2. **Understand** why metrics move (not just that they moved)
3. **Recommend** changes with clear rationale and risk assessment
4. **Protect** campaigns from thrashing that resets learning

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                         │
│              (Scheduler: hourly data pull, daily analysis)      │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  DATA LAYER   │      │ ANALYSIS LAYER│      │ ACTION LAYER  │
│               │      │               │      │               │
│ • API Client  │ ──▶  │ • Analyzers   │ ──▶  │ • Recommender │
│ • Data Store  │      │ • Detectors   │      │ • Executor    │
│ • Cache       │      │ • Scorers     │      │ • Safeguards  │
└───────────────┘      └───────────────┘      └───────────────┘
                                │
                                ▼
                    ┌───────────────────┐
                    │   OUTPUT LAYER    │
                    │                   │
                    │ • Reports (JSON)  │
                    │ • Alerts          │
                    │ • Audit Log       │
                    └───────────────────┘
```

### Data Storage Schema

```python
# Core entities to track with historical snapshots
ENTITIES = {
    "campaigns": ["id", "name", "status", "budget", "bid_strategy", "start_date"],
    "ad_groups": ["id", "campaign_id", "name", "status", "cpc_bid"],
    "keywords": ["id", "ad_group_id", "text", "match_type", "status", "quality_score"],
    "ads": ["id", "ad_group_id", "type", "headlines", "descriptions", "status"],
    "search_terms": ["query", "keyword_id", "impressions", "clicks", "conversions", "cost"],
    "geo_performance": ["location_id", "location_name", "level", "metrics"],
}

# Metrics to capture at each level (daily granularity minimum)
METRICS = [
    "impressions", "clicks", "cost", "conversions", "conversion_value",
    "ctr", "cpc", "conversion_rate", "cpa", "roas",
    "impression_share", "impression_share_lost_budget", "impression_share_lost_rank",
    "quality_score", "expected_ctr", "ad_relevance", "landing_page_exp",
    "avg_position", "search_impression_share"
]

# Change log for detecting learning resets
CHANGE_LOG = {
    "entity_type": str,
    "entity_id": str,
    "change_type": str,  # "budget", "bid_strategy", "creative", "targeting", "status"
    "old_value": any,
    "new_value": any,
    "timestamp": datetime,
    "triggered_by": str,  # "manual", "system", "auto_recommendation"
}
```

### API Rate Limit Handling
- Google Ads API: ~15,000 operations/day for standard access
- Implement exponential backoff: 1s, 2s, 4s, 8s, max 60s
- Batch requests where possible (max 10,000 operations per mutate)
- Cache aggressively — most analysis doesn't need real-time data

---

## Analysis Modules (Implement in Priority Order)

### Phase 1: Foundation (Week 1-2)

#### 1.1 Data Collection Pipeline

```python
class DataCollector:
    """
    Pull and store data at multiple time granularities.
    Run: Every 6 hours for metrics, daily for structure changes.
    """

    TIME_WINDOWS = [1, 3, 7, 14, 30, 60, 90]  # days

    def collect_campaign_metrics(self, date_range: tuple) -> DataFrame
    def collect_keyword_metrics(self, date_range: tuple) -> DataFrame
    def collect_search_terms(self, date_range: tuple) -> DataFrame
    def collect_geo_metrics(self, date_range: tuple) -> DataFrame
    def collect_ad_metrics(self, date_range: tuple) -> DataFrame
    def detect_structure_changes(self) -> List[ChangeEvent]
```

#### 1.2 Learning Phase Detector

```python
class LearningPhaseDetector:
    """
    Identify entities currently in learning or recently disrupted.
    Critical: Never optimize entities in learning phase.
    """

    # Events that trigger learning reset
    LEARNING_TRIGGERS = {
        "budget_change": {"threshold_pct": 20, "learning_days": 7},
        "bid_strategy_change": {"threshold_pct": 0, "learning_days": 14},
        "creative_change": {"threshold_pct": 0, "learning_days": 7},
        "targeting_change": {"threshold_pct": 0, "learning_days": 7},
        "conversion_action_change": {"threshold_pct": 0, "learning_days": 14},
    }

    # Minimum data requirements before analysis is valid
    MIN_DATA_THRESHOLDS = {
        "campaign": {"clicks": 100, "conversions": 10, "days": 14},
        "ad_group": {"clicks": 50, "conversions": 5, "days": 14},
        "keyword": {"clicks": 30, "conversions": 3, "days": 21},
        "ad": {"impressions": 1000, "clicks": 50, "days": 14},
    }

    def is_in_learning(self, entity_type: str, entity_id: str) -> LearningStatus
    def days_since_last_change(self, entity_type: str, entity_id: str) -> int
    def has_sufficient_data(self, entity_type: str, entity_id: str) -> DataSufficiency
```

### Phase 2: Core Analysis (Week 3-4)

#### 2.1 Time-Aware Performance Analyzer

```python
class PerformanceAnalyzer:
    """
    Analyze trends across multiple time windows to distinguish:
    - Normal volatility vs structural problems
    - Temporary dips vs sustained decline
    - Seasonal patterns vs real degradation
    """

    def analyze_trend(self, entity_id: str, metric: str) -> TrendAnalysis:
        """
        Returns:
        - direction: "improving" | "declining" | "stable" | "volatile"
        - confidence: 0.0-1.0
        - pattern: "seasonal" | "day_of_week" | "random" | "structural"
        - recommendation: "wait" | "investigate" | "act"
        """

    def detect_anomalies(self, entity_id: str) -> List[Anomaly]:
        """
        Flag statistically significant deviations (>2 std dev).
        Distinguish one-off spikes from trend changes.
        """

    def calculate_statistical_significance(
        self,
        metric_before: Series,
        metric_after: Series
    ) -> SignificanceResult:
        """
        Use appropriate test based on data distribution.
        Require p < 0.05 AND practical significance (>10% change).
        """
```

#### 2.2 Budget Intelligence Module

```python
class BudgetAnalyzer:
    """
    Optimize budget allocation while respecting learning constraints.
    """

    # Hard limits on budget changes
    CHANGE_LIMITS = {
        "max_increase_pct": 20,      # Never increase >20% at once
        "max_decrease_pct": 15,      # Never decrease >15% at once
        "min_days_between_changes": 7,
        "min_budget_floor": 10.00,   # Never go below $10/day
    }

    def analyze_utilization(self, campaign_id: str) -> BudgetUtilization:
        """
        Returns:
        - avg_daily_spend vs budget
        - impression_share_lost_to_budget (7d, 30d)
        - estimated_incremental_conversions_if_uncapped
        """

    def detect_diminishing_returns(self, campaign_id: str) -> DiminishingReturnsAnalysis:
        """
        Model the spend-to-conversion curve.
        Identify the point where marginal CPA starts increasing.
        """

    def recommend_reallocation(self) -> List[BudgetRecommendation]:
        """
        Suggest moving budget from low-efficiency to high-efficiency campaigns.
        Include expected impact and confidence interval.
        """
```

#### 2.3 Geographic Performance Module

```python
class GeoAnalyzer:
    """
    Analyze performance by location with appropriate granularity.
    """

    # Minimum thresholds for geo-level decisions
    GEO_MIN_DATA = {
        "country": {"cost": 100, "clicks": 50},
        "region": {"cost": 50, "clicks": 30},
        "city": {"cost": 30, "clicks": 20},
    }

    def analyze_geo_performance(self, campaign_id: str) -> GeoAnalysis:
        """
        Returns performance by location hierarchy.
        Flags locations with statistically significant deviation from average.
        """

    def recommend_geo_actions(self, campaign_id: str) -> List[GeoRecommendation]:
        """
        Recommendations:
        - Exclusions (only for clearly negative ROI with sufficient data)
        - Bid modifiers (conservative: -20% to +30% range)
        - Campaign splits (only if data volume justifies)
        """
```

### Phase 3: Advanced Analysis (Week 5-6)

#### 3.1 Keyword & Search Term Intelligence

```python
class KeywordAnalyzer:
    """
    Deep keyword analysis with protection against premature decisions.
    """

    def analyze_keyword_health(self, keyword_id: str) -> KeywordHealth:
        """
        Factors:
        - Quality score trend (not just current value)
        - Conversion rate vs campaign average
        - Cost efficiency trend
        - Search term quality feeding this keyword
        """

    def mine_search_terms(self, days: int = 30) -> SearchTermAnalysis:
        """
        Identify:
        - High-converting terms not yet as exact keywords
        - Negative keyword candidates (high spend, zero/low conversions)
        - Match type optimization opportunities

        Thresholds for negative keyword recommendation:
        - Minimum spend: $50
        - Minimum clicks: 20
        - Conversions: 0 (or CPA > 3x target)
        """

    def recommend_keyword_actions(self) -> List[KeywordRecommendation]:
        """
        Actions: pause, bid_adjust, match_type_change, promote_to_exact

        NEVER recommend pausing keywords with:
        - < 100 clicks
        - < 30 days of data
        - Recent quality score improvement trend
        """
```

#### 3.2 Creative Analysis Module

```python
class CreativeAnalyzer:
    """
    Analyze ad performance without triggering excessive refreshes.
    """

    # RSA asset performance thresholds
    ASSET_THRESHOLDS = {
        "min_impressions_for_judgment": 5000,
        "fatigue_detection_window_days": 30,
        "ctr_decline_threshold_pct": 20,
    }

    def analyze_rsa_assets(self, ad_id: str) -> RSAAnalysis:
        """
        Google's asset ratings: "Best", "Good", "Low"
        Combine with actual CTR/conversion data.
        Identify winning/losing combinations.
        """

    def detect_creative_fatigue(self, ad_group_id: str) -> FatigueAnalysis:
        """
        Signs of fatigue:
        - CTR declining over 3+ weeks despite stable impression share
        - Frequency increasing (if available)
        - Same audience, declining engagement
        """

    def recommend_creative_actions(self) -> List[CreativeRecommendation]:
        """
        Recommendations:
        - New headline themes to test
        - Underperforming assets to replace
        - Optimal asset count guidance

        NEVER recommend changes to ads with < 14 days performance data.
        """
```

#### 3.3 Campaign Structure Evaluator

```python
class StructureAnalyzer:
    """
    Evaluate account architecture health.
    """

    def detect_cannibalization(self) -> List[CannibalizationIssue]:
        """
        Find campaigns/ad groups competing for same queries.
        Use search term overlap analysis.
        """

    def analyze_segmentation(self) -> SegmentationAnalysis:
        """
        Detect:
        - Over-segmentation: too many campaigns with insufficient data each
        - Under-segmentation: mixed intent in single ad groups

        Healthy thresholds:
        - Campaign should have > 30 conversions/month
        - Ad group should have > 10 conversions/month
        """

    def recommend_restructure(self) -> List[StructureRecommendation]:
        """
        High-impact, low-frequency recommendations only.
        Restructuring is disruptive — only recommend when clearly beneficial.
        """
```

### Phase 4: Recommendation Engine (Week 7-8)

#### 4.1 Risk-Aware Recommendation System

```python
class RecommendationEngine:
    """
    Central engine that produces actionable, risk-assessed recommendations.
    """

    @dataclass
    class Recommendation:
        id: str
        category: str  # "budget", "keyword", "geo", "creative", "structure"
        action: str    # Specific action to take
        entity_type: str
        entity_id: str

        # Risk assessment (REQUIRED for all recommendations)
        confidence: float        # 0.0-1.0, based on data sufficiency
        risk_level: str          # "low", "medium", "high"
        expected_impact: dict    # {"metric": "conversions", "change_pct": 15, "confidence_interval": [10, 20]}
        downside_scenario: str   # What could go wrong

        # Implementation guidance
        rollout_strategy: str    # "immediate", "gradual", "test_first"
        rollback_trigger: str    # Condition that should trigger rollback

        # Explanation (REQUIRED - no black box recommendations)
        rationale: str           # Why this recommendation
        evidence: List[dict]     # Data points supporting this
        assumptions: List[str]   # What we're assuming is true

    def generate_recommendations(self) -> List[Recommendation]:
        """
        Aggregate insights from all analyzers.
        Filter by confidence and data sufficiency.
        Prioritize by expected impact / risk ratio.
        """

    def validate_recommendation(self, rec: Recommendation) -> ValidationResult:
        """
        Pre-execution checks:
        - Entity not in learning phase
        - Sufficient data for decision
        - No conflicting recent changes
        - Within safe change limits
        """
```

#### 4.2 Safe Execution Layer

```python
class SafeExecutor:
    """
    Execute recommendations with safeguards.
    """

    # Global execution limits
    EXECUTION_LIMITS = {
        "max_changes_per_day": 10,
        "max_budget_changes_per_day": 3,
        "max_keyword_pauses_per_day": 5,
        "require_approval_above_risk": "medium",  # Auto-execute only "low" risk
    }

    def execute_with_safeguards(
        self,
        recommendation: Recommendation,
        dry_run: bool = True
    ) -> ExecutionResult:
        """
        Steps:
        1. Validate recommendation is still valid
        2. Check against daily limits
        3. Log intended change
        4. Execute (or simulate if dry_run)
        5. Schedule follow-up check
        """

    def schedule_impact_check(
        self,
        recommendation: Recommendation,
        check_after_days: int = 7
    ) -> None:
        """
        Automated follow-up to measure actual vs expected impact.
        Feed back into recommendation accuracy tracking.
        """
```

---

## Output Specifications

### 1. Daily Insight Report (JSON)

```json
{
  "report_date": "2024-01-15",
  "account_health": {
    "overall_score": 78,
    "trend": "stable",
    "alerts": []
  },
  "key_metrics_summary": {
    "spend_7d": 6850.00,
    "conversions_7d": 145,
    "cpa_7d": 47.24,
    "roas_7d": 3.2,
    "vs_prior_period": {
      "spend_change_pct": 5.2,
      "conversions_change_pct": 12.1,
      "cpa_change_pct": -6.1
    }
  },
  "learning_status": {
    "campaigns_in_learning": ["campaign_123"],
    "reason": "budget_change",
    "estimated_completion": "2024-01-20"
  },
  "observations": [
    {
      "type": "trend",
      "severity": "info",
      "message": "Campaign 'Brand' CTR improved 15% over 14 days",
      "entity": {"type": "campaign", "id": "123", "name": "Brand"}
    }
  ],
  "recommendations": [
    {
      "id": "rec_001",
      "priority": 1,
      "action": "Increase budget for 'Non-Brand - High Intent' from $150 to $175",
      "rationale": "Campaign is losing 25% impression share to budget with strong 2.1 CPA",
      "confidence": 0.85,
      "risk_level": "low",
      "expected_impact": "+8 conversions/week at similar CPA",
      "rollout": "immediate"
    }
  ]
}
```

### 2. Human-Readable Summary

```
=== GOOGLE ADS DAILY INTELLIGENCE REPORT ===
Date: January 15, 2024
Account Health: 78/100 (Stable)

📊 7-DAY PERFORMANCE
   Spend: $6,850 (+5.2%)
   Conversions: 145 (+12.1%)
   CPA: $47.24 (-6.1% ✓)
   ROAS: 3.2x

⚠️ LEARNING STATUS
   • Campaign "Winter Sale" in learning (budget change 3 days ago)
     → No optimization actions until Jan 20

💡 TOP RECOMMENDATIONS

   1. [LOW RISK] Increase "Non-Brand - High Intent" budget
      Current: $150/day → Proposed: $175/day (+16.7%)
      Why: Losing 25% impression share to budget, CPA is 30% below target
      Expected: +8 conversions/week

   2. [MEDIUM RISK] Add negative keywords to "Broad Match" campaign
      Terms: "free", "cheap template", "DIY"
      Why: $234 spent, 0 conversions over 30 days
      Expected: Save ~$200/month, reallocate to converting terms

   3. [OBSERVATION] Monitor "Display Retargeting"
      CPA increased 40% over 14 days
      Recommendation: Wait 7 more days before action (may be seasonal)

=== END REPORT ===
```

### 3. Audit Log Format

```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "action_type": "budget_change",
  "entity": {"type": "campaign", "id": "456", "name": "Non-Brand"},
  "change": {"field": "daily_budget", "old": 150.00, "new": 175.00},
  "triggered_by": "recommendation_rec_001",
  "approval": "auto",
  "expected_impact": {"metric": "conversions", "change": "+8/week"},
  "follow_up_scheduled": "2024-01-22"
}
```

---

## Critical Rules (Non-Negotiable)

### Never Do
1. **Never optimize entities in learning phase** — wait for stability
2. **Never make decisions on insufficient data** — respect minimum thresholds
3. **Never change budgets by more than 20% at once** — gradual scaling only
4. **Never pause keywords with < 100 clicks** — insufficient signal
5. **Never make multiple changes to same entity within 7 days** — allow measurement
6. **Never trust single-day performance** — always use 7+ day windows for decisions
7. **Never ignore seasonality** — compare to same period last year when available
8. **Never recommend without explanation** — every action needs clear rationale

### Always Do
1. **Always log every change** — full audit trail
2. **Always calculate confidence intervals** — not just point estimates
3. **Always consider the downside** — what if we're wrong?
4. **Always schedule follow-up checks** — measure actual vs expected
5. **Always respect API rate limits** — implement proper backoff
6. **Always validate data freshness** — don't act on stale data
7. **Always provide rollback path** — how to undo if needed

---

## Testing & Validation

### Backtesting Requirements
Before deploying any recommendation logic:
1. Backtest on 90 days of historical data
2. Measure: Would recommendations have been profitable?
3. Measure: False positive rate (bad recommendations)
4. Measure: Timing accuracy (did we act at right time?)

### Monitoring Metrics
Track ongoing system health:
- Recommendation acceptance rate
- Recommendation accuracy (expected vs actual impact)
- False positive rate (recommendations that hurt performance)
- Coverage (% of account analyzed)
- Data freshness (lag between reality and analysis)

---

## Implementation Checklist

- [ ] **Phase 1**: Data pipeline operational, pulling all required metrics
- [ ] **Phase 1**: Learning phase detection working, tested against known events
- [ ] **Phase 2**: Performance analyzer detecting real trends vs noise
- [ ] **Phase 2**: Budget analyzer identifying reallocation opportunities
- [ ] **Phase 2**: Geo analyzer flagging underperforming locations
- [ ] **Phase 3**: Keyword analyzer with search term mining
- [ ] **Phase 3**: Creative analyzer detecting fatigue patterns
- [ ] **Phase 3**: Structure analyzer finding cannibalization
- [ ] **Phase 4**: Recommendation engine aggregating all insights
- [ ] **Phase 4**: Safe executor with all safeguards
- [ ] **Phase 4**: Reporting pipeline (JSON + human-readable)
- [ ] **Testing**: Backtesting framework operational
- [ ] **Testing**: All analyzers validated against historical data

---

## Final Note

Build this system as if every dollar spent is your own money. The goal is not to impress with complex optimizations — it's to make reliable, explainable decisions that compound over time. A conservative system that's right 90% of the time beats an aggressive system that's right 70% of the time.

When in doubt, **wait and observe**. Google's algorithms are sophisticated. Often the best action is no action — just ensuring we're not getting in the way.
