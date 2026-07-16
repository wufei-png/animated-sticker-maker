#!/usr/bin/env python3
"""Render one offline Review Page from separated HTML, CSS, and JavaScript assets."""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path


ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "review-page"


def safe_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


@lru_cache(maxsize=1)
def review_assets() -> tuple[str, str, str]:
    return tuple(
        (ASSET_DIR / name).read_text(encoding="utf-8")
        for name in ("template.html", "style.css", "script.js")
    )


def render_review_html(model: dict[str, object]) -> str:
    payload = safe_json(model)
    text = model["text"]
    assert isinstance(text, dict)
    template, style, script = review_assets()
    rendered_script = script.replace("__REVIEW_DATA__", payload)
    return (
        template.replace(
            "__HTML_LANG__",
            html.escape(str(text["html_lang"]), quote=True),
        )
        .replace("__DOCUMENT_TITLE__", html.escape(str(text["document_title"])))
        .replace("__REVIEW_CSS__", style)
        .replace("__REVIEW_SCRIPT__", rendered_script)
    )
