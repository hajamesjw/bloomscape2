# Google Ads Intelligence System

An automated system for deep Google Ads performance analysis, insight generation, and risk-aware optimization recommendations.

## Philosophy

This system behaves like a **cautious, experienced account manager**, not an aggressive optimizer. Key principles:

1. **Never optimize entities in learning phase** - Wait for stability
2. **Never make decisions on insufficient data** - Respect minimum thresholds
3. **Never change budgets by more than 20% at once** - Gradual scaling only
4. **Never pause keywords with < 100 clicks** - Insufficient signal
5. **Every recommendation has explanation** - No black box decisions

## Installation

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
export GOOGLE_ADS_CUSTOMER_ID="123-456-7890"
export GOOGLE_ADS_DEVELOPER_TOKEN="your-token"
export GOOGLE_ADS_CLIENT_ID="your-client-id"
export GOOGLE_ADS_CLIENT_SECRET="your-client-secret"
export GOOGLE_ADS_REFRESH_TOKEN="your-refresh-token"
```

## Usage

### CLI Commands

```bash
# Run full analysis
gads-intel analyze --days 30

# Quick status check
gads-intel status

# Execute recommendations (dry run)
gads-intel execute --dry-run

# Execute recommendations (real)
gads-intel execute --execute --max 5

# View change history
gads-intel history --days 30

# Check execution limits
gads-intel limits
```

### Python API

```python
from google_ads_intelligence import create_system

# Create system
system = create_system(customer_id="123-456-7890")

# Run full analysis
results = system.run_full_analysis(days=30)

# Print report
system.print_report(results["report"])

# Get recommendations
recommendations = results["recommendations"]
for rec in recommendations.recommendations[:5]:
    print(f"[{rec.risk_level.value}] {rec.action}")
    print(f"  Rationale: {rec.rationale}")
    print(f"  Confidence: {rec.confidence:.0%}")
    print()

# Execute with dry run
execution_results = system.execute_recommendations(
    recommendations=recommendations.recommendations[:3],
    dry_run=True
)
```

## Architecture

```
google_ads_intelligence/
├── core/                 # Core components
│   ├── api_client.py     # Google Ads API wrapper with rate limiting
│   └── data_store.py     # SQLite storage for metrics and changes
├── collectors/           # Data collection modules
│   ├── campaign_collector.py
│   ├── keyword_collector.py
│   ├── search_term_collector.py
│   ├── geo_collector.py
│   ├── audience_collector.py
│   └── ...
├── analyzers/            # Analysis modules
│   ├── learning_detector.py    # Learning phase detection
│   ├── performance_analyzer.py # Trend and anomaly detection
│   ├── budget_analyzer.py      # Budget optimization
│   ├── keyword_analyzer.py     # Keyword health analysis
│   └── ...
├── executors/            # Execution layer
│   ├── recommendation_engine.py  # Central recommendation aggregation
│   └── safe_executor.py          # Safe execution with safeguards
├── reports/              # Report generation
│   └── report_generator.py
├── models/               # Data models
├── utils/                # Utilities
├── config.py             # Configuration
├── main.py               # Main orchestration
└── cli.py                # Command-line interface
```

## Analysis Coverage

### Core Analysis
- Campaign performance trends
- Keyword health and quality score
- Search term mining (negatives & promotions)
- Budget utilization and allocation
- Geographic performance
- Audience segment performance
- Ad schedule / dayparting
- Creative fatigue detection
- Account structure evaluation

### Safety Features
- Learning phase detection
- Minimum data thresholds
- Budget change limits (max 20%)
- Daily execution limits
- Full audit trail
- Dry run mode

## Report Output

### JSON Format
```json
{
  "report_date": "2024-01-15",
  "account_health": {
    "overall_score": 78,
    "trend": "stable"
  },
  "key_metrics_summary": {
    "spend_7d": 6850.00,
    "conversions_7d": 145,
    "cpa_7d": 47.24,
    "roas_7d": 3.2
  },
  "recommendations": [...]
}
```

### Human-Readable Format
```
============================================================
    GOOGLE ADS DAILY INTELLIGENCE REPORT
============================================================
Date: 2024-01-15
Account Health: 78/100 (stable)

7-DAY PERFORMANCE
----------------------------------------
   Spend:           $6,850.00
   Conversions:     145.0
   CPA:             $47.24
   ROAS:            3.20x

TOP RECOMMENDATIONS
----------------------------------------
   1. [LOW RISK] Increase budget for 'Non-Brand - High Intent'
      Expected: +12.0% conversions
      Confidence: 85%
      Why: Campaign is losing 25% impression share to budget...
```

## Configuration Options

```python
from google_ads_intelligence.config import Config

config = Config()

# Analysis thresholds
config.analysis.MIN_DATA_THRESHOLDS = {
    "campaign": {"clicks": 100, "conversions": 10, "days": 14},
    "keyword": {"clicks": 30, "conversions": 3, "days": 21},
}

# Budget limits
config.budget.MAX_INCREASE_PCT = 20.0
config.budget.MAX_DECREASE_PCT = 15.0
config.budget.MIN_DAYS_BETWEEN_CHANGES = 7

# Execution limits
config.execution.MAX_CHANGES_PER_DAY = 10
config.execution.MAX_BUDGET_CHANGES_PER_DAY = 3
config.execution.DRY_RUN_DEFAULT = True
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check .

# Type checking
mypy google_ads_intelligence
```

## License

MIT
