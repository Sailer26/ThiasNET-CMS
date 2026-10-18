"""Comandi CLI sulle pagine.

- `flask publish-scheduled`  pubblica le pagine programmate scadute (cron ogni minuto, D-16)
"""

from __future__ import annotations

from datetime import UTC, datetime

import click
from flask.cli import with_appcontext

from app.services import publishing


@click.command("publish-scheduled")
@with_appcontext
def publish_scheduled_command() -> None:
    """Pubblica le pagine con data di pubblicazione scaduta. Si può lanciare ogni minuto."""
    result = publishing.run_due(datetime.now(UTC))
    click.echo(f"Pagine pubblicate: {result.published}")
    if result.failed:  # il cron lo segnala; i dettagli sono nel log dell'app
        click.echo(f"Pagine non pubblicate per errore: {result.failed}", err=True)
        raise click.exceptions.Exit(1)


PAGE_COMMANDS = (publish_scheduled_command,)
