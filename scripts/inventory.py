#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import re
import subprocess

TEXT_EXTENSIONS = {
    ".c", ".h", ".cc", ".cpp", ".cxx", ".s", ".asm", ".ld",
    ".py", ".md", ".sh", ".clv", ".lst", ".cls", ".cva",
    ".vert", ".frag", ".glsl", ".yml", ".yaml", ".json", ".toml",
    ".ini", ".cfg", ".bat", ".ps1", ".txt"
}
TEXT_NAMES = {
    "makefile", "license", ".gitignore", ".gitattributes", ".gitmodules"
}
SKIP_DIRS = {".git", "build", "site", ".venv", "__pycache__"}

FUNC_RE = re.compile(
    r"^[\t ]*(?:[A-Za-z_][\w\s\*]*?)[\t ]+([A-Za-z_]\w*)"
    r"\s*\([^;{}]*\)\s*(?:__attribute__\s*\(\([^)]*\)\)\s*)?\{",
    re.M,
)
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source), *args], text=True
    ).strip()


def is_text_candidate(path: Path) -> bool:
    return (
        path.suffix.lower() in TEXT_EXTENSIONS
        or path.name.lower() in TEXT_NAMES
        or (not path.suffix and path.stat().st_size < 2_000_000)
    )


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def detect_symbols(text: str) -> list[dict[str, object]]:
    rows = []
    for match in FUNC_RE.finditer(text):
        rows.append({"name": match.group(1), "line": line_number(text, match.start())})
        if len(rows) >= 400:
            break
    return rows


def detect_includes(text: str) -> list[dict[str, object]]:
    rows = []
    for match in INCLUDE_RE.finditer(text):
        rows.append({"name": match.group(1), "line": line_number(text, match.start())})
        if len(rows) >= 200:
            break
    return rows


def scan(source: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if not is_text_candidate(path):
            continue

        raw = path.read_bytes()
        if b"\x00" in raw[:8192]:
            continue

        text = raw.decode("utf-8", errors="replace")
        rows.append({
            "path": rel.as_posix(),
            "lines": text.count("\n") + 1,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "includes": detect_includes(text),
            "symbols": detect_symbols(text),
            "text": text,
        })
    return rows


def lexer_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
        ".s": "asm", ".asm": "nasm", ".ld": "ld",
        ".py": "python", ".sh": "bash", ".bat": "batch", ".ps1": "powershell",
        ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
        ".ini": "ini", ".cfg": "ini",
        ".vert": "glsl", ".frag": "glsl", ".glsl": "glsl",
    }.get(suffix, "text")


def fence_for(text: str) -> str:
    longest = max((len(m.group(0)) for m in re.finditer(r"`+", text)), default=0)
    return "`" * max(4, longest + 1)


