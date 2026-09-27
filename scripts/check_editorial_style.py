#!/usr/bin/env python3
"""Reject conversational editorial patterns in foundational and entry pages."""

from __future__ import annotations

from pathlib import Path
import argparse
import re

from frontmatter import iter_pages, read_page

QUESTION_HEADING_EN = re.compile(r"^#{2,4}\s+(?:why|what|how|when|where|who)\b", re.I)
QUESTION_HEADING_PT = re.compile(r"^#{2,4}\s+(?:por que|o que|como|quando|onde|quem)\b", re.I)
DIRECT_EN = re.compile(r"\b(?:let's|let us|you|your|yours|imagine)\b", re.I)
DIRECT_PT = re.compile(r"\b(?:você|vocês|vamos|imagine|vejamos)\b", re.I)
QUESTION_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+.*\?\s*$")


def in_scope(path: Path, meta: dict) -> bool:
    posix = path.as_posix()
    if "/01-foundations/" in posix:
        return True
    return meta.get("type") in {"landing", "volume-index"}


def prose_lines(body: str):
    fenced = False
    fence_marker = None
    ticks = chr(96) * 3
    tildes = "~" * 3
    for number, raw in enumerate(body.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith(ticks) or stripped.startswith(tildes):
            marker = stripped[:3]
            if not fenced:
                fenced = True
                fence_marker = marker
            elif marker == fence_marker:
                fenced = False
                fence_marker = None
            continue
        if fenced:
            continue
        if stripped.startswith("|"):
            continue
        yield number, raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()

    errors: list[str] = []
    docs = Path(args.docs)

    for page in iter_pages(docs):
        meta, body = read_page(page)
        if not in_scope(page, meta):
            continue
        lang = meta.get("lang")
        direct = DIRECT_PT if lang == "pt-br" else DIRECT_EN
        question_heading = QUESTION_HEADING_PT if lang == "pt-br" else QUESTION_HEADING_EN

        for number, line in prose_lines(body):
            if question_heading.search(line):
                errors.append(f"{page}:{number}: interrogative heading: {line.strip()}")
            if QUESTION_BULLET.search(line):
                errors.append(f"{page}:{number}: question-form list item: {line.strip()}")
            match = direct.search(line)
            if match:
                errors.append(
                    f"{page}:{number}: direct/conversational address {match.group(0)!r}: {line.strip()}"
                )

    if errors:
        print("\n".join("ERROR: " + item for item in errors))
        raise SystemExit(1)

    print("editorial style: foundational and entry pages use declarative technical prose")


if __name__ == "__main__":
    main()
