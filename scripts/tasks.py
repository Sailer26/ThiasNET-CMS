"""Comandi di progetto senza `make` (D-17).

Uso: python scripts/tasks.py <dev|test|lint|migrate|theme-check|admin-*>
Usa l'interprete con cui viene lanciato: attivare prima la .venv.
I comandi `admin-*` lavorano sul pannello React in `admin/` con npm (D-96).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "admin"
PY = sys.executable
FLASK = [PY, "-m", "flask", "--app", "app"]

COMMANDS: dict[str, list[list[str]]] = {
    "dev": [[*FLASK, "run", "--debug", "--port", "5000"]],
    "test": [[PY, "-m", "pytest", "-q", "--cov=app", "--cov-report=term-missing"]],
    "lint": [
        [PY, "-m", "ruff", "check", "."],
        [PY, "-m", "ruff", "format", "--check", "."],
        [PY, "-m", "mypy"],
    ],
    "migrate": [[*FLASK, "db", "upgrade"]],
    "theme-check": [[PY, "-m", "app.theme_check"]],
}
# Pannello (D-96): `npm` si cerca nel PATH (su Windows è `npm.cmd`, invisibile a subprocess).
ADMIN_COMMANDS: dict[str, list[str]] = {
    "admin-install": ["ci", "--ignore-scripts"],  # nessuno script dei pacchetti serve al pannello
    "admin-dev": ["run", "dev"],
    "admin-build": ["run", "build"],
    "admin-test": ["run", "test:coverage"],
    "admin-lint": ["run", "lint"],
}
NO_NPM = "npm non trovato: installa Node.js 24 (https://nodejs.org) e riapri il terminale."


# L'app non parte senza APP_ENV (fail-closed): i comandi locali usano lo sviluppo.
DEV_ENV = {**os.environ, "APP_ENV": os.environ.get("APP_ENV", "development")}


def _run(command: Sequence[str], cwd: Path = ROOT) -> int:
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, cwd=cwd, env=DEV_ENV, check=False).returncode


def _admin(name: str) -> int:
    npm = shutil.which("npm")
    if npm is None:
        print(NO_NPM, file=sys.stderr)
        return 1
    return _run([npm, *ADMIN_COMMANDS[name]], cwd=ADMIN_DIR)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comandi di ThiasNET CMS")
    parser.add_argument("command", choices=sorted({*COMMANDS, *ADMIN_COMMANDS}))
    args = parser.parse_args(argv)
    if args.command in ADMIN_COMMANDS:
        return _admin(args.command)

    for step in COMMANDS[args.command]:
        code = _run(step)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
