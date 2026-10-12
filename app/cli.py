"""Comandi `flask ...` del progetto."""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import with_appcontext

from app.services.theme import ThemeValidationError, load_theme


@click.command("theme-check")
@with_appcontext
def theme_check_command() -> None:
    """Valida theme.json di tutti i temi in THEMES_DIR."""
    themes_dir = Path(current_app.config["THEMES_DIR"])
    candidates = sorted(
        p for p in themes_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    failures = 0
    for candidate in candidates:
        try:
            load_theme(themes_dir, candidate.name)
        except ThemeValidationError as exc:
            failures += 1
            click.echo(f"ERRORE {exc}")
        else:
            click.echo(f"OK     {candidate.name}")
    if failures:
        raise click.exceptions.Exit(1)


def register_cli(app: Flask) -> None:
    app.cli.add_command(theme_check_command)
