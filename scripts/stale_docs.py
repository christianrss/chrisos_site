#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, subprocess
from frontmatter import iter_pages, read_page

def git(source,*args,check=True):
    p=subprocess.run(["git","-C",str(source),*args],text=True,capture_output=True)
    if check and p.returncode:
        raise RuntimeError(p.stderr.strip())
    return p

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--docs",default="docs")
    args=ap.parse_args()
    source,docs=Path(args.source),Path(args.docs)
    head=git(source,"rev-parse","HEAD").stdout.strip()
    stale=[]
    invalid=[]
    for page in iter_pages(docs):
        meta,_=read_page(page)
        sources=meta.get("sources") or []
        rev=meta.get("reviewed_revision")
        if not sources or not rev:
            continue
        if git(source,"cat-file","-e",f"{rev}^{{commit}}",check=False).returncode:
            invalid.append((page,rev))
            continue
        changed=set(git(source,"diff","--name-only",f"{rev}..{head}","--",*sources).stdout.splitlines())
        if changed:
            stale.append((page,rev,sorted(changed)))
    for lang in ("en","pt-br"):
        pt=lang=="pt-br"
        target=docs/lang/"98-maintenance"/"review-queue.md"
        target.parent.mkdir(parents=True,exist_ok=True)
        tick=chr(96)
        lines=["---","id: review-queue",f"lang: {lang}","type: generated-status","status: generated",f"reviewed_revision: {head}","---","",
          f"# {'Fila de revisão' if pt else 'Documentation review queue'}","",f"ChrisOS HEAD: {tick}{head}{tick}",""]
        if not stale:
            lines.append("Nenhuma página declarada está obsoleta em relação às suas fontes." if pt else "No declared page is stale relative to its source dependencies.")
        else:
            lines += [f"| {'Página' if pt else 'Page'} | {'Revisão' if pt else 'Reviewed at'} | {'Fontes alteradas' if pt else 'Changed sources'} |","|---|---|---|"]
            for p,rev,changed in stale:
                lines.append(f"| {tick}{p.relative_to(docs)}{tick} | {tick}{rev[:12]}{tick} | {', '.join(tick+x+tick for x in changed)} |")
        if invalid:
            lines += ["",f"## {'Revisões inválidas' if pt else 'Invalid revisions'}",""]
            for p,rev in invalid:
                lines.append(f"- {tick}{p.relative_to(docs)}{tick}: {tick}{rev}{tick}")
        target.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"stale={len(stale)} invalid_revision={len(invalid)} head={head}")

if __name__=="__main__":
    main()
