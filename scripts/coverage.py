#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import re
import yaml

from frontmatter import iter_pages, read_page

DEPTH_TARGET_WORDS = {
    "concept": 1800,
    "subsystem": 2200,
    "specification": 1600,
    "source-commentary": 1200,
}
DEFAULT_TARGET_WORDS = 900
WORD_RE = re.compile(r"\b[\wÀ-ÿ][\wÀ-ÿ'’-]*\b", re.UNICODE)


def word_count(body: str) -> int:
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return len(WORD_RE.findall(body))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="docs")
    parser.add_argument("--manifest", default="data/documentation-manifest.yml")
    args = parser.parse_args()

    docs = Path(args.docs)
    manifest = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))

    pages: dict[tuple[str, str], dict[str, object]] = {}
    for path in iter_pages(docs):
        meta, body = read_page(path)
        pid = meta.get("id")
        lang = meta.get("lang")
        typ = str(meta.get("type", ""))
        if not pid or not lang or typ.startswith("generated") or typ in {"volume-index", "landing"}:
            continue
        words = word_count(body)
        target = DEPTH_TARGET_WORDS.get(typ, DEFAULT_TARGET_WORDS)
        pages[(str(pid), str(lang))] = {
            "path": path,
            "type": typ,
            "words": words,
            "target": target,
            "deep": words >= target,
        }

    planned = []
    for volume, volume_data in manifest["volumes"].items():
        for chapter in volume_data.get("chapters", []):
            planned.append((
                volume,
                chapter["id"],
                chapter["title"],
                chapter.get("priority", "expansion"),
            ))

    for lang in ("en", "pt-br"):
        pt = lang == "pt-br"
        present = []
        missing = []
        thin = []
        deep = []

        for volume, pid, title, priority in planned:
            page = pages.get((pid, lang))
            if page is None:
                missing.append((volume, pid, title, priority))
                continue
            present.append((volume, pid, title, priority, page))
            if page["deep"]:
                deep.append((volume, pid, title, priority, page))
            else:
                thin.append((volume, pid, title, priority, page))

        structural_pct = 100.0 * len(present) / len(planned) if planned else 100.0
        depth_pct = 100.0 * len(deep) / len(planned) if planned else 100.0

        target = docs / lang / "98-maintenance" / "coverage.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "---",
            "id: documentation-coverage",
            f"lang: {lang}",
            "type: generated-status",
            "status: generated",
            "---",
            "",
            f"# {'Cobertura e profundidade do corpus' if pt else 'Corpus coverage and depth'}",
            "",
            (
                "Esta página não usa a mera existência de um arquivo como sinônimo de conclusão. "
                "Um capítulo é contado como profundo apenas quando atinge o piso editorial de palavras para seu tipo."
                if pt else
                "This page does not treat the mere existence of a file as completion. "
                "A chapter counts as deep only when it reaches the editorial word floor for its page type."
            ),
            "",
            f"{'Capítulos planejados' if pt else 'Planned chapters'}: **{len(planned)}**  ",
            f"{'Arquivos autorais presentes' if pt else 'Authored files present'}: **{len(present)}**  ",
            f"{'Capítulos ausentes' if pt else 'Missing chapters'}: **{len(missing)}**  ",
            f"{'Presentes, porém abaixo da profundidade-alvo' if pt else 'Present but below depth target'}: **{len(thin)}**  ",
            f"{'Capítulos que atingem a profundidade-alvo' if pt else 'Chapters meeting depth target'}: **{len(deep)}**  ",
            f"{'Cobertura estrutural' if pt else 'Structural coverage'}: **{structural_pct:.1f}%**  ",
            f"{'Cobertura profunda' if pt else 'Deep coverage'}: **{depth_pct:.1f}%**",
            "",
            f"## {'Pisos editoriais' if pt else 'Editorial depth floors'}",
            "",
            "| Type | Minimum words |",
            "|---|---:|",
        ]
        for typ, floor in sorted(DEPTH_TARGET_WORDS.items()):
            lines.append(f"| `{typ}` | {floor} |")
        lines.append(f"| other authored technical page | {DEFAULT_TARGET_WORDS} |")

        lines.extend([
            "",
            f"## {'Capítulos que precisam ser expandidos' if pt else 'Chapters requiring expansion'}",
            "",
            "| Volume | ID | Words | Target | Title |",
            "|---|---|---:|---:|---|",
        ])
        if thin:
            for volume, pid, title, priority, page in thin:
                lines.append(
                    f"| {volume} | `{pid}` | {page['words']} | {page['target']} | {title} |"
                )
        else:
            lines.append("| — | — | — | — | — |")

        lines.extend([
            "",
            f"## {'Capítulos ausentes' if pt else 'Missing chapters'}",
            "",
            "| Volume | ID | Priority | Title |",
            "|---|---|---|---|",
        ])
        if missing:
            for volume, pid, title, priority in missing:
                lines.append(f"| {volume} | `{pid}` | {priority} | {title} |")
        else:
            lines.append("| — | — | — | — |")

        lines.extend([
            "",
            f"## {'Capítulos profundos' if pt else 'Deep chapters'}",
            "",
            "| Volume | ID | Words | Title |",
            "|---|---|---:|---|",
        ])
        if deep:
            for volume, pid, title, priority, page in deep:
                lines.append(f"| {volume} | `{pid}` | {page['words']} | {title} |")
        else:
            lines.append("| — | — | — | — |")

        target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"coverage planned={len(planned)} authored_pairs={len(pages)}")


if __name__ == "__main__":
    main()
