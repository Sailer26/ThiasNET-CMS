"""Distribuzione dei media (D-75): solo i file della revisione corrente di un media esistente.

Header che impediscono di eseguirli: tipo deciso dal CMS, `nosniff`, CSP `sandbox`. Le
immagini hanno nomi che cambiano a ogni revisione (cache di un anno); i PDF hanno un
indirizzo stabile (`file.pdf`) e si scaricano sempre come allegato con il nome originale.
"""

from __future__ import annotations

from flask import abort, request, send_file
from sqlalchemy import select
from werkzeug.wrappers import Response as BaseResponse

from app.extensions import db
from app.models.media import Media, MediaKind
from app.public import bp
from app.services import media_library, media_storage

IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
IMAGE_CACHE = 365 * 24 * 3600
DOCUMENT_CACHE = 300
MEDIA_CSP = "default-src 'none'; sandbox"


def _harden(response: BaseResponse) -> BaseResponse:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = MEDIA_CSP
    return response


def _download_name(media: Media) -> str:
    name = media.original_name
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


@bp.get("/media/<key>/<filename>")
def media_file(key: str, filename: str) -> BaseResponse:
    if not media_storage.KEY_RE.fullmatch(key):
        abort(404)
    media = db.session.execute(select(Media).where(Media.storage_key == key)).scalar_one_or_none()
    if media is None:
        abort(404)
    if media.kind == MediaKind.DOCUMENT:
        if filename != media_library.DOCUMENT_FILE:
            abort(404)
        path = media_storage.existing(key, f"r{media.file_rev}.pdf")
        if path is None:
            abort(404)
        response = send_file(
            path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=_download_name(media),
            max_age=DOCUMENT_CACHE,
            conditional=True,
            etag=True,
        )
        return _harden(response.make_conditional(request))
    if filename not in media_library.stored_files(media):
        abort(404)
    path = media_storage.existing(key, filename)
    extension = filename.rsplit(".", 1)[-1]
    if path is None or extension not in IMAGE_TYPES:
        abort(404)
    response = send_file(
        path, mimetype=IMAGE_TYPES[extension], max_age=IMAGE_CACHE, conditional=True
    )
    response.headers["Cache-Control"] = f"public, max-age={IMAGE_CACHE}, immutable"
    return _harden(response)
