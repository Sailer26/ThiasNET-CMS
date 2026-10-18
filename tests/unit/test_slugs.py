"""Slug delle pagine (D-45): generati dal titolo, solo minuscole, cifre e trattini."""

from __future__ import annotations

import pytest

from app.services.errors import ServiceError
from app.services.slugs import SLUG_MAX_LENGTH, is_reserved, slugify, validate_slug


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Chi siamo", "chi-siamo"),
        ("Über uns", "ueber-uns"),
        ("Öffnungszeiten Ärzte", "oeffnungszeiten-aerzte"),
        ("Straße", "strasse"),
        ("Città e caffè", "citta-e-caffe"),
        ("  --Ciao!!  mondo-- ", "ciao-mondo"),
        ("Scuola dell'infanzia", "scuola-dell-infanzia"),
        ("Anno 2026", "anno-2026"),
        ("日本", ""),
    ],
)
def test_slugify(title: str, slug: str) -> None:
    assert slugify(title) == slug


def test_slugify_cuts_long_titles_at_a_word_boundary() -> None:
    slug = slugify("parola " * 30)
    assert len(slug) <= SLUG_MAX_LENGTH
    assert not slug.endswith("-")
    assert slug.endswith("parola")


@pytest.mark.parametrize("slug", ["chi-siamo", "a", "2026", "a-1-b"])
def test_valid_slugs(slug: str) -> None:
    validate_slug(slug)


@pytest.mark.parametrize("slug", ["Chi", "a--b", "-a", "a-", "a_b", "a b", "à", "x" * 81, ""])
def test_invalid_slugs(slug: str) -> None:
    with pytest.raises(ServiceError) as exc:
        validate_slug(slug)
    assert exc.value.status == 422


@pytest.mark.parametrize(
    "slug", ["api", "admin", "_preview", "static", "media", "assets", "it", "de", "rm", "en"]
)
def test_reserved_first_segments(slug: str) -> None:
    assert is_reserved(slug)


def test_ordinary_slug_is_not_reserved() -> None:
    assert not is_reserved("servizi")
