"""Pannello e server danno lo stesso verdetto sugli stessi casi (D-106).

I casi stanno in tests/fixtures/safe_url_cases.json e li legge anche il test Vitest
admin/src/features/editor/schema/validate.test.ts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.blocks import Mode, get_registry
from app.services.sanitize import is_safe_url, normalize_url

CASES: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "safe_url_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("url", CASES["safe"])
def test_safe_urls(url: str) -> None:
    assert is_safe_url(url)


@pytest.mark.parametrize("url", CASES["unsafe"])
def test_unsafe_urls(url: str) -> None:
    assert not is_safe_url(url)


@pytest.mark.parametrize(("raw", "clean"), CASES["normalized"])
def test_normalized_urls(raw: str, clean: str) -> None:
    assert normalize_url(raw) == clean


@pytest.mark.parametrize("case", CASES["fields"], ids=lambda c: f"{c['block']}.{c['field']}")
def test_field_cases_in_draft_mode(case: dict[str, Any]) -> None:
    errors = get_registry().errors(case["block"], {case["field"]: case["value"]}, mode=Mode.DRAFT)
    assert (not errors) is case["ok"], errors
