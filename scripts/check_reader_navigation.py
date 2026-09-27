#!/usr/bin/env python3
"""Static contracts for the documentation reader before MkDocs rendering."""

from pathlib import Path
import argparse
import re


def require(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{path}: missing reader contracts {missing}")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()
    docs = Path(args.docs)

    theme = require(
        Path("theme/main.html"),
        [
            'id="nav-panel"',
            'id="search-dialog"',
            'id="global-search"',
            'class="chapter-rail"',
            'class="mobile-bookbar"',
            'class="book-pager"',
            'class="section-title-link"',
            'class="section-toggle"',
            'class="chapter-info"',
            'class="reader-current-title"',
        ],
    )
    require(
        docs / "assets/site.js",
        [
            "function openNav()",
            "function openSearch()",
            "function loadSearchIndex()",
            "function searchDocuments(",
            "versionedUrl(",
            "reader-",
            "active-section",
            "ArrowDown",
            "section-toggle",
        ],
    )
    require(
        docs / "assets/site.css",
        [
            ".search-dialog",
            ".chapter-rail",
            ".mobile-bookbar",
            "@media(max-width:1120px)",
            "@media(max-width:720px)",
            ".sidebar.is-open",
            ".section-title-link",
        ],
    )

    for lang in ("en", "pt-br"):
        path = docs / lang / "learning-path.md"
        text = path.read_text(encoding="utf-8")
        if not re.findall(r"^## \[[^\]]+\]\([^)]+\)", text, re.M):
            raise AssertionError(f"{path}: no curriculum level links to authored content")
        if not re.findall(r"^### \[[^\]]+\]\([^)]+\)", text, re.M):
            raise AssertionError(f"{path}: no curriculum module links to authored content")

    if 'aria-label="{{ \'Sumário do livro\'' not in theme:
        raise AssertionError("theme/main.html: bilingual book-contents accessibility label missing")

    print(
        "reader contracts passed: hierarchical book navigation, responsive drawer, "
        "direct indexed search, chapter TOC and sequential reading controls are present"
    )


if __name__ == "__main__":
    main()
