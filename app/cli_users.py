"""Comandi CLI sugli utenti: richiedono accesso al server (D-29, D-31).

- `flask create-owner --email ...`  crea l'owner (unico modo: mai via API)
- `flask set-password --email ...`  reimposta una password e chiude le sessioni
- `flask disable-totp --email ...`  toglie il secondo fattore a chi ha perso il telefono
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.services import audit, users
from app.services.errors import ServiceError

password_option = click.option(
    "--password",
    prompt="Password",
    hide_input=True,
    confirmation_prompt="Ripeti la password",
)


def _abort(exc: ServiceError) -> click.ClickException:
    return click.ClickException(exc.message)


@click.command("create-owner")
@click.option("--email", required=True, help="Email dell'owner")
@click.option("--additional", is_flag=True, help="Consente un owner in più")
@password_option
@with_appcontext
def create_owner_command(email: str, additional: bool, password: str) -> None:
    """Crea l'owner (Thias). È l'unico modo di creare un owner."""
    try:
        owner = users.create_owner(email, password, additional=additional)
    except ServiceError as exc:
        raise _abort(exc) from exc
    click.echo(f"Owner creato: {owner.email}")


@click.command("set-password")
@click.option("--email", required=True)
@password_option
@with_appcontext
def set_password_command(email: str, password: str) -> None:
    """Reimposta la password di un utente e chiude tutte le sue sessioni."""
    try:
        user = users.require_by_email(email)
        users.set_password(user, password)
    except ServiceError as exc:
        raise _abort(exc) from exc
    audit.record("auth.password_reset_cli", actor_id=None, entity="user", entity_id=user.id)
    db.session.commit()
    click.echo(f"Password aggiornata per {user.email}")


@click.command("disable-totp")
@click.option("--email", required=True)
@with_appcontext
def disable_totp_command(email: str) -> None:
    """Toglie il codice a 6 cifre (recupero senza codici di recupero, D-29)."""
    try:
        user = users.require_by_email(email)
    except ServiceError as exc:
        raise _abort(exc) from exc
    users.clear_totp(user)
    audit.record("totp.reset_cli", actor_id=None, entity="user", entity_id=user.id)
    db.session.commit()
    click.echo(f"Codice a 6 cifre disattivato per {user.email}")


USER_COMMANDS = (create_owner_command, set_password_command, disable_totp_command)
