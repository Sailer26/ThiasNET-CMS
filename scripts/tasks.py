"""Comandi di progetto senza `make` (D-17).

Uso: python scripts/tasks.py <dev|test|lint|migrate|theme-check>
Usa l'interprete con cui viene lanciato: attivare prima la .venv.
"""

from __future__ import annotations

import argparse
import os
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
        [PY, "-m", "mypy", "app"],
    ],
    "migrate": [[*FLASK, "db", "upgrade"]],
    "theme-check": [[PY, "-m", "app.theme_check"]],
}


# L'app non parte senza APP_ENV (fail-closed): i comandi locali usano lo sviluppo.
DEV_ENV = {**os.environ, "APP_ENV": os.environ.get("APP_ENV", "development")}


def _run(command: Sequence[str]) -> int:
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=DEV_ENV, check=False).returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comandi di ThiasNET CMS")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)

    steps = list(COMMANDS[args.command])
    if args.command == "lint" and (ADMIN_DIR / "package.json").is_file():
        steps.append(["npm", "--prefix", str(ADMIN_DIR), "run", "lint"])

    for step in steps:
        code = _run(step)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
