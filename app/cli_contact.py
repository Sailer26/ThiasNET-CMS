"""Comandi CLI del modulo contatti (da lanciare con cron).

- `flask send-contact-messages`   ritenta le email non partite (ogni 10 minuti)
- `flask purge-contact-messages`  cancella i messaggi più vecchi di 12 mesi (ogni giorno, D-67)
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app.services import contact_form


@click.command("send-contact-messages")
@with_appcontext
def send_contact_messages_command() -> None:
    """Ritenta l'invio dei messaggi non ancora consegnati (massimo 5 tentativi, ultimi 3 giorni)."""
    sent, failed = contact_form.retry_pending()
    click.echo(f"Messaggi inviati: {sent}")
    if failed:
        click.echo(f"Messaggi ancora da inviare: {failed}", err=True)
        raise click.exceptions.Exit(1)


@click.command("purge-contact-messages")
@with_appcontext
def purge_contact_messages_command() -> None:
    """Cancella i messaggi del modulo contatti più vecchi di 12 mesi."""
    click.echo(f"Messaggi cancellati: {contact_form.purge_expired()}")


CONTACT_COMMANDS = (send_contact_messages_command, purge_contact_messages_command)
