#!/usr/bin/env python3
"""Post-build smoke checks for generated reader navigation and search assets."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import argparse
import json


class ReaderHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section_links: list[str] = []
        self.ids: set[str] = set()
        self.hash_links: list[str] = []
        self.has_search = False
        self.has_mobile_bar = False

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        classes = set((data.get("class") or "").split())
        if data.get("id"):
            self.ids.add(data["id"])
        if data.get("id") == "search-dialog":
            self.has_search = True
        if "mobile-bookbar" in classes:
            self.has_mobile_bar = True
        if tag == "a":
            href = data.get("href") or ""
            if "section-title-link" in classes:
                self.section_links.append(href)
            if href.startswith("#") and len(href) > 1:
                self.hash_links.append(href[1:])


def inspect_html(path: Path) -> None:
    parser = ReaderHTML()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.has_search:
        raise AssertionError(f"{path}: search dialog missing")
    if not parser.has_mobile_bar:
        raise AssertionError(f"{path}: mobile reader bar missing")
    if len(parser.section_links) < 10:
        raise AssertionError(f"{path}: too few linked book sections ({len(parser.section_links)})")
    broken = [href for href in parser.section_links if not href.strip() or href != href.strip()]
    if broken:
        raise AssertionError(f"{path}: invalid section links {broken[:5]}")


def inspect_search(path: Path, lang: str) -> None:
    if not path.exists():
        raise AssertionError(f"{path}: reader search index missing")
    size = path.stat().st_size
    if size > 2_000_000:
        raise AssertionError(f"{path}: reader search payload too large ({size} bytes)")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("language") != lang:
        raise AssertionError(f"{path}: wrong language marker")
    docs = payload.get("docs") or []
    if len(docs) < 100:
        raise AssertionError(f"{path}: suspiciously small index ({len(docs)} records)")
    required = {"location", "title", "page_title", "kind", "text"}
    if any(required - set(doc) for doc in docs[:50]):
        raise AssertionError(f"{path}: incomplete search records")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="site")
    args = parser.parse_args()
    site = Path(args.site)

    for rel in ("en/index.html", "pt-br/index.html"):
        inspect_html(site / rel)

    inspect_search(site / "search/reader-en.json", "en")
    inspect_search(site / "search/reader-pt-br.json", "pt-br")

    for asset in ("assets/site.js", "assets/search-worker.js", "assets/site.css"):
        if not (site / asset).exists():
            raise AssertionError(f"{asset}: generated asset missing")

    print("built reader smoke checks passed")


if __name__ == "__main__":
    main()
