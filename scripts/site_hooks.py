"""MkDocs hook: curriculum-driven navigation, language pairs and source provenance."""
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).parent))
from curriculum import load_catalog
from frontmatter import iter_pages, read_page

PAGES = {}
PAGE_META = {}
PLANNED = {}
CURRICULUM_CONTEXT = {}
CURRICULUM_ORDER = []


def _url_for(rel):
    path = rel[:-3]
    return path[:-5] if path.endswith('index') else path + '/'


def on_config(config):
    global PAGES, PAGE_META, PLANNED, CURRICULUM_CONTEXT, CURRICULUM_ORDER
    docs = Path(config['docs_dir'])
    extra = dict(config.get('extra') or {})
    extra['build_version'] = os.environ.get('GITHUB_SHA', 'dev')[:12]
    config['extra'] = extra
    curriculum, planned, chapters = load_catalog(docs)
    PLANNED = planned
    PAGES = {}
    PAGE_META = {}
    for path in iter_pages(docs):
        meta, body = read_page(path)
        if meta.get('id') and meta.get('lang'):
            rel = path.relative_to(docs).as_posix()
            title = next((line[2:] for line in body.splitlines() if line.startswith('# ')), meta['id'])
            key = (meta['id'], meta['lang'])
            PAGES[key] = (rel, title)
            PAGE_META[key] = meta

    CURRICULUM_ORDER = []
    CURRICULUM_CONTEXT = {}
    for level in curriculum['levels']:
        for module in level['modules']:
            for pid in module['chapters']:
                CURRICULUM_CONTEXT[pid] = {
                    'level': level['title'],
                    'module': module['title'],
                }
                CURRICULUM_ORDER.append(pid)

    nav = []
    for lang, label in [('en', 'English'), ('pt-br', 'Português')]:
        items = [
            {'ChrisOS': f'{lang}/index.md'},
            {'Percurso de aprendizado' if lang == 'pt-br' else 'Learning path': f'{lang}/learning-path.md'},
        ]
        used = {f'{lang}/index.md', f'{lang}/learning-path.md'}
        for level in curriculum['levels']:
            modules = []
            for module in level['modules']:
                entries = []
                for pid in module['chapters']:
                    page = chapters.get((pid, lang))
                    if page:
                        rel = page['path'].relative_to(docs).as_posix()
                        used.add(rel)
                        entries.append({page['title']: rel})
                if entries:
                    modules.append({module['title'][lang]: entries})
            if modules:
                items.append({level['title'][lang]: modules})
        reference = []
        for (pid, plang), (rel, title) in sorted(PAGES.items()):
            if plang == lang and rel not in used:
                reference.append({title: rel})
        items.append({'Índices e auditoria' if lang == 'pt-br' else 'Indexes and audit': reference})
        nav.append({label: items})
    config['nav'] = nav
    return config


def on_page_markdown(markdown, page, config, files):
    if '/99-source-atlas/generated/' in page.file.src_uri:
        page.meta['search'] = {'exclude': True}
    return markdown


def on_page_context(context, page, config, nav):
    lang = page.meta.get('lang', 'en')
    other = 'pt-br' if lang == 'en' else 'en'

    def entry(pid, language=lang):
        if not pid:
            return None
        pair = PAGES.get((pid, language))
        if pair:
            return {
                'id': pid,
                'title': pair[1],
                'url': _url_for(pair[0]),
                'missing': False,
            }
        planned = PLANNED.get(pid, {})
        return {
            'id': pid,
            'title': planned.get('title', pid),
            'url': None,
            'missing': True,
        }

    pid = page.meta.get('id')
    context['translation'] = entry(pid, other) or {'url': None}
    context['prerequisites'] = [entry(dep) for dep in page.meta.get('depends_on', [])]

    dependents = []
    if pid:
        for (other_pid, other_lang), meta in PAGE_META.items():
            if other_lang == lang and pid in (meta.get('depends_on') or []):
                dependents.append(entry(other_pid))
    context['dependents'] = [item for item in dependents if item]

    curriculum = None
    if pid in CURRICULUM_CONTEXT:
        idx = CURRICULUM_ORDER.index(pid)
        meta = CURRICULUM_CONTEXT[pid]
        curriculum = {
            'level': meta['level'][lang],
            'module': meta['module'][lang],
            'position': idx + 1,
            'total': len(CURRICULUM_ORDER),
            'previous': entry(CURRICULUM_ORDER[idx - 1]) if idx > 0 else None,
            'next': entry(CURRICULUM_ORDER[idx + 1]) if idx + 1 < len(CURRICULUM_ORDER) else None,
        }
    context['curriculum_context'] = curriculum
    return context


from mkdocs.plugins import event_priority
import json


@event_priority(-100)
def on_post_build(config):
    # MkDocs Core search does not implement Material's search.exclude metadata.
    # Filter the generated public JSON instead of relying on that unsupported key.
    target = Path(config['site_dir']) / 'search/search_index.json'
    data = json.loads(target.read_text())
    data['docs'] = [d for d in data['docs'] if '/99-source-atlas/generated/' not in d['location']]
    target.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False))
    for lang in ('en', 'pt-br'):
        language_docs = [d for d in data['docs'] if d['location'].startswith(lang + '/')]
        page_titles = {
            d['location']: d.get('title', d['location'])
            for d in language_docs
            if '#' not in d['location']
        }
        reader_docs = []
        for doc in language_docs:
            location = doc['location']
            base_location = location.split('#', 1)[0]
            kind = 'section' if '#' in location else 'page'
            text = ' '.join(str(doc.get('text', '')).split())
            # Page records duplicate their section corpus. Keep only a compact
            # page-level lead and a bounded section body so the direct client-side
            # search index remains usable on mobile as the 214-chapter corpus grows.
            # Section titles and anchor locations remain indexed independently.
            text_limit = 400 if kind == 'page' else 2000
            reader_docs.append({
                'location': location,
                'title': doc.get('title', location),
                'page_title': page_titles.get(base_location, doc.get('title', location)),
                'kind': kind,
                'text': text[:text_limit],
            })
        payload = {'schema_version': 1, 'language': lang, 'docs': reader_docs}
        (target.parent / f'reader-{lang}.json').write_text(
            json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        )
