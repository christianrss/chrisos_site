#!/usr/bin/env python3
"""Static contracts for the documentation book-reader navigation."""

from pathlib import Path
import argparse
import re


def require(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{path}: missing navigation contracts {missing}")
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
            'class="reading-progress"',
            'class="book-pager"',
        ],
    )
    require(
        docs / "assets/site.js",
        [
            "function openNav()",
            "function openSearch()",
            "section-entry",
            "active-section",
            "ArrowDown",
            "IntersectionObserver",
        ],
    )
    require(
        docs / "assets/site.css",
        [
            ".search-dialog",
            ".chapter-rail",
            ".mobile-bookbar",
            "@media(max-width:820px)",
            ".sidebar.is-open",
        ],
    )

    for lang in ("en", "pt-br"):
        path = docs / lang / "learning-path.md"
        text = path.read_text(encoding="utf-8")
        linked_levels = re.findall(r"^## \[[^\]]+\]\([^)]+\)", text, re.M)
        linked_modules = re.findall(r"^### \[[^\]]+\]\([^)]+\)", text, re.M)
        if not linked_levels:
            raise AssertionError(f"{path}: no curriculum level links to authored content")
        if not linked_modules:
            raise AssertionError(f"{path}: no curriculum module links to authored content")

    if 'aria-label="{{ \'Sumário do livro\'' not in theme:
        raise AssertionError("theme/main.html: bilingual book-contents accessibility label missing")

    print(
        "reader navigation contracts passed: linked curriculum sections, book drawer, "
        "chapter TOC, global search and mobile chapter bar are present"
    )


if __name__ == "__main__":
    main()
