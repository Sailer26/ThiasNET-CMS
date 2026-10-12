"""`python -m app.theme_check`: valida tutti i temi SENZA avviare l'app.

Serve proprio quando il tema attivo è rotto e quindi `create_app()` (e `flask theme-check`)
non può partire.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from app.cli import check_all_themes
from app.config import PROJECT_ROOT


def main() -> int:
    themes_dir = Path(os.environ.get("THEMES_DIR", str(PROJECT_ROOT / "themes")))
    lines, failures = check_all_themes(themes_dir)
    for line in lines:
        click.echo(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
