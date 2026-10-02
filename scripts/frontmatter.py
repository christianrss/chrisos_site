#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import yaml


def read_page(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}

    # The directory is authoritative for localized documentation.  Older and
    # newly authored pages may omit `lang` in front matter; normalize it here
    # so catalogue/build consumers do not fail on otherwise valid chapters.
    if not meta.get("lang"):
        parts = path.as_posix().split("/")
        if "pt-br" in parts:
            meta["lang"] = "pt-br"
        elif "en" in parts:
            meta["lang"] = "en"

    body = text[end + 5:]
    return meta, body


def iter_pages(docs: Path):
    for path in sorted(docs.rglob("*.md")):
        if "/99-source-atlas/generated/" in path.as_posix():
            continue
        yield path
