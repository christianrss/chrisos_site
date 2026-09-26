#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse
from frontmatter import iter_pages, read_page

REQUIRED={"id","lang","type"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--docs",default="docs")
    args=ap.parse_args()
    source,docs=Path(args.source),Path(args.docs)
    errors=[]
    seen={}
    pairs={}
    for page in iter_pages(docs):
        meta,_=read_page(page)
        missing=REQUIRED-set(meta)
        if missing:
            errors.append(f"{page}: missing frontmatter {sorted(missing)}")
        pid=meta.get("id")
        lang=meta.get("lang")
        if pid and lang:
            key=(pid,lang)
            if key in seen:
                errors.append(f"duplicate id/lang {key}: {seen[key]} and {page}")
            seen[key]=page
            pairs.setdefault(pid,set()).add(lang)
        for src in meta.get("sources") or []:
            if not (source/src).exists():
                errors.append(f"{page}: missing source {src}")
    for pid,langs in sorted(pairs.items()):
        paths=[p for (i,l),p in seen.items() if i==pid]
        generated=any("/99-source-atlas/generated/" in p.as_posix() or p.name in {"review-queue.md","inventory.md"} for p in paths)
        if not generated and langs != {"en","pt-br"}:
            errors.append(f"{pid}: languages={sorted(langs)}, expected en and pt-br")
    if errors:
        print("\n".join("ERROR: "+e for e in errors))
        raise SystemExit(1)
    print(f"validated {len(seen)} page/language identities")

if __name__=="__main__":
    main()
