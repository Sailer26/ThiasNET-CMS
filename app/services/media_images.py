"""Immagini: decodifica con limiti, ricodifica senza metadati, varianti (D-71 … D-73, D-80).

Modulo puro: byte in ingresso, byte in uscita. Non scrive mai file: l'unica `save` di Pillow
scrive in un `io.BytesIO` (eccezione motivata in `tests/security/test_golden_rule.py`).
Si usano solo operazioni che restituiscono immagini nuove (`resize`, `crop`, `convert`).
"""

from __future__ import annotations

import io
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageCms, ImageOps

MASTER_MAX_SIDE = 3840
PANEL_WIDTH = 400
OG_SIZE = (1200, 630)
VARIANT_QUALITY = 80
MASTER_OPTIONS: Mapping[str, dict[str, Any]] = {
    "JPEG": {"quality": 88, "optimize": True, "progressive": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 85, "method": 4},
}
MASTER_FORMAT = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WEBP", "GIF": "PNG"}  # GIF → PNG statico
EXTENSIONS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
SRGB = ImageCms.createProfile("sRGB")


class ImageError(ValueError):
    """Immagine non utilizzabile: il messaggio è in italiano e si mostra all'utente."""


@dataclass(frozen=True)
class EncodedImage:
    data: bytes
    width: int
    height: int
    ext: str
    mime: str


@dataclass(frozen=True)
class Variant:
    size: str  # chiave di image_sizes del tema, oppure "_panel" / "_og" del CMS
    width: int
    height: int
    data: bytes


def decode(data: bytes, fmt: str, *, max_pixels: int) -> Image.Image:
    """Apre l'immagine solo con il decoder del formato riconosciuto e controlla le dimensioni
    prima di decodificare i pixel (niente "bombe" di decompressione)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data), formats=[fmt])
            if image.format != fmt:
                raise ImageError("Il contenuto del file non corrisponde al formato")
            if image.width * image.height > max_pixels:
                raise ImageError("Immagine troppo grande: riducila prima di caricarla")
            image.seek(0)  # GIF animate: solo il primo fotogramma
            image.load()
    except ImageError:
        raise
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError, Warning) as exc:
        raise ImageError("File danneggiato o non leggibile") from exc
    return image


def _to_srgb(image: Image.Image) -> Image.Image:
    profile = image.info.get("icc_profile")
    if not profile or image.mode not in {"RGB", "RGBA"}:
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        return ImageCms.profileToProfile(image, source, SRGB, outputMode=image.mode) or image
    except (ImageCms.PyCMSError, OSError, ValueError):
        return image  # profilo illeggibile: si scarta, i colori possono variare di poco


def normalize(image: Image.Image) -> Image.Image:
    """Orientamento applicato, colori sRGB, RGB/RGBA, nessun metadato (D-72)."""
    rotated = ImageOps.exif_transpose(image) or image
    has_alpha = rotated.mode in {"RGBA", "LA", "PA"} or (
        rotated.mode == "P" and "transparency" in rotated.info
    )
    if rotated.mode.startswith("I;16") or rotated.mode == "I":
        rotated = rotated.point(lambda value: value / 256).convert("L")
    converted = rotated.convert("RGBA" if has_alpha else "RGB")
    if "icc_profile" in rotated.info:
        converted.info["icc_profile"] = rotated.info["icc_profile"]
    colored = _to_srgb(converted)
    # Copia dei soli pixel: EXIF, ICC, XMP e commenti restano indietro.
    return Image.frombytes(colored.mode, colored.size, colored.tobytes())


def _encode(image: Image.Image, fmt: str, **options: Any) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **options)  # unica save: in memoria, mai su file
    return buffer.getvalue()


def _fit(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def master(image: Image.Image, fmt: str) -> EncodedImage:
    """L'immagine conservata: ricodificata, al massimo MASTER_MAX_SIDE sul lato lungo."""
    clean = normalize(image)
    scale = min(1.0, MASTER_MAX_SIDE / max(clean.size))
    if scale < 1:
        size = (max(1, round(clean.width * scale)), max(1, round(clean.height * scale)))
        clean = clean.resize(size, Image.Resampling.LANCZOS)
    target = MASTER_FORMAT[fmt]
    if target == "JPEG" and clean.mode == "RGBA":
        target = "PNG"  # il JPEG non ha trasparenza
    ext, mime = EXTENSIONS[target]
    data = _encode(clean, target, **MASTER_OPTIONS[target])
    return EncodedImage(data, clean.width, clean.height, ext, mime)


def _ratio(spec: Mapping[str, Any]) -> tuple[int, int] | None:
    raw = spec.get("ratio")
    if not isinstance(raw, str) or ":" not in raw:
        return None
    left, _, right = raw.partition(":")
    if not (left.isdigit() and right.isdigit()) or int(left) == 0 or int(right) == 0:
        return None
    return int(left), int(right)


def crop_to_ratio(
    image: Image.Image, ratio: tuple[int, int], focal: tuple[int, int]
) -> Image.Image:
    """Il ritaglio più grande con quel rapporto, il più vicino possibile al punto focale."""
    width_ratio, height_ratio = ratio
    crop_w = min(image.width, round(image.height * width_ratio / height_ratio))
    crop_h = min(image.height, round(crop_w * height_ratio / width_ratio))
    center_x = image.width * focal[0] / 100
    center_y = image.height * focal[1] / 100
    left = int(min(max(center_x - crop_w / 2, 0), image.width - crop_w))
    top = int(min(max(center_y - crop_h / 2, 0), image.height - crop_h))
    return image.crop((left, top, left + crop_w, top + crop_h))


def _webp(image: Image.Image, size: str, width: int) -> Variant:
    fitted = _fit(image, width)
    data = _encode(fitted, "WEBP", quality=VARIANT_QUALITY, method=4)
    return Variant(size, fitted.width, fitted.height, data)


def _widths(base: int, available: int) -> list[int]:
    """Larghezza normale e doppia (schermi ad alta densità), mai oltre l'immagine."""
    return sorted({min(base, available), min(base * 2, available)})


def variants(
    image: Image.Image, image_sizes: Mapping[str, Any], focal: tuple[int, int]
) -> list[Variant]:
    clean = normalize(image)
    found: list[Variant] = []
    for size, spec in sorted(image_sizes.items()):
        width = spec.get("width") if isinstance(spec, Mapping) else None
        if not isinstance(width, int) or width < 1:
            continue
        ratio = _ratio(spec)
        source = crop_to_ratio(clean, ratio, focal) if ratio else clean
        found += [_webp(source, size, w) for w in _widths(width, source.width)]
    found.append(_webp(clean, "_panel", PANEL_WIDTH))
    found.append(_webp(crop_to_ratio(clean, (OG_SIZE[0], OG_SIZE[1]), focal), "_og", OG_SIZE[0]))
    return found
