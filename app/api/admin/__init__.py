"""API JSON del pannello admin (`/api/admin/*`), usate dalla SPA React (D-22)."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")

# Le route si registrano sul blueprint all'import.
from app.api.admin import audit, auth, blocks, page_drafts, pages, users  # noqa: E402, F401
