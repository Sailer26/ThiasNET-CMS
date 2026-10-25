"""Tipi di blocco e widget conosciuti dal core.

Tutti i temi usano questi stessi tipi (D-04); in Fase 2 i blocchi passano al registry.
"""

from __future__ import annotations

BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "hero",
        "heading",
        "text",
        "image",
        "gallery",
        "text_image",
        "cta",
        "quote",
        "video",
        "divider",
        "map",
        "files",
        "contacts",
    }
)

WIDGET_TYPES: frozenset[str] = frozenset(
    {"notice", "contacts_inline", "hours", "contacts", "social", "latest_entries", "text", "cta"}
)
# D-142, D-155: dalla Fase 7b anche "ultime notizie"; l'insieme resta per spegnere un tipo.
ENABLED_WIDGET_TYPES: frozenset[str] = WIDGET_TYPES
