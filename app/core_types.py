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
# D-142: "ultime notizie" arriva con le collezioni (Fase 7); fino ad allora non si può scegliere.
ENABLED_WIDGET_TYPES: frozenset[str] = WIDGET_TYPES - {"latest_entries"}
