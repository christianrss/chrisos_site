#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, json, re, shutil, subprocess
from frontmatter import read_page

MAX_FULL_CHARS=24000
CONTEXT_LINES=100

def run(source,*args):
    return subprocess.run(["git","-C",str(source),*args],text=True,capture_output=True,check=False)

def symbol_extract(text,symbols):
    if not symbols:
        return None
    lines=text.splitlines()
    chunks=[]
    seen=set()
    for symbol in symbols:
        pat=re.compile(r"\b"+re.escape(symbol)+r"\b")
        hits=[i for i,line in enumerate(lines) if pat.search(line)]
        for i in hits[:4]:
            lo=max(0,i-CONTEXT_LINES)
            hi=min(len(lines),i+CONTEXT_LINES+1)
            key=(lo,hi)
            if key in seen:
                continue
            seen.add(key)
            chunks.append(f"/* context for {symbol}: lines {lo+1}-{hi} */\n"+"\n".join(lines[lo:hi]))
    return "\n\n".join(chunks) if chunks else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--source",required=True)
    ap.add_argument("--out",default=".context")
    ap.add_argument("--full",action="store_true",help="Copy complete declared sources even when large")
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
    symbols=meta.get("symbols") or []
    manifest=[]
    for rel in sources:
        src=source/rel
        if not src.is_file():
            manifest.append({"path":rel,"mode":"missing-or-nonfile"})
            continue
        text=src.read_text(encoding="utf-8",errors="replace")
        extracted=None if args.full or len(text)<=MAX_FULL_CHARS else symbol_extract(text,symbols)
        dst=out/"source"/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        if extracted:
            dst.write_text(extracted+"\n",encoding="utf-8")
            manifest.append({"path":rel,"mode":"symbol-context","source_chars":len(text),"packed_chars":len(extracted)})
        else:
            shutil.copy2(src,dst)
            manifest.append({"path":rel,"mode":"full","source_chars":len(text),"packed_chars":len(text)})
    rev=meta.get("reviewed_revision")
    head=run(source,"rev-parse","HEAD").stdout.strip()
    diff=""
    if rev and run(source,"cat-file","-e",f"{rev}^{{commit}}").returncode==0 and sources:
        diff=run(source,"diff",f"{rev}..{head}","--",*sources).stdout
    (out/"DIFF.patch").write_text(diff,encoding="utf-8")
    (out/"META.json").write_text(json.dumps({
      "page":str(page),"id":pid,"reviewed_revision":rev,"head":head,
      "sources":sources,"symbols":symbols,
      "depends_on":meta.get("depends_on") or [],"related":meta.get("related") or [],
      "packed_sources":manifest
    },indent=2),encoding="utf-8")
    (out/"INSTRUCTIONS.md").write_text(
      "# Context-pack instructions\n\n"
      "Reconcile PAGE.md against supplied source material and DIFF.patch. "
      "Large files may contain only symbol-centered excerpts; request --full only when an unresolved dependency requires it. "
      "Do not scan unrelated repository areas. Preserve theory, architecture, implementation, validation, limitations and roadmap as distinct claims.\n",
      encoding="utf-8")
    print(out)

if __name__=="__main__":
    main()
