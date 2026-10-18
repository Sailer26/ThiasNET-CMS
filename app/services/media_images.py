"""Immagini: decodifica con limiti, ricodifica senza metadati, varianti (D-71 … D-73, D-80).

Modulo puro: byte in ingresso, byte in uscita. Non scrive mai file: l'unica `save` di Pillow
scrive in un `io.BytesIO` (eccezione motivata in `tests/security/test_golden_rule.py`).
Si usano solo operazioni che restituiscono immagini nuove (`resize`, `crop`, `convert`).
Ogni errore di Pillow diventa `ImageError` (422 per l'utente), mai un errore interno.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageCms, ImageOps

MASTER_MAX_SIDE = 3840
WEBP_MAX_SIDE = 16383  # limite del formato WebP
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
FORMAT_BY_EXT = {ext: fmt for fmt, (ext, _mime) in EXTENSIONS.items()}
# Le foto dei telefoni con più immagini (MPO) sono JPEG: si usa la prima.
DECODED_AS = {"JPEG": frozenset({"JPEG", "MPO"})}
PILLOW_ERRORS = (
    OSError,
    SyntaxError,
    ValueError,
    MemoryError,
    SystemError,
    Image.DecompressionBombError,
)
SRGB = ImageCms.createProfile("sRGB")
MAX_ICC_BYTES = 1024 * 1024


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
        image = Image.open(io.BytesIO(data), formats=[fmt])
        if image.format not in DECODED_AS.get(fmt, frozenset({fmt})):
            raise ImageError("Il contenuto del file non corrisponde al formato")
        if image.width * image.height > max_pixels:
            raise ImageError("Immagine troppo grande: riducila prima di caricarla")
        image.seek(0)  # GIF animate e MPO: solo la prima immagine
        image.load()
    except ImageError:
        raise
    except PILLOW_ERRORS as exc:
        raise ImageError("File danneggiato o non leggibile") from exc
    return image


def _to_srgb(image: Image.Image) -> Image.Image:
    """Colori dal profilo incorporato a sRGB, prima di ogni conversione di modo (CMYK incluso)."""
    profile = image.info.get("icc_profile")
    if (
        not profile
        or len(profile) > MAX_ICC_BYTES
        or image.mode not in {"RGB", "RGBA", "CMYK", "L"}
    ):
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        mode = "RGBA" if image.mode == "RGBA" else "RGB"
        return ImageCms.profileToProfile(image, source, SRGB, outputMode=mode) or image
    except (ImageCms.PyCMSError, OSError, ValueError):
        return image  # profilo illeggibile: si scarta, i colori possono variare di poco


def normalize(image: Image.Image) -> Image.Image:
    """Orientamento applicato, colori sRGB, RGB/RGBA, nessun metadato (D-72)."""
    rotated = ImageOps.exif_transpose(image) or image
    has_alpha = rotated.mode in {"RGBA", "LA", "PA"} or "transparency" in rotated.info
    if rotated.mode.startswith("I;16") or rotated.mode == "I":
        rotated = rotated.point(lambda value: value / 256).convert("L")
    colored = _to_srgb(rotated)
    converted = colored.convert("RGBA" if has_alpha else "RGB")
    # Copia dei soli pixel: EXIF, ICC, XMP e commenti restano indietro.
    return Image.frombytes(converted.mode, converted.size, converted.tobytes())


def _encode(image: Image.Image, fmt: str, **options: Any) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **options)  # unica save: in memoria, mai su file
    return buffer.getvalue()


def _fit(image: Image.Image, width: int, max_side: int = WEBP_MAX_SIDE) -> Image.Image:
    """Ridimensiona alla larghezza voluta senza ingrandire e senza superare `max_side`."""
    scale = min(1.0, width / image.width, max_side / max(image.size))
    if scale >= 1:
        return image
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def prepare(image: Image.Image) -> Image.Image:
    """Immagine pulita e al massimo MASTER_MAX_SIDE sul lato lungo: base di master e varianti."""
    clean = normalize(image)
    return _fit(clean, clean.width, MASTER_MAX_SIDE)


def encode_master(clean: Image.Image, fmt: str) -> EncodedImage:
    target = MASTER_FORMAT[fmt]
    if clean.mode == "RGBA" and target == "JPEG":
        target = "PNG"  # trasparenza da un profilo o da un colore chiave: il JPEG non la regge
    ext, mime = EXTENSIONS[target]
    return EncodedImage(
        _encode(clean, target, **MASTER_OPTIONS[target]), clean.width, clean.height, ext, mime
    )


def master(image: Image.Image, fmt: str) -> EncodedImage:
    """L'immagine conservata: ricodificata, al massimo MASTER_MAX_SIDE sul lato lungo."""
    return encode_master(prepare(image), fmt)


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
    crop_w = max(1, min(image.width, round(image.height * width_ratio / height_ratio)))
    crop_h = max(1, min(image.height, round(crop_w * height_ratio / width_ratio)))
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


def variants_from(
    clean: Image.Image, image_sizes: Mapping[str, Any], focal: tuple[int, int]
) -> list[Variant]:
    """Varianti WebP da un'immagine già pulita (il master)."""
    found: list[Variant] = []
    for size, spec in sorted(image_sizes.items()):
        width = spec.get("width") if isinstance(spec, Mapping) else None
        if not isinstance(width, int) or width < 1:
            continue
        ratio = _ratio(spec)
        source = crop_to_ratio(clean, ratio, focal) if ratio else clean
        found += [_webp(source, size, w) for w in _widths(width, source.width)]
    found.append(_webp(clean, "_panel", PANEL_WIDTH))
    found.append(_webp(crop_to_ratio(clean, OG_SIZE, focal), "_og", OG_SIZE[0]))
    return found


def variants(
    image: Image.Image, image_sizes: Mapping[str, Any], focal: tuple[int, int]
) -> list[Variant]:
    return variants_from(prepare(image), image_sizes, focal)


def process(
    data: bytes,
    fmt: str,
    *,
    max_pixels: int,
    image_sizes: Mapping[str, Any],
    focal: tuple[int, int],
) -> tuple[EncodedImage, list[Variant]]:
    """Caricamento: decodifica, una sola pulizia, master e varianti. Errori → ImageError."""
    image = decode(data, fmt, max_pixels=max_pixels)
    try:
        clean = prepare(image)
        return encode_master(clean, fmt), variants_from(clean, image_sizes, focal)
    except PILLOW_ERRORS as exc:
        raise ImageError(
            "Immagine non elaborabile: prova a salvarla di nuovo e ricaricarla"
        ) from exc


def variants_from_master(
    data: bytes, ext: str, *, image_sizes: Mapping[str, Any], focal: tuple[int, int]
) -> list[Variant]:
    """Nuove varianti dal master già salvato, senza ricodificarlo (punto focale, cambio tema)."""
    fmt = FORMAT_BY_EXT[ext]
    try:
        clean = Image.open(io.BytesIO(data), formats=[fmt])
        clean.load()
        return variants_from(
            clean.convert("RGBA" if clean.mode == "RGBA" else "RGB"), image_sizes, focal
        )
    except PILLOW_ERRORS as exc:
        raise ImageError("Il file originale non si riesce più a leggere") from exc
