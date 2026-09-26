#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, yaml
from frontmatter import iter_pages, read_page

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--docs",default="docs")
    ap.add_argument("--manifest",default="data/documentation-manifest.yml")
    args=ap.parse_args()
    docs=Path(args.docs)
    data=yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    existing=set()
    for p in iter_pages(docs):
        meta,_=read_page(p)
        if meta.get("id") and not str(meta.get("type","")).startswith("generated"):
            existing.add(meta["id"])
    planned=[]
    for volume,v in data["volumes"].items():
        for ch in v.get("chapters",[]):
            planned.append((volume,ch["id"],ch["title"],ch.get("priority","expansion")))
    missing=[x for x in planned if x[1] not in existing]
    present=[x for x in planned if x[1] in existing]
    pct=(100.0*len(present)/len(planned)) if planned else 100.0
    for lang in ("en","pt-br"):
        pt=lang=="pt-br"
        target=docs/lang/"98-maintenance"/"coverage.md"
        lines=[
          "---","id: documentation-coverage",f"lang: {lang}","type: generated-status","status: generated","---","",
          f"# {'Cobertura do corpus' if pt else 'Documentation corpus coverage'}","",
          f"{'Capítulos autorais planejados' if pt else 'Planned authored chapters'}: **{len(planned)}**  ",
          f"{'Presentes' if pt else 'Present'}: **{len(present)}**  ",
          f"{'Pendentes de expansão' if pt else 'Pending expansion'}: **{len(missing)}**  ",
          f"{'Cobertura estrutural' if pt else 'Structural coverage'}: **{pct:.1f}%**","",
          "> "+("Pendente não significa página vazia. O manifesto define unidades futuras; páginas só entram no corpus quando possuem conteúdo técnico substantivo." if pt else "Pending does not mean an empty placeholder page. The manifest defines future units; pages enter the corpus only when substantive technical content exists."),"",
          f"## {'Capítulos existentes' if pt else 'Existing authored chapters'}","",
          "| Volume | ID | Title |","|---|---|---|"
        ]
        for vol,pid,title,priority in present:
            lines.append(f"| {vol} | `{pid}` | {title} |")
        lines += ["",f"## {'Próximas unidades' if pt else 'Pending units'}","",
                  "| Volume | ID | Priority | Title |","|---|---|---|---|"]
        for vol,pid,title,priority in missing:
            lines.append(f"| {vol} | `{pid}` | {priority} | {title} |")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"coverage planned={len(planned)} present={len(present)} missing={len(missing)}")

if __name__=="__main__":
    main()
