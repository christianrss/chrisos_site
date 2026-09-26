#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, re, subprocess

EXTS = {".c",".h",".cc",".cpp",".s",".S",".asm",".ld",".py",".md",".sh"}
SKIP = {".git","build","third_party"}
FUNC_RE = re.compile(r"^[\t ]*(?:[A-Za-z_][\w\s\*]+?)[\t ]+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", re.M)
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)

def git(source, *args):
    return subprocess.check_output(["git","-C",str(source),*args], text=True).strip()

def scan(source: Path):
    rows=[]
    for p in sorted(source.rglob("*")):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        rel=p.relative_to(source)
        if any(part in SKIP for part in rel.parts):
            continue
        raw=p.read_bytes()
        text=raw.decode("utf-8",errors="replace")
        rows.append({
          "path":rel.as_posix(),
          "lines": text.count("\n")+1,
          "bytes":len(raw),
          "sha256":hashlib.sha256(raw).hexdigest(),
          "includes":INCLUDE_RE.findall(text)[:80],
          "symbols":FUNC_RE.findall(text)[:160],
        })
    return rows

def generated_page(row, rev, lang):
    pt=lang=="pt-br"
    title=("Referência de fonte: " if pt else "Source reference: ")+row["path"]
    tick=chr(96)
    sym=", ".join(tick+x+tick for x in row["symbols"]) or ("Nenhuma função C detectada pelo scanner." if pt else "No C-like function definition detected by the scanner.")
    inc=", ".join(tick+x+tick for x in row["includes"]) or ("Nenhum include detectado." if pt else "No include detected.")
    return f"""---
id: source-{row['sha256'][:16]}
lang: {lang}
type: generated-source-reference
status: generated
reviewed_revision: {rev}
sources:
  - {row['path']}
---

# {title}

> {"Esta página é gerada de forma determinística; não editar manualmente." if pt else "This page is generated deterministically; do not edit it manually."}

| {"Campo" if pt else "Field"} | {"Valor" if pt else "Value"} |
|---|---|
| Path | {tick}{row['path']}{tick} |
| Lines | {row['lines']} |
| Bytes | {row['bytes']} |
| SHA-256 | {tick}{row['sha256']}{tick} |
| ChrisOS revision | {tick}{rev}{tick} |

## {"Includes detectados" if pt else "Detected includes"}

{inc}

## {"Símbolos detectados" if pt else "Detected symbols"}

{sym}

## {"Uso" if pt else "Use"}

{"A interpretação arquitetural pertence às páginas autorais. Este registro fornece identidade, tamanho, dependências sintáticas simples e símbolos para navegação e context packs." if pt else "Architectural interpretation belongs in authored pages. This record provides identity, size, simple syntactic dependencies and symbols for navigation and context packs."}
"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--docs",default="docs")
    args=ap.parse_args()
    source, docs=Path(args.source), Path(args.docs)
    rev=git(source,"rev-parse","HEAD")
    rows=scan(source)
    for lang in ("en","pt-br"):
        root=docs/lang/"99-source-atlas"/"generated"
        root.mkdir(parents=True,exist_ok=True)
        for old in root.rglob("*.md"):
            old.unlink()
        for row in rows:
            target=root/(row["path"]+".md")
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(generated_page(row,rev,lang),encoding="utf-8")
        idx=docs/lang/"99-source-atlas"/"inventory.md"
        idx.parent.mkdir(parents=True,exist_ok=True)
        pt=lang=="pt-br"
        tick=chr(96)
        lines=[
          "---","id: generated-source-inventory",f"lang: {lang}","type: generated-index",
          "status: generated",f"reviewed_revision: {rev}","---","",
          f"# {'Inventário de fonte' if pt else 'Source inventory'}","",
          f"> {'Gerado a partir da branch main do ChrisOS.' if pt else 'Generated from the ChrisOS main branch.'}","",
          f"Revision: {tick}{rev}{tick}","",f"Files indexed: **{len(rows)}**","",
          f"| {'Arquivo' if pt else 'File'} | {'Linhas' if pt else 'Lines'} | Bytes |","|---|---:|---:|"
        ]
        for row in rows:
            rel="generated/"+row["path"]+".md"
            lines.append(f"| [{row['path']}]({rel}) | {row['lines']} | {row['bytes']} |")
        idx.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"indexed {len(rows)} source files at {rev}")

if __name__=="__main__":
    main()
