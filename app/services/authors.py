"""Chi ha salvato: un'etichetta leggibile per il pannello (D-92, D-93)."""

from __future__ import annotations

from app.extensions import db
from app.models.user import Role, User

OWNER_LABEL = "ThiasNET (assistenza)"
UNKNOWN_LABEL = "un altro utente"


def display_name(user_id: int | None) -> str:
    """Email dell'utente; l'owner è l'assistenza ThiasNET; chi non esiste più resta anonimo."""
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        return UNKNOWN_LABEL
    if user.role == Role.OWNER:
        return OWNER_LABEL
    return user.email
