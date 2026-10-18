"""Immagini e PDF generati in memoria per i test della libreria media."""

from __future__ import annotations

import io

from PIL import Image

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def image_bytes(
    fmt: str = "PNG",
    size: tuple[int, int] = (40, 30),
    color: tuple[int, ...] = (200, 30, 30),
    mode: str = "RGB",
    **save: object,
) -> bytes:
    image = Image.new(mode, size, color)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **save)
    return buffer.getvalue()


def open_image(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image
