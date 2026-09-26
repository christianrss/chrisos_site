#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, subprocess
from frontmatter import iter_pages, read_page

def git(source,*args):
    return subprocess.check_output(["git","-C",str(source),*args],text=True).splitlines()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--docs",default="docs")
    ap.add_argument("--base",required=True,help="Git revision to compare against current source HEAD")
    args=ap.parse_args()
    source,docs=Path(args.source),Path(args.docs)
    changed=set(git(source,"diff","--name-only",f"{args.base}..HEAD"))
    affected=[]
    for p in iter_pages(docs):
        meta,_=read_page(p)
        sources=set(meta.get("sources") or [])
        hit=sorted(changed & sources)
        if hit:
            affected.append((p.relative_to(docs).as_posix(),hit))
    for page,hit in affected:
        print(page)
        for src in hit:
            print(f"  <- {src}")
    print(f"affected={len(affected)} changed_files={len(changed)}")

if __name__=="__main__":
    main()