def generated_page(row: dict[str, object], rev: str, lang: str) -> str:
    pt = lang == "pt-br"
    path = str(row["path"])
    title = ("Referência de fonte: " if pt else "Source reference: ") + path
    tick = "`"

    includes = row["includes"]
    symbols = row["symbols"]
    include_lines = [
        "| Line | Include |" if not pt else "| Linha | Include |",
        "|---:|---|",
    ]
    if includes:
        for item in includes:
            include_lines.append(f"| {item['line']} | {tick}{item['name']}{tick} |")
    else:
        include_lines.append(
            "| — | No preprocessor include detected. |"
            if not pt else "| — | Nenhum include de preprocessor detectado. |"
        )

    symbol_lines = [
        "| Line | Symbol |" if not pt else "| Linha | Símbolo |",
        "|---:|---|",
    ]
    if symbols:
        for item in symbols:
            symbol_lines.append(f"| {item['line']} | {tick}{item['name']}{tick} |")
    else:
        symbol_lines.append(
            "| — | No C-like function definition detected by the scanner. |"
            if not pt else "| — | Nenhuma definição de função no formato C detectada pelo scanner. |"
        )

    source = str(row["text"])
    fence = fence_for(source)
    lexer = lexer_for(path)

    return f"""---
id: source-{row['sha256'][:16]}
lang: {lang}
type: generated-source-reference
status: generated
reviewed_revision: {rev}
sources:
  - {path}
---

# {title}

> {"Registro determinístico da fonte. O conteúdo completo do arquivo é reproduzido abaixo; esta página não substitui a interpretação arquitetural dos capítulos autorais." if pt else "Deterministic source record. The complete textual file is reproduced below; this page does not replace architectural interpretation in the authored chapters."}

## {"Identidade do arquivo" if pt else "File identity"}

| {"Campo" if pt else "Field"} | {"Valor" if pt else "Value"} |
|---|---|
| Path | {tick}{path}{tick} |
| Lines | {row['lines']} |
| Bytes | {row['bytes']} |
| SHA-256 | {tick}{row['sha256']}{tick} |
| ChrisOS revision | {tick}{rev}{tick} |

## {"Dependências sintáticas detectadas" if pt else "Detected syntactic dependencies"}

{chr(10).join(include_lines)}

## {"Símbolos detectados" if pt else "Detected symbols"}

{chr(10).join(symbol_lines)}

## {"Fonte completa" if pt else "Complete source"}

{"O bloco seguinte é o arquivo textual integral na revisão indicada. Não há elisão, abreviação ou paráfrase." if pt else "The following block is the complete textual file at the recorded revision. No lines are elided, abbreviated or paraphrased."}

{fence}{lexer} linenums="1"
{source}
{fence}

## {"Papel deste registro" if pt else "Role of this record"}

{"O atlas garante rastreabilidade arquivo-a-arquivo. Responsabilidade, invariantes, ownership, concorrência, segurança, desempenho e interação entre subsistemas pertencem aos capítulos autorais e devem citar este arquivo quando aplicável." if pt else "The atlas guarantees file-by-file traceability. Responsibility, invariants, ownership, concurrency, security, performance and subsystem interactions belong in authored chapters and must cite this file when applicable."}
"""


def inventory_page(rows: list[dict[str, object]], rev: str, lang: str) -> str:
    pt = lang == "pt-br"
    tick = "`"
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        path = str(row["path"])
        top = path.split("/", 1)[0]
        grouped.setdefault(top, []).append(row)

    lines = [
        "---",
        "id: generated-source-inventory",
        f"lang: {lang}",
        "type: generated-index",
        "status: generated",
        f"reviewed_revision: {rev}",
        "---",
        "",
        f"# {'Inventário integral de fonte textual' if pt else 'Complete textual source inventory'}",
        "",
        (
            "> Gerado diretamente da branch `main` do ChrisOS. Cada entrada abre uma página que contém o arquivo textual completo, hash, tamanho, includes e símbolos detectados."
            if pt else
            "> Generated directly from the ChrisOS `main` branch. Every entry opens a page containing the complete textual file, hash, size, detected includes and detected symbols."
        ),
        "",
        f"Revision: {tick}{rev}{tick}  ",
        f"{'Arquivos textuais indexados' if pt else 'Text files indexed'}: **{len(rows)}**",
        "",
    ]

    for top in sorted(grouped):
        subset = grouped[top]
        lines.extend([
            f"## {top}",
            "",
            f"{'Arquivos' if pt else 'Files'}: **{len(subset)}**",
            "",
            f"| {'Arquivo' if pt else 'File'} | {'Linhas' if pt else 'Lines'} | Bytes | SHA-256 |",
            "|---|---:|---:|---|",
        ])
        for row in subset:
            rel = "generated/" + str(row["path"]) + ".md"
            lines.append(
                f"| [{row['path']}]({rel}) | {row['lines']} | {row['bytes']} | "
                f"{tick}{str(row['sha256'])[:16]}…{tick} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()

    source = Path(args.source)
    docs = Path(args.docs)
    rev = git(source, "rev-parse", "HEAD")
    rows = scan(source)

    for lang in ("en", "pt-br"):
        root = docs / lang / "99-source-atlas" / "generated"
        root.mkdir(parents=True, exist_ok=True)
        for old in root.rglob("*.md"):
            old.unlink()

        for row in rows:
            target = root / (str(row["path"]) + ".md")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(generated_page(row, rev, lang), encoding="utf-8")

        index = docs / lang / "99-source-atlas" / "inventory.md"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(inventory_page(rows, rev, lang), encoding="utf-8")

    print(f"indexed {len(rows)} complete textual source files at {rev}")


if __name__ == "__main__":
    main()
