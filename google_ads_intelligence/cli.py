"""Command-line interface for Google Ads Intelligence System."""

import click
from pathlib import Path
from datetime import date

from .main import GoogleAdsIntelligence, create_system
from .config import Config
from .utils.logging import setup_logging


@click.group()
@click.option("--customer-id", envvar="GOOGLE_ADS_CUSTOMER_ID", help="Google Ads customer ID")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.pass_context
def cli(ctx, customer_id, debug):
    """Google Ads Intelligence System - Automated analysis and optimization."""
    setup_logging("DEBUG" if debug else "INFO")

    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj["customer_id"] = customer_id


@cli.command()
@click.option("--days", default=30, help="Number of days to analyze")
@click.option("--full/--quick", default=True, help="Full analysis vs quick check")
@click.option("--output", type=click.Path(), help="Output directory for reports")
@click.pass_context
def analyze(ctx, days, full, output):
    """Run analysis and generate recommendations."""
    click.echo(f"Starting {'full' if full else 'quick'} analysis for {days} days...")

    system = create_system(customer_id=ctx.obj.get("customer_id"))

    if full:
        results = system.run_full_analysis(days=days)
    else:
        results = system.run_quick_check()

    # Print report
    system.print_report(results["report"])

    # Save if output specified
    if output:
        paths = system.save_report(results["report"], Path(output))
        click.echo(f"\nReports saved to:")
        click.echo(f"  JSON: {paths['json']}")
        click.echo(f"  Text: {paths['text']}")

    # Summary
    rec_count = len(results["recommendations"].recommendations)
    click.echo(f"\n{rec_count} recommendations generated.")


@cli.command()
@click.option("--days", default=30, help="Number of days to analyze")
@click.option("--dry-run/--execute", default=True, help="Dry run or execute")
@click.option("--max", "max_exec", default=5, help="Maximum recommendations to execute")
@click.pass_context
def execute(ctx, days, dry_run, max_exec):
    """Execute recommendations (use with caution)."""
    system = create_system(customer_id=ctx.obj.get("customer_id"))

    # Run analysis to get recommendations
    click.echo("Running analysis...")
    results = system.run_full_analysis(days=days)

    recommendations = results["recommendations"].recommendations

    if not recommendations:
        click.echo("No recommendations to execute.")
        return

    # Filter to low-risk only for auto-execution
    from .models.recommendations import RiskLevel

    low_risk = [r for r in recommendations if r.risk_level == RiskLevel.LOW]

    if not low_risk:
        click.echo("No low-risk recommendations available for auto-execution.")
        click.echo(f"Total recommendations: {len(recommendations)}")
        click.echo("Run with --manual to review and approve higher-risk recommendations.")
        return

    click.echo(f"\n{len(low_risk)} low-risk recommendations available.")

    if dry_run:
        click.echo("\n[DRY RUN MODE - No changes will be made]")

    # Confirm execution
    if not dry_run:
        if not click.confirm(f"Execute up to {max_exec} recommendations?"):
            click.echo("Aborted.")
            return

    # Execute
    execution_results = system.execute_recommendations(
        recommendations=low_risk[:max_exec],
        dry_run=dry_run,
    )

    # Show results
    click.echo("\nExecution Results:")
    for result in execution_results:
        status = "SUCCESS" if result.success else "FAILED"
        click.echo(f"  [{status}] {result.message}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show current account status and health."""
    system = create_system(customer_id=ctx.obj.get("customer_id"))

    click.echo("Fetching account status...")

    # Quick analysis
    results = system.run_quick_check()

    report = results["report"]
    metrics = report["key_metrics_summary"]
    health = report["account_health"]

    click.echo("\n" + "=" * 50)
    click.echo("        ACCOUNT STATUS")
    click.echo("=" * 50)
    click.echo(f"Health Score: {health['overall_score']}/100 ({health['trend']})")
    click.echo("")
    click.echo("7-Day Performance:")
    click.echo(f"  Spend:        ${metrics['spend_7d']:,.2f}")
    click.echo(f"  Conversions:  {metrics['conversions_7d']:,.1f}")
    click.echo(f"  CPA:          ${metrics['cpa_7d']:,.2f}")
    click.echo(f"  ROAS:         {metrics['roas_7d']:.2f}x")

    # Learning status
    learning = report["learning_status"]
    if learning["count"] > 0:
        click.echo(f"\nCampaigns in Learning: {learning['count']}")
        for camp in learning["campaigns_in_learning"]:
            click.echo(f"  - {camp['name']} ({camp['days_remaining']} days remaining)")

    # Alerts
    alerts = health["alerts"]
    if alerts:
        click.echo("\nAlerts:")
        for alert in alerts:
            click.echo(f"  [{alert['severity'].upper()}] {alert['message']}")

    click.echo("")


@cli.command()
@click.option("--days", default=30, help="Days of history to review")
@click.pass_context
def history(ctx, days):
    """Show recent changes and their outcomes."""
    system = create_system(customer_id=ctx.obj.get("customer_id"))

    click.echo(f"Fetching change history for last {days} days...")

    from datetime import timedelta
    from .utils.dates import days_ago

    start_date = days_ago(days)
    end_date = date.today()

    changes = system.change_collector.collect(start_date, end_date)

    if not changes:
        click.echo("No changes found in the specified period.")
        return

    click.echo(f"\n{len(changes)} changes found:\n")

    for change in changes[:20]:
        click.echo(f"  {change.timestamp.strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"    Type: {change.change_type.value}")
        click.echo(f"    Entity: {change.entity_name or change.entity_id}")
        click.echo(f"    Triggered by: {change.triggered_by}")
        if change.triggers_learning:
            click.echo(f"    Learning period: {change.learning_days} days")
        click.echo("")


@cli.command()
@click.pass_context
def limits(ctx):
    """Show execution limits and current usage."""
    system = create_system(customer_id=ctx.obj.get("customer_id"))

    stats = system.safe_executor.get_execution_stats()

    click.echo("\n" + "=" * 40)
    click.echo("      EXECUTION LIMITS")
    click.echo("=" * 40)
    click.echo(f"Date: {stats['date']}")
    click.echo("")
    click.echo("Daily Limits:")
    click.echo(f"  Total changes:    {stats['limits']['max_total']}")
    click.echo(f"  Budget changes:   {stats['limits']['max_budget']}")
    click.echo(f"  Keyword pauses:   {stats['limits']['max_keyword_pauses']}")
    click.echo("")
    click.echo("Today's Usage:")
    click.echo(f"  Total:            {stats['executions_today']['total']}")
    click.echo(f"  Budget:           {stats['executions_today']['budget']}")
    click.echo(f"  Keyword pauses:   {stats['executions_today']['keyword_pause']}")
    click.echo("")
    click.echo("Remaining:")
    click.echo(f"  Total:            {stats['remaining']['total']}")
    click.echo(f"  Budget:           {stats['remaining']['budget']}")
    click.echo("")


def main():
    """Entry point for CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
