"""Comandi CLI di "Chiedi a Thias" (da lanciare con cron, D-134).

- `flask send-support-requests`   ritenta le email non partite (ogni 10 minuti)
- `flask purge-support-requests`  cancella le richieste più vecchie di 12 mesi (ogni giorno)
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app.services import support


@click.command("send-support-requests")
@with_appcontext
def send_support_requests_command() -> None:
    """Ritenta l'invio delle richieste di assistenza non ancora consegnate."""
    sent, failed = support.retry_pending()
    click.echo(f"Richieste inviate: {sent}")
    if failed:
        click.echo(f"Richieste ancora da inviare: {failed}", err=True)
        raise click.exceptions.Exit(1)


@click.command("purge-support-requests")
@with_appcontext
def purge_support_requests_command() -> None:
    """Cancella le richieste di assistenza più vecchie di 12 mesi."""
    click.echo(f"Richieste cancellate: {support.purge_expired()}")


SUPPORT_COMMANDS = (send_support_requests_command, purge_support_requests_command)
