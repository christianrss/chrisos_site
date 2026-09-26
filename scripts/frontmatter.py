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
    body = text[end + 5:]
    return meta, body

def iter_pages(docs: Path):
    for path in sorted(docs.rglob("*.md")):
        if "/99-source-atlas/generated/" in path.as_posix():
            continue
        yield path
