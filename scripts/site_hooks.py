"""MkDocs hook: curriculum-driven navigation, language pairs and source provenance."""
from pathlib import Path
from urllib.parse import urljoin
import html
import json
import os
import re
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

    site_url = config.get('site_url') or ''
    canonical_url = urljoin(site_url, page.url)
    translation_entry = context.get('translation') or {}
    alternate_url = urljoin(site_url, translation_entry['url']) if translation_entry.get('url') else None

    explicit_description = str(page.meta.get('description') or '').strip()
    if explicit_description:
        description = explicit_description
    else:
        rendered = page.content or ''
        rendered = re.sub(r'<(script|style)\\b[^>]*>.*?</\\1>', ' ', rendered, flags=re.I | re.S)
        rendered = re.sub(r'<[^>]+>', ' ', rendered)
        rendered = html.unescape(rendered)
        rendered = ' '.join(rendered.split())
        title = (page.title or '').strip()
        if title and rendered.lower().startswith(title.lower()):
            rendered = rendered[len(title):].lstrip(' .:-—')
        description = rendered[:320].strip()
        if len(description) > 160:
            description = description[:157].rsplit(' ', 1)[0] + '…'
        if not description:
            description = config.get('site_description', '')

    schema_type = 'TechArticle'
    if page.meta.get('type') in {'landing', 'generated-root', 'index', 'catalog'}:
        schema_type = 'CollectionPage'

    in_language = 'pt-BR' if lang == 'pt-br' else 'en'
    context['seo'] = {
        'canonical_url': canonical_url,
        'alternate_url': alternate_url,
        'alternate_lang': 'en' if lang == 'pt-br' else 'pt-BR',
        'x_default_url': (alternate_url if lang == 'pt-br' and alternate_url else canonical_url if lang == 'en' else urljoin(site_url, 'en/')),
        'description': description,
        'image_url': urljoin(site_url, 'assets/images/ChrisOS_Monolito.png'),
        'in_language': in_language,
        'schema_json': json.dumps({
            '@context': 'https://schema.org',
            '@type': schema_type,
            'headline': page.title,
            'description': description,
            'url': canonical_url,
            'inLanguage': in_language,
            'author': {
                '@type': 'Person',
                'name': 'Christian Rafael de Souza Silva',
                'url': 'https://github.com/christianrss',
            },
            'publisher': {
                '@type': 'Person',
                'name': 'Christian Rafael de Souza Silva',
                'url': 'https://github.com/christianrss',
            },
            'isPartOf': {
                '@type': 'WebSite',
                'name': 'ChrisOS — Operating System & Systems Research',
                'url': site_url,
            },
            'about': {
                '@type': 'SoftwareSourceCode',
                'name': 'ChrisOS',
                'codeRepository': 'https://github.com/christianrss/ChrisOS',
                'programmingLanguage': ['C', 'Assembly', 'ChrisC'],
                'runtimePlatform': 'x86-64',
            },
        }, ensure_ascii=False, separators=(',', ':')),
    }
    return context


from mkdocs.plugins import event_priority


