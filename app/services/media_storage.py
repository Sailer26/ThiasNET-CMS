"""Archivio dei file caricati (D-74): l'unico modulo dell'app che scrive file.

- Radice `MEDIA_ROOT`, che la configurazione tiene lontana da `themes/` e da `app/`.
- Percorso `<root>/<chiave[:2]>/<chiave>/<nome>`: chiave casuale e nome generati dal CMS,
  validati con espressioni regolari e ricontrollati dopo `resolve()` (niente symlink in uscita).
- Creazione esclusiva (`"xb"`): un file esistente non viene mai sovrascritto.
Eccezioni motivate in `tests/security/test_golden_rule.py`.
"""

from __future__ import annotations

import contextlib
import logging
import re
import secrets
from collections.abc import Iterable
from pathlib import Path

from flask import current_app

log = logging.getLogger("thiasnet.media")
KEY_RE = re.compile(r"[0-9a-f]{32}")
# r<rev>-master.<ext> · r<rev>-<formato>-<larghezza>.webp · r<rev>.pdf
NAME_RE = re.compile(
    r"r[0-9]{1,6}(?:-master\.(?:jpg|png|webp)|-_?[a-z][a-z0-9_]{0,63}-[0-9]{1,5}\.webp|\.pdf)"
)


class MediaStorageError(RuntimeError):
    """Chiave o nome non generati dal CMS, oppure file già esistente."""


def new_key() -> str:
    return secrets.token_hex(16)


def _root() -> Path:
    return Path(current_app.config["MEDIA_ROOT"]).resolve()


def path_for(key: str, name: str) -> Path:
    if not KEY_RE.fullmatch(key) or not NAME_RE.fullmatch(name):
        raise MediaStorageError(f"percorso non ammesso: {key!r}/{name!r}")
    root = _root()
    path = (root / key[:2] / key / name).resolve()
    if not path.is_relative_to(root):
        raise MediaStorageError("il percorso esce dalla cartella dei media")
    return path


def put(key: str, name: str, data: bytes) -> None:
    path = path_for(key, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.parent.resolve().is_relative_to(_root()):
        raise MediaStorageError("la cartella esce dalla cartella dei media")
    try:
        handle = path.open("xb")
    except FileExistsError as exc:
        raise MediaStorageError(f"il file esiste già: {name}") from exc
    try:
        with handle:
            handle.write(data)
    except OSError:
        path.unlink(missing_ok=True)  # niente file a metà (es. disco pieno)
        raise


def put_replacing_orphan(key: str, name: str, data: bytes, current: Iterable[str]) -> None:
    """Come `put`, ma un file rimasto da un tentativo fallito (non nella revisione corrente)
    si sostituisce: altrimenti quel media non potrebbe più cambiare revisione."""
    try:
        put(key, name, data)
    except MediaStorageError:
        if name in set(current):
            raise
        path_for(key, name).unlink(missing_ok=True)
        put(key, name, data)


def discard(key: str, names: Iterable[str]) -> None:
    """Cancella i file indicati e la cartella se resta vuota. Non solleva: un file bloccato
    (es. su Windows) resta orfano e innocuo, perché si serve solo ciò che il database conosce."""
    folder: Path | None = None
    for name in names:
        try:
            path = path_for(key, name)
            folder = path.parent
            path.unlink(missing_ok=True)
        except (OSError, MediaStorageError):
            log.exception("file del media %s non cancellato: %s", key, name)
    if folder is not None:
        with contextlib.suppress(OSError):  # non vuota: restano file di altre revisioni
            folder.rmdir()


def existing(key: str, name: str) -> Path | None:
    try:
        path = path_for(key, name)
    except MediaStorageError:
        return None
    return path if path.is_file() else None
