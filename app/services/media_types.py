"""Riconoscimento del tipo di file dai primi byte (D-70).

Estensione e Content-Type dichiarati dal browser non contano: un file `.png` con dentro HTML
non è un'immagine. Sono ammessi solo JPEG, PNG, WebP, GIF e PDF.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.media import MediaKind

JPEG = bytes.fromhex("ffd8ff")
PNG = bytes.fromhex("89504e470d0a1a0a")
GIF_HEADS = (b"GIF87a", b"GIF89a")
PDF = b"%PDF-"


@dataclass(frozen=True)
class DetectedType:
    kind: MediaKind
    format: str  # nome del formato per Pillow ("JPEG", "PNG", ...) o "PDF"
    mime: str
    ext: str


def sniff(data: bytes) -> DetectedType | None:
    head = data[:16]
    if head.startswith(JPEG):
        return DetectedType(MediaKind.IMAGE, "JPEG", "image/jpeg", "jpg")
    if head.startswith(PNG):
        return DetectedType(MediaKind.IMAGE, "PNG", "image/png", "png")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return DetectedType(MediaKind.IMAGE, "WEBP", "image/webp", "webp")
    if head[:6] in GIF_HEADS:
        return DetectedType(MediaKind.IMAGE, "GIF", "image/gif", "gif")
    if head.startswith(PDF):
        return DetectedType(MediaKind.DOCUMENT, "PDF", "application/pdf", "pdf")
    return None
