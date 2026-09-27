#!/usr/bin/env python3
"""Validate the learning DAG and emit a bilingual, honest reading catalogue."""
from pathlib import Path
import argparse
import json
import os
import yaml
from frontmatter import iter_pages, read_page
from coverage import word_count, DEPTH_TARGET_WORDS, DEFAULT_TARGET_WORDS


def load_catalog(docs):
    manifest = yaml.safe_load(Path('data/documentation-manifest.yml').read_text())
    curriculum = yaml.safe_load(Path('data/curriculum.yml').read_text())
    planned = {c['id']: dict(c, volume=v) for v, data in manifest['volumes'].items() for c in data['chapters']}
    pages = {}
    for path in iter_pages(docs):
        meta, body = read_page(path)
        if meta.get('id') in planned:
            pages[(meta['id'], meta['lang'])] = dict(meta, path=path, title=next((s[2:] for s in body.splitlines() if s.startswith('# ')), meta['id']), words=word_count(body))
    seen = []
    for level in curriculum['levels']:
        for module in level['modules']:
            seen.extend(module['chapters'])
    if len(set(seen)) != len(seen) or set(seen) != set(planned):
        raise ValueError(f'Curriculum must partition manifest exactly; missing={set(planned)-set(seen)}, unknown={set(seen)-set(planned)} or duplicate IDs')
    for lang in ('en', 'pt-br'):
        visiting, visited = set(), set()
        def visit(pid):
            if pid in visiting:
                raise ValueError(f'Prerequisite cycle ({lang}): {pid}')
            if pid in visited:
                return
            visiting.add(pid)
            for dependency in pages.get((pid, lang), {}).get('depends_on', []):
                if dependency not in planned:
                    raise ValueError(f'{pid}: unknown prerequisite {dependency}')
                visit(dependency)
            visiting.remove(pid)
            visited.add(pid)
        for pid in planned:
            visit(pid)
    return curriculum, planned, pages


def state(page, lang):
    pt = lang == 'pt-br'
    if not page:
        return 'Ausente' if pt else 'Missing'
    floor = DEPTH_TARGET_WORDS.get(page.get('type'), DEFAULT_TARGET_WORDS)
    if page['words'] < floor:
        return 'Requer expansão' if pt else 'Needs expansion'
    return 'Piso textual atingido; revisão técnica necessária' if pt else 'Text floor met; technical review required'


def generate(docs):
    curriculum, planned, pages = load_catalog(docs)
    order = [
        pid
        for level in curriculum['levels']
        for module in level['modules']
        for pid in module['chapters']
    ]
    positions = {pid: index for index, pid in enumerate(order)}
    record = {'schema_version': 1, 'levels': curriculum['levels'], 'order': order, 'chapters': {}}
    for lang in ('en', 'pt-br'):
        target = docs / lang / 'learning-path.md'
        pt = lang == 'pt-br'
        lines = ['---', 'id: learning-path', f'lang: {lang}', 'type: generated-index', 'status: generated', '---', '',
                 '# ' + ('Percurso de aprendizado e pré-requisitos' if pt else 'Learning path and prerequisites'), '',
                 ('A sequência organiza o corpus em níveis, módulos e capítulos. Uma entrada ausente representa uma lacuna explícita; não é um capítulo publicado. A quantidade de palavras é apenas um sinal editorial, não comprovação de domínio ou de completude técnica.' if pt else 'The sequence organizes the corpus into levels, modules and chapters. A missing entry is an explicit gap, not a published chapter. Word count is only an editorial signal, not evidence of mastery or technical completeness.'), '',
                 '![Mapa do percurso](../assets/diagrams/learning-map.svg)' if pt else '![Learning map](../assets/diagrams/learning-map.svg)', '']
        for level in curriculum['levels']:
            lines += ['## ' + level['title'][lang], '']
            for module in level['modules']:
                lines += [
                    '### '+module['title'][lang],
                    '',
                    '| '+('Nº | Capítulo | Estado | Pré-requisitos | Anterior na sequência' if pt else 'No. | Chapter | State | Prerequisites | Previous in sequence')+' |',
                    '|---:|---|---|---|---|'
                ]
                for pid in module['chapters']:
                    p = pages.get((pid, lang))
                    title = p['title'] if p else planned[pid]['title']
                    link = f'[{title}]({os.path.relpath(p["path"], target.parent)})' if p else f'{title} (`{pid}`)'
                    deps=[]
                    for dep in (p or {}).get('depends_on', []):
                        dp=pages.get((dep, lang))
                        deps.append(f'[{dp["title"]}]({os.path.relpath(dp["path"],target.parent)})' if dp else f'`{dep}` — '+('ausente' if pt else 'missing'))
                    index = positions[pid]
                    previous_id = order[index - 1] if index > 0 else None
                    next_id = order[index + 1] if index + 1 < len(order) else None
                    previous = '—'
                    if previous_id:
                        previous_page = pages.get((previous_id, lang))
                        if previous_page:
                            previous = f'[{previous_page["title"]}]({os.path.relpath(previous_page["path"], target.parent)})'
                        else:
                            previous = f'`{previous_id}` — '+('ausente' if pt else 'missing')
                    lines.append(f'| {index + 1} | {link} | {state(p,lang)} | {"; ".join(deps) or "—"} | {previous} |')
                    record['chapters'].setdefault(pid, {})[lang]={
                        'path':p['path'].relative_to(docs).as_posix() if p else None,
                        'state':state(p,lang),
                        'depends_on':(p or {}).get('depends_on',[]),
                        'level':level['id'],
                        'module':module['title'][lang],
                        'position':index + 1,
                        'previous_id':previous_id,
                        'next_id':next_id,
                    }
                lines.append('')
        target.write_text('\n'.join(lines)+'\n')
    out=docs/'generated-meta/curriculum.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(f'curriculum: {len(curriculum["levels"])} levels; {len(planned)} chapters; DAG validated')

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--docs',default='docs')
    generate(Path(ap.parse_args().docs))
