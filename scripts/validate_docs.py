#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import re

from frontmatter import iter_pages, read_page

REQUIRED = {"id", "lang", "type"}
PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|REPLACE_ID|REPLACE_SOURCE|REPLACE_REVISION)\b|lorem ipsum"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()

    source = Path(args.source)
    docs = Path(args.docs)
    errors = []
    warnings = []
    seen = {}
    pairs = {}
    types = {}

    for page in iter_pages(docs):
        meta, body = read_page(page)
        missing = REQUIRED - set(meta)
        if missing:
            errors.append(f"{page}: missing frontmatter {sorted(missing)}")

        pid = meta.get("id")
        lang = meta.get("lang")
        typ = str(meta.get("type", ""))
        if pid and lang:
            key = (pid, lang)
            if key in seen:
                errors.append(f"duplicate id/lang {key}: {seen[key]} and {page}")
            seen[key] = page
            pairs.setdefault(pid, set()).add(lang)
            types.setdefault(pid, set()).add(typ)

        for src in meta.get("sources") or []:
            if not (source / src).exists():
                errors.append(f"{page}: missing source {src}")

        if not typ.startswith("generated"):
            placeholder = PLACEHOLDER_RE.search(body)
            if placeholder:
                errors.append(f"{page}: placeholder token {placeholder.group(0)!r}")
            if typ not in {"landing", "volume-index"} and len(body.strip()) < 1200:
                warnings.append(
                    f"{page}: authored technical body is only {len(body.strip())} characters; "
                    "coverage.py will classify it as below the depth target"
                )

    for pid, langs in sorted(pairs.items()):
        generated = any(t.startswith("generated") for t in types.get(pid, set()))
        if not generated and langs != {"en", "pt-br"}:
            errors.append(f"{pid}: languages={sorted(langs)}, expected en and pt-br")

    for warning in warnings:
        print("WARNING: " + warning)

    if errors:
        print("\n".join("ERROR: " + error for error in errors))
        raise SystemExit(1)

    print(
        f"validated {len(seen)} page/language identities; "
        f"depth_warnings={len(warnings)}"
    )


if __name__ == "__main__":
    main()