@event_priority(-100)
def on_post_build(config):
    # MkDocs Core search does not implement Material's search.exclude metadata.
    # Filter the generated public JSON instead of relying on that unsupported key.
    target = Path(config['site_dir']) / 'search/search_index.json'
    data = json.loads(target.read_text())
    data['docs'] = [d for d in data['docs'] if '/99-source-atlas/generated/' not in d['location']]
    target.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False))
    site_dir = Path(config['site_dir'])
    site_url = (config.get('site_url') or '').rstrip('/') + '/'

    robots = (
        "User-agent: *\\n"
        "Allow: /\\n\\n"
        f"Sitemap: {urljoin(site_url, 'sitemap.xml')}\\n"
    )
    (site_dir / 'robots.txt').write_text(robots, encoding='utf-8')

    llms_lines = [
        "# ChrisOS",
        "",
        "> ChrisOS is an experimental x86-64 operating-system and systems-research ecosystem covering kernel engineering, compilers, ChrisC/CLVM, filesystems, graphics, networking, emulation and virtualization.",
        "",
        "Canonical documentation: " + site_url,
        "Source repository: https://github.com/christianrss/ChrisOS",
        "Documentation repository: https://github.com/christianrss/chrisos_site",
        "",
        "## Primary documentation",
        f"- [English documentation]({urljoin(site_url, 'en/')})",
        f"- [Brazilian Portuguese documentation]({urljoin(site_url, 'pt-br/')})",
        f"- [English learning path]({urljoin(site_url, 'en/learning-path/')})",
        f"- [Percurso de aprendizado em português]({urljoin(site_url, 'pt-br/learning-path/')})",
        f"- [XML sitemap]({urljoin(site_url, 'sitemap.xml')})",
        "",
        "## Scope",
        "- Physical foundations, electronics, digital logic and computer architecture",
        "- x86-64 boot, kernel, memory, interrupts, processes and concurrency",
        "- ChrisC, CLVM, compiler/toolchain design and self-hosting",
        "- Storage, ChrisFS, graphics, desktop, networking and drivers",
        "- ChrisVM, ChrisCPU, emulation, virtualization and hardware bring-up",
        "- Revision-bound validation, specifications and architecture history",
        "",
        "## Machine-readable corpus",
        f"- [Expanded LLM corpus]({urljoin(site_url, 'llms-full.txt')})",
        "",
        "Prefer canonical documentation pages for citations. Implementation claims are revision-bound to the ChrisOS source revision recorded on each page.",
        "",
    ]
    (site_dir / 'llms.txt').write_text('\\n'.join(llms_lines), encoding='utf-8')

    full_lines = llms_lines + ["# Documentation corpus", ""]
    docs_dir = Path(config['docs_dir'])
    for source_path in sorted(iter_pages(docs_dir)):
        rel = source_path.relative_to(docs_dir).as_posix()
        if '/99-source-atlas/generated/' in rel:
            continue
        meta, body = read_page(source_path)
        language = meta.get('lang', '')
        if language not in {'en', 'pt-br'}:
            continue
        public_url = urljoin(site_url, _url_for(rel))
        full_lines.extend([
            "",
            "---",
            f"Source: {public_url}",
            f"Language: {'pt-BR' if language == 'pt-br' else 'en'}",
            f"Document-ID: {meta.get('id', '')}",
            "",
            body.strip(),
        ])
    (site_dir / 'llms-full.txt').write_text('\\n'.join(full_lines) + '\\n', encoding='utf-8')

    for lang in ('en', 'pt-br'):
        language_docs = [d for d in data['docs'] if d['location'].startswith(lang + '/')]
        page_titles = {
            d['location']: d.get('title', d['location'])
            for d in language_docs
            if '#' not in d['location']
        }
        raw_reader_docs = []
        for doc in language_docs:
            location = doc['location']
            base_location = location.split('#', 1)[0]
            kind = 'section' if '#' in location else 'page'
            raw_reader_docs.append({
                'location': location,
                'title': doc.get('title', location),
                'page_title': page_titles.get(base_location, doc.get('title', location)),
                'kind': kind,
                'text': ' '.join(str(doc.get('text', '')).split()),
            })

        # Page records duplicate their section corpus. Keep page leads compact and
        # adapt the section excerpt budget to corpus growth. The reader performs
        # direct client-side JSON search, so unbounded per-section text eventually
        # turns a complete 214-chapter corpus into a multi-megabyte mobile payload.
        # Preserve every section title/location and shrink only body excerpts.
        page_text_limit = 160
        section_text_limit = 800
        min_page_text_limit = 80
        min_section_text_limit = 80
        target_bytes = 1_700_000

        while True:
            reader_docs = []
            for doc in raw_reader_docs:
                text_limit = page_text_limit if doc['kind'] == 'page' else section_text_limit
                reader_docs.append({
                    'location': doc['location'],
                    'title': doc['title'],
                    'page_title': doc['page_title'],
                    'kind': doc['kind'],
                    'text': doc['text'][:text_limit],
                })
            payload = {'schema_version': 1, 'language': lang, 'docs': reader_docs}
            encoded = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
            if len(encoded.encode('utf-8')) <= target_bytes:
                break
            if section_text_limit > min_section_text_limit:
                section_text_limit = max(
                    min_section_text_limit,
                    int(section_text_limit * 0.80),
                )
                continue
            if page_text_limit > min_page_text_limit:
                page_text_limit = max(
                    min_page_text_limit,
                    int(page_text_limit * 0.80),
                )
                continue
            # At the minimum excerpt budget, keep all section/page records.
            # The smoke test will still fail if record metadata alone eventually
            # exceeds the payload contract, making that future scaling boundary
            # explicit rather than silently dropping searchable sections.
            break

        (target.parent / f'reader-{lang}.json').write_text(encoded)
