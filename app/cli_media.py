"""Comandi CLI della libreria media.

- `flask media-variants [--dry-run]`  dopo un deploy che cambia `image_sizes` del tema,
  crea le varianti mancanti delle immagini già caricate (D-73). Si può rilanciare.
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app.services import media


@click.command("media-variants")
@click.option("--dry-run", is_flag=True, help="Mostra quante immagini andrebbero aggiornate")
@with_appcontext
def media_variants_command(dry_run: bool) -> None:
    """Crea le varianti mancanti delle immagini dopo un cambio del tema."""
    pending = media.media_missing_variants()
    if dry_run:
        click.echo(f"Immagini da aggiornare: {len(pending)}")
        return
    done, failed = media.refresh_variants(pending)
    click.echo(f"Immagini aggiornate: {done}")
    if failed:
        click.echo(f"Immagini non aggiornate: {failed}", err=True)
        raise click.exceptions.Exit(1)


MEDIA_COMMANDS = (media_variants_command,)
