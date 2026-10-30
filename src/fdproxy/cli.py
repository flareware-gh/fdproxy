"""Main CLI application using Typer."""

import os
import sys
from datetime import datetime

import typer
from rich.console import Console

from fdproxy.config import get_collector_version, load_env
from fdproxy.models import JsonEnvelope, TriggerEnvelope

app = typer.Typer(
    name="fdproxy",
    help="FDProxy CLI - Research infrastructure for late-day 0DTE ETF options",
    add_completion=False,
)

console = Console()


def output_result(envelope: JsonEnvelope, json_mode: bool) -> None:
    """Output result in JSON or human-readable format."""
    if json_mode:
        typer.echo(envelope.model_dump_json(indent=2))
    else:
        if envelope.ok:
            console.print(f"[green]✓[/green] {envelope.command} completed")
            if envelope.data:
                for key, value in envelope.data.items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(f"[red]✗[/red] {envelope.command} failed")
            for error in envelope.errors:
                console.print(f"  [red]Error:[/red] {error}")


@app.callback()
def main(
    env_file: str = typer.Option(".env", help="Path to .env file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """FDProxy CLI main callback."""
    load_env(env_file)


@app.command()
def collect(
    slot: str | None = typer.Option(
        None, help="Slot name (m0935, t1530, etc.) or 'auto' (soft label)"
    ),
    symbols: str | None = typer.Option(None, help="Comma-separated symbols (default: all)"),
    strict: bool = typer.Option(False, help="Exit 1 if any symbol fails"),
    dry_run: bool = typer.Option(False, help="Fetch and compute without DB writes"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    trigger_source: str | None = typer.Option(
        None, help="Trigger source (github_actions, vercel_cron, manual, agent)"
    ),
    trigger_id: str | None = typer.Option(None, help="Trigger ID (e.g., GitHub run ID)"),
    intended_at: str | None = typer.Option(None, help="Intended time (ISO 8601 timestamp)"),
):
    """
    Collect underlying quotes and 0DTE option chains.

    Timestamp-first collection: always saves (except holidays) regardless of wall-clock
    distance from named slots. Slot names are soft labels assigned when near a planned time.

    Examples:
        fdproxy collect --slot auto
        fdproxy collect --slot t1530 --json
        fdproxy collect --symbols SPY,QQQ --dry-run
        fdproxy collect --trigger-source github_actions --trigger-id $GITHUB_RUN_ID
    """
    from fdproxy import collect_svc

    envelope = JsonEnvelope(
        ok=False,
        command="collect",
        collector_version=get_collector_version(),
    )

    try:
        # Build trigger envelope from flags and environment
        trigger = TriggerEnvelope(
            trigger_source=trigger_source or os.getenv("FDPROXY_TRIGGER_SOURCE"),
            trigger_id=trigger_id or os.getenv("GITHUB_RUN_ID") or os.getenv("FDPROXY_TRIGGER_ID"),
            intended_at=datetime.fromisoformat(intended_at) if intended_at else None,
            intended_slot=slot if slot and slot != "auto" else None,
            symbols=symbols.split(",") if symbols else None,
        )

        result = collect_svc.run_collect(
            slot=slot,
            symbols=symbols.split(",") if symbols else None,
            strict=strict,
            dry_run=dry_run,
            trigger=trigger,
        )

        envelope.ok = result.status in ["ok", "partial", "skipped_holiday"]
        envelope.data = result.model_dump(mode="json")

        if result.status == "failed":
            envelope.errors.append("Collection failed")

    except Exception as e:
        envelope.ok = False
        envelope.errors.append(str(e))

    output_result(envelope, json)
    sys.exit(0 if envelope.ok else 1)


@app.command()
def status(
    days: int = typer.Option(5, help="Number of days to query"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """
    Show collection status and health.

    Examples:
        fdproxy status
        fdproxy status --days 3 --json
    """
    envelope = JsonEnvelope(
        ok=False,
        command="status",
        collector_version=get_collector_version(),
    )

    # TODO: Implement status logic
    envelope.ok = True
    envelope.data = {
        "message": "Status command not yet implemented",
        "days": days,
    }

    output_result(envelope, json)
    sys.exit(0)


@app.command()
def simulate(
    from_date: str = typer.Option(..., "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="End date (YYYY-MM-DD)"),
    entry_slot: str = typer.Option("t1530", help="Entry slot"),
    symbols: str | None = typer.Option(None, help="Comma-separated symbols"),
    write_outcomes: bool = typer.Option(False, help="Write to contract_outcomes table"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """
    Simulate option paths and compute multiples from stored snapshots.

    Examples:
        fdproxy simulate --from 2026-10-27 --to 2026-11-27
        fdproxy simulate --from 2026-10-27 --to 2026-11-27 --entry-slot t1530 --json
    """
    envelope = JsonEnvelope(
        ok=False,
        command="simulate",
        collector_version=get_collector_version(),
    )

    # TODO: Implement simulate logic
    envelope.ok = True
    envelope.data = {
        "message": "Simulate command not yet implemented",
        "from": from_date,
        "to": to_date,
        "entry_slot": entry_slot,
    }

    output_result(envelope, json)
    sys.exit(0)


@app.command()
def study(
    analysis: str = typer.Argument(..., help="Analysis type: feasibility or convexity"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """
    Run offline research studies.

    Examples:
        fdproxy study feasibility
        fdproxy study convexity
    """
    envelope = JsonEnvelope(
        ok=False,
        command="study",
        collector_version=get_collector_version(),
    )

    # TODO: Implement study logic
    envelope.ok = True
    envelope.data = {
        "message": f"Study {analysis} not yet implemented",
        "analysis": analysis,
    }

    output_result(envelope, json)
    sys.exit(0)


@app.command()
def doctor(
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """
    Validate environment and connectivity.

    Examples:
        fdproxy doctor
        fdproxy doctor --json
    """
    from fdproxy import doctor_svc

    envelope = JsonEnvelope(
        ok=False,
        command="doctor",
        collector_version=get_collector_version(),
    )

    try:
        checks = doctor_svc.run_checks()
        envelope.ok = all(check.ok for check in checks)
        envelope.data = {"checks": [check.model_dump() for check in checks]}

        if not envelope.ok:
            envelope.errors.append("Some checks failed")

    except Exception as e:
        envelope.ok = False
        envelope.errors.append(str(e))

    output_result(envelope, json)
    sys.exit(0 if envelope.ok else 1)


if __name__ == "__main__":
    app()
