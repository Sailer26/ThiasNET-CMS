"""Comandi del progetto.

`theme-check` esiste in due forme:
- `flask --app app theme-check` (richiede che il tema attivo sia valido, perché l'app parte);
- `python -m app.theme_check` che NON crea l'app: serve proprio quando il tema attivo è rotto.
"""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app
from flask.cli import with_appcontext

from app.cli_contact import CONTACT_COMMANDS
from app.cli_pages import PAGE_COMMANDS
from app.cli_users import USER_COMMANDS
from app.services.theme import ThemeValidationError, load_theme
from app.services.theme_lint import lint_theme


def check_all_themes(themes_dir: Path) -> tuple[list[str], int]:
    """Valida ogni cartella in `themes_dir`. Restituisce (righe di report, numero di errori)."""
    if not themes_dir.is_dir():
        return [f"ERRORE la cartella dei temi non esiste: {themes_dir}"], 1
    lines: list[str] = []
    failures = 0
    candidates = sorted(
        p for p in themes_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    for candidate in candidates:
        try:
            theme = load_theme(themes_dir, candidate.name)
        except ThemeValidationError as exc:
            failures += 1
            lines.append(f"ERRORE {exc}")
            continue
        errors, warnings = lint_theme(theme)  # template (D-63)
        lines += [f"AVVISO {warning}" for warning in warnings]
        if errors:
            failures += 1
            lines += [f"ERRORE {error}" for error in errors]
        else:
            lines.append(f"OK     {candidate.name}")
    return lines, failures


@click.command("theme-check")
@with_appcontext  # necessario: add_command() non aggiunge da solo il contesto dell'app
def theme_check_command() -> None:
    """Valida theme.json di tutti i temi in THEMES_DIR."""
    lines, failures = check_all_themes(Path(current_app.config["THEMES_DIR"]))
    for line in lines:
        click.echo(line)
    if failures:
        raise click.exceptions.Exit(1)


def register_cli(app: Flask) -> None:
    app.cli.add_command(theme_check_command)
    for command in (*USER_COMMANDS, *PAGE_COMMANDS, *CONTACT_COMMANDS):
        app.cli.add_command(command)
