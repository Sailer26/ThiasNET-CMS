"""Formati riconosciuti dai byte, ricodifica senza metadati e varianti (D-70 … D-73, D-80)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.media_images import ImageError, decode, master, variants
from app.services.media_types import sniff
from tests.media_fixtures import PDF_BYTES, image_bytes, open_image

SIZES = {
    "card": {"width": 640, "ratio": "4:3"},
    "content": {"width": 1024},
    "thumb": {"width": 320, "ratio": "1:1"},
}


# --- Riconoscimento dai byte ---------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "kind", "ext"),
    [
        (image_bytes("JPEG"), "image", "jpg"),
        (image_bytes("PNG"), "image", "png"),
        (image_bytes("WEBP"), "image", "webp"),
        (image_bytes("GIF"), "image", "gif"),
        (PDF_BYTES, "document", "pdf"),
    ],
)
def test_supported_types_are_recognized(data: bytes, kind: str, ext: str) -> None:
    found = sniff(data)
    assert found is not None
    assert (found.kind, found.ext) == (kind, ext)


@pytest.mark.parametrize(
    "data",
    [
        b"<html><script>alert(1)</script></html>",
        b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>',
        b"<svg onload=alert(1)>",
        b"RIFF" + bytes(4) + b"WAVEfmt ",
        b"",
        b"PK" + bytes(10),  # ZIP, Word, Excel: non ammessi (D-70)
        b"   %PDF-1.4",  # il PDF deve iniziare subito
    ],
)
def test_anything_else_is_refused(data: bytes) -> None:
    assert sniff(data) is None


# --- Decodifica e limiti ----------------------------------------------------------


def test_too_many_pixels_is_refused_before_decoding() -> None:
    data = image_bytes("PNG", size=(1000, 1000))
    with pytest.raises(ImageError, match="grande"):
        decode(data, "PNG", max_pixels=100_000)


def test_truncated_or_mismatched_files_are_refused() -> None:
    data = image_bytes("JPEG", size=(200, 200))
    with pytest.raises(ImageError):
        decode(data[:200], "JPEG", max_pixels=10**7)
    with pytest.raises(ImageError):
        decode(image_bytes("PNG"), "JPEG", max_pixels=10**7)


# --- Ricodifica ---------------------------------------------------------------------


def _with_exif(orientation: int | None = None, gps: bool = False) -> bytes:
    image = Image.new("RGB", (20, 10), (10, 120, 200))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if gps:
        exif[0x8825] = {1: "N", 2: (46.0, 0.0, 0.0)}
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes(), icc_profile=b"finto-profilo")
    return buffer.getvalue()


def test_metadata_is_removed_and_orientation_applied() -> None:
    image = decode(_with_exif(orientation=6, gps=True), "JPEG", max_pixels=10**7)
    encoded = master(image, "JPEG")
    result = open_image(encoded.data)
    assert result.size == (10, 20)  # ruotata come la vede chi l'ha scattata
    assert not result.getexif()
    assert "icc_profile" not in result.info
    assert (encoded.width, encoded.height, encoded.ext) == (10, 20, "jpg")


@pytest.mark.parametrize(
    ("mode", "fmt", "color", "expected"),
    [
        ("CMYK", "JPEG", (0, 255, 255, 0), "RGB"),
        ("I;16", "PNG", 4000, "RGB"),
        ("RGBA", "PNG", (255, 0, 0, 128), "RGBA"),
        ("LA", "PNG", (100, 50), "RGBA"),
    ],
)
def test_color_modes_become_rgb_or_rgba(mode: str, fmt: str, color: object, expected: str) -> None:
    data = image_bytes(fmt, mode=mode, color=color)  # type: ignore[arg-type]
    result = open_image(master(decode(data, fmt, max_pixels=10**7), fmt).data)
    assert result.mode == expected


def test_animated_gif_keeps_the_first_frame_as_png() -> None:
    frames = [Image.new("P", (10, 10), i) for i in range(3)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
    encoded = master(
        decode(buffer.getvalue() + b"<script>x</script>", "GIF", max_pixels=10**7), "GIF"
    )
    assert encoded.ext == "png"
    assert b"<script>" not in encoded.data
    assert getattr(open_image(encoded.data), "n_frames", 1) == 1


def test_master_is_at_most_3840_pixels_wide() -> None:
    encoded = master(decode(image_bytes("PNG", size=(5000, 100)), "PNG", max_pixels=10**7), "PNG")
    assert (encoded.width, encoded.height) == (3840, 77)


# --- Varianti -----------------------------------------------------------------------


def _decoded(size: tuple[int, int]) -> Image.Image:
    return decode(image_bytes("PNG", size=size), "PNG", max_pixels=10**8)


def test_variants_follow_the_theme_sizes_without_upscaling() -> None:
    found = {(v.size, v.width, v.height) for v in variants(_decoded((1000, 800)), SIZES, (50, 50))}
    assert {("card", 640, 480), ("card", 1000, 750)} <= found
    assert ("content", 1000, 800) in found and not any(
        v[0] == "content" and v[1] > 1000 for v in found
    )
    assert {("thumb", 320, 320), ("thumb", 640, 640)} <= found
    small = {(v.size, v.width, v.height) for v in variants(_decoded((300, 200)), SIZES, (50, 50))}
    assert ("card", 267, 200) in small  # ritaglio 4:3 di 300x200: non si ingrandisce
    assert not any(w > 300 for _, w, _ in small)


def test_variants_are_webp_and_include_panel_and_social() -> None:
    found = {v.size: v for v in variants(_decoded((2000, 1500)), SIZES, (50, 50))}
    assert open_image(found["card"].data).format == "WEBP"
    assert (found["_og"].width, found["_og"].height) == (1200, 630)
    assert found["_panel"].width == 400


def test_crop_follows_the_focal_point() -> None:
    image = Image.new("RGB", (400, 100), (255, 255, 255))
    image.paste((255, 0, 0), (0, 0, 50, 100))  # rosso a sinistra
    left = next(v for v in variants(image, SIZES, (0, 50)) if v.size == "thumb")
    right = next(v for v in variants(image, SIZES, (100, 50)) if v.size == "thumb")
    assert (left.width, left.height) == (100, 100)
    red = open_image(left.data).convert("RGB").getpixel((5, 50))
    assert isinstance(red, tuple) and red[0] > 200
    assert open_image(right.data).convert("RGB").getpixel((5, 50)) != (255, 0, 0)
