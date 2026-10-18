"""Genera le miniature PNG delle varianti del tema `default` (D-64).

Uso (a mano, poi si fa commit delle immagini):
    python scripts/make_variant_thumbnails.py

Solo libreria standard. Sono schizzi semplici: Thias può sostituirli con immagini disegnate,
basta che restino PNG, JPG o WebP veri con lo stesso nome (D-63).
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "themes" / "default" / "assets" / "variants"
WIDTH, HEIGHT = 240, 160

Color = tuple[int, int, int]
PAPER: Color = (247, 248, 250)
INK: Color = (32, 33, 36)
GREY: Color = (189, 193, 198)
IMAGE: Color = (134, 168, 214)
ACCENT: Color = (11, 95, 255)
DARK: Color = (32, 33, 36)
LIGHT_TEXT: Color = (232, 234, 237)

Canvas = list[list[Color]]
Rect = tuple[int, int, int, int]  # x, y, larghezza, altezza


def _canvas(background: Color) -> Canvas:
    return [[background] * WIDTH for _ in range(HEIGHT)]


def _fill(canvas: Canvas, rect: Rect, color: Color) -> Canvas:
    x, y, w, h = rect
    return [
        [
            color if x <= col < x + w and y <= row < y + h else pixel
            for col, pixel in enumerate(line)
        ]
        for row, line in enumerate(canvas)
    ]


def _lines(canvas: Canvas, x: int, y: int, width: int, count: int, color: Color) -> Canvas:
    for index in range(count):
        canvas = _fill(canvas, (x, y + index * 14, width - (index % 2) * 30, 6), color)
    return canvas


def _png(canvas: Canvas) -> bytes:
    raw = b"".join(b"\x00" + bytes(c for pixel in line for c in pixel) for line in canvas)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    signature = bytes.fromhex("89504e470d0a1a0a")
    return (
        signature
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def hero_image_full() -> Canvas:
    canvas = _fill(_canvas(PAPER), (0, 0, WIDTH, HEIGHT), IMAGE)
    canvas = _fill(canvas, (30, 60, 180, 14), INK)
    return _fill(canvas, (30, 90, 70, 18), ACCENT)


def hero_split() -> Canvas:
    canvas = _fill(_canvas(PAPER), (125, 0, 115, HEIGHT), IMAGE)
    canvas = _fill(canvas, (16, 50, 95, 14), INK)
    canvas = _lines(canvas, 16, 76, 95, 2, GREY)
    return _fill(canvas, (16, 110, 60, 16), ACCENT)


def text_image_left() -> Canvas:
    return _lines(_fill(_canvas(PAPER), (16, 30, 96, 100), IMAGE), 128, 40, 96, 6, GREY)


def text_image_right() -> Canvas:
    return _lines(_fill(_canvas(PAPER), (128, 30, 96, 100), IMAGE), 16, 40, 96, 6, GREY)


def text_image_dark() -> Canvas:
    return _lines(_fill(_canvas(DARK), (16, 30, 96, 100), IMAGE), 128, 40, 96, 6, LIGHT_TEXT)


def _cta(background: Color, text: Color, button: Color) -> Canvas:
    canvas = _fill(_canvas(background), (40, 50, 160, 14), text)
    return _fill(canvas, (80, 90, 80, 20), button)


def cta_light() -> Canvas:
    return _cta(PAPER, INK, ACCENT)


def cta_accent() -> Canvas:
    return _cta(ACCENT, PAPER, PAPER)


def cta_dark() -> Canvas:
    return _cta(DARK, LIGHT_TEXT, ACCENT)


def quote_simple() -> Canvas:
    canvas = _fill(_canvas(PAPER), (30, 40, 6, 70), GREY)
    return _lines(canvas, 48, 45, 160, 4, INK)


def quote_highlight() -> Canvas:
    canvas = _fill(_canvas(PAPER), (16, 24, 208, 112), ACCENT)
    return _lines(canvas, 36, 50, 168, 4, PAPER)


def _grid(columns: int) -> Canvas:
    canvas = _canvas(PAPER)
    gap = 8
    size = (WIDTH - gap * (columns + 1)) // columns
    for row in range(2):
        for col in range(columns):
            x, y = gap + col * (size + gap), 20 + row * (size + gap)
            canvas = _fill(canvas, (x, y, size, size), IMAGE)
    return canvas


def gallery_grid_3() -> Canvas:
    return _grid(3)


def gallery_grid_4() -> Canvas:
    return _grid(4)


THUMBNAILS: dict[str, Callable[[], Canvas]] = {
    "hero-image_full.png": hero_image_full,
    "hero-split.png": hero_split,
    "text_image-image_left.png": text_image_left,
    "text_image-image_right.png": text_image_right,
    "text_image-dark.png": text_image_dark,
    "cta-light.png": cta_light,
    "cta-accent.png": cta_accent,
    "cta-dark.png": cta_dark,
    "quote-simple.png": quote_simple,
    "quote-highlight.png": quote_highlight,
    "gallery-grid_3.png": gallery_grid_3,
    "gallery-grid_4.png": gallery_grid_4,
}


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, draw in THUMBNAILS.items():
        (TARGET / name).write_bytes(_png(draw()))
        print(f"OK {name}")


if __name__ == "__main__":
    main()
