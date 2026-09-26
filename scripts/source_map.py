#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, json
from frontmatter import iter_pages, read_page

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--docs",default="docs")
    ap.add_argument("--out",default="docs/generated-meta/source-map.json")
    args=ap.parse_args()
    docs=Path(args.docs)
    reverse={}
    pages={}
    for p in iter_pages(docs):
        meta,_=read_page(p)
        pid=meta.get("id")
        lang=meta.get("lang")
        if not pid or not lang:
            continue
        rel=p.relative_to(docs).as_posix()
        entry={
          "id":pid,
          "lang":lang,
          "path":rel,
          "type":meta.get("type"),
          "reviewed_revision":meta.get("reviewed_revision"),
          "sources":meta.get("sources") or [],
          "symbols":meta.get("symbols") or [],
          "depends_on":meta.get("depends_on") or [],
          "related":meta.get("related") or []
        }
        pages[rel]=entry
        for src in entry["sources"]:
            reverse.setdefault(src,[]).append(rel)
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    payload={"pages":pages,"source_to_docs":{k:sorted(v) for k,v in sorted(reverse.items())}}
    out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"source-map pages={len(pages)} sources={len(reverse)} -> {out}")

if __name__=="__main__":
    main()
