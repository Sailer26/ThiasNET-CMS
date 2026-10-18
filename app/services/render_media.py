"""Media nel sito (D-80, D-81): `<img>` responsive, file scaricabili, tag per i social.

Solo markup escapato e classi: niente `style=` (CSP, D-69). Il punto focale arriva al CSS
con le classi `cms-fx-N`/`cms-fy-N` (N = 0…10) di `app/static/cms/media.css`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from markupsafe import Markup

from app.services.render_context import MediaView, PageContext, VariantView

SIZES_RE = re.compile(r"[0-9a-z(),.:%\s-]{1,200}")
CLASS_RE = re.compile(r"[a-z0-9_ -]{0,80}")
FOCAL_STEPS = 10
KB, MB = 1024, 1024 * 1024
OG_SIZE = "_og"
MEDIA_CSS = "/static/cms/media.css"


def _focal_classes(media: MediaView) -> str:
    fx = round(media.focal_x / 100 * FOCAL_STEPS)
    fy = round(media.focal_y / 100 * FOCAL_STEPS)
    return f"cms-img cms-fx-{fx} cms-fy-{fy}"


def variants_for(media: MediaView, size: str) -> tuple[VariantView, ...]:
    """Le varianti del formato; se mancano (tema cambiato) il master, mai un buco (D-73)."""
    found = media.sizes.get(size)
    if found:
        return found
    if media.width and media.height:
        return (VariantView(media.width, media.height, media.url),)
    return ()


def img_markup(
    media: MediaView,
    size: str,
    *,
    sizes: object = None,
    eager: bool = False,
    css_class: object = None,
) -> Markup:
    variants = variants_for(media, size)
    if not variants:
        return Markup("")
    base = variants[0]
    srcset = ", ".join(f"{v.url} {v.width}w" for v in variants)
    size_hint = (
        sizes
        if isinstance(sizes, str) and SIZES_RE.fullmatch(sizes)
        else f"(min-width: {base.width}px) {base.width}px, 100vw"
    )
    extra = css_class if isinstance(css_class, str) and CLASS_RE.fullmatch(css_class) else ""
    classes = f"{_focal_classes(media)} {extra}".strip()
    return Markup(
        '<img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{w}" height="{h}" alt="{alt}" '
        'loading="{loading}" decoding="async" class="{cls}">'
    ).format(
        src=base.url,
        srcset=srcset,
        sizes=size_hint,
        w=base.width,
        h=base.height,
        alt=media.alt,
        loading="eager" if eager else "lazy",
        cls=classes,
    )


def size_label(size_bytes: int) -> str:
    """Peso leggibile all'italiana: "340 kB", "1,2 MB"."""
    if size_bytes >= MB:
        return f"{size_bytes / MB:.1f} MB".replace(".", ",")
    return f"{max(1, round(size_bytes / KB))} kB"


def file_info(media: MediaView) -> Mapping[str, Any]:
    return {
        "url": media.url,
        "name": media.name,
        "ext": media.ext.upper(),
        "size_label": size_label(media.size_bytes),
    }


def social_markup(context: PageContext, title: str, description: str | None) -> Markup:
    """Open Graph e Twitter: indirizzi assoluti da SITE_URL, mai dall'header Host (D-62)."""
    base = context.site.base_url
    parts = [
        Markup('<meta property="og:type" content="website">'),
        Markup('<meta property="og:title" content="{}">').format(title),
        Markup('<meta property="og:url" content="{}">').format(base + context.page.path),
    ]
    if description:
        parts.append(Markup('<meta property="og:description" content="{}">').format(description))
    image = context.og_image
    variants = variants_for(image, OG_SIZE) if image is not None else ()
    if image is not None and variants:
        picked = variants[-1]
        parts += [
            Markup('<meta property="og:image" content="{}">').format(base + picked.url),
            Markup('<meta property="og:image:width" content="{}">').format(picked.width),
            Markup('<meta property="og:image:height" content="{}">').format(picked.height),
            Markup('<meta property="og:image:alt" content="{}">').format(image.alt),
            Markup('<meta name="twitter:card" content="summary_large_image">'),
        ]
    else:
        parts.append(Markup('<meta name="twitter:card" content="summary">'))
    parts.append(Markup('<link rel="stylesheet" href="{}">').format(MEDIA_CSS))
    return Markup("\n").join(parts)
