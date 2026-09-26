#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, json, shutil, subprocess
from frontmatter import read_page

def run(source,*args):
    return subprocess.run(["git","-C",str(source),*args],text=True,capture_output=True,check=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--source",required=True)
    ap.add_argument("--out",default=".context")
    args=ap.parse_args()
    page,source=Path(args.page),Path(args.source)
    meta,_=read_page(page)
    pid=meta.get("id") or page.stem
    out=Path(args.out)/pid
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(page,out/"PAGE.md")
    sources=meta.get("sources") or []
    for rel in sources:
        src=source/rel
        if src.exists():
            dst=out/"source"/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
    rev=meta.get("reviewed_revision")
    head=run(source,"rev-parse","HEAD").stdout.strip()
    diff=""
    if rev and run(source,"cat-file","-e",f"{rev}^{{commit}}").returncode==0 and sources:
        diff=run(source,"diff",f"{rev}..{head}","--",*sources).stdout
    (out/"DIFF.patch").write_text(diff,encoding="utf-8")
    (out/"META.json").write_text(json.dumps({
      "page":str(page),"id":pid,"reviewed_revision":rev,"head":head,
      "sources":sources,"symbols":meta.get("symbols") or [],
      "depends_on":meta.get("depends_on") or [],"related":meta.get("related") or []
    },indent=2),encoding="utf-8")
    (out/"INSTRUCTIONS.md").write_text(
      "# Context-pack instructions\n\n"
      "Reconcile PAGE.md against the supplied source files and DIFF.patch. "
      "Do not scan unrelated repository areas unless a declared dependency cannot be resolved. "
      "Preserve the distinction between theory, architecture, implementation, validation, limitations and roadmap.\n",
      encoding="utf-8")
    print(out)

if __name__=="__main__":
    main()
