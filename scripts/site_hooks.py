"""Small MkDocs hook: semantic navigation, language pairs and source provenance."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from curriculum import load_catalog
from frontmatter import iter_pages, read_page

PAGES = {}

def on_config(config):
    global PAGES
    docs=Path(config['docs_dir'])
    curriculum, planned, chapters = load_catalog(docs)
    PAGES={}
    for path in iter_pages(docs):
        meta, body=read_page(path)
        if meta.get('id') and meta.get('lang'):
            PAGES[(meta['id'],meta['lang'])]=(path.relative_to(docs).as_posix(), next((l[2:] for l in body.splitlines() if l.startswith('# ')), meta['id']))
    nav=[]
    for lang,label in [('en','English'),('pt-br','Português')]:
        items=[{'ChrisOS':f'{lang}/index.md'},{'Percurso de aprendizado' if lang=='pt-br' else 'Learning path': f'{lang}/learning-path.md'}]
        used={f'{lang}/index.md', f'{lang}/learning-path.md'}
        for level in curriculum['levels']:
            modules=[]
            for module in level['modules']:
                entries=[]
                for pid in module['chapters']:
                    p=chapters.get((pid,lang))
                    if p:
                        rel=p['path'].relative_to(docs).as_posix(); used.add(rel)
                        entries.append({p['title']:rel})
                if entries: modules.append({module['title'][lang]:entries})
            if modules: items.append({level['title'][lang]:modules})
        reference=[]
        for (pid,plang),(rel,title) in sorted(PAGES.items()):
            if plang==lang and rel not in used:
                reference.append({title:rel})
        items.append({'Índices e auditoria' if lang=='pt-br' else 'Indexes and audit':reference})
        nav.append({label:items})
    config['nav']=nav
    return config

def on_page_markdown(markdown, page, config, files):
    if '/99-source-atlas/generated/' in page.file.src_uri:
        page.meta['search']={'exclude':True}
    return markdown

def on_page_context(context, page, config, nav):
    lang=page.meta.get('lang','en'); other='pt-br' if lang=='en' else 'en'
    def entry(pid, language=lang):
        pair=PAGES.get((pid,language))
        if not pair: return {'title':pid,'url':None}
        # source paths map predictably under use_directory_urls, including index pages.
        path=pair[0][:-3]
        url=path[:-5] if path.endswith('index') else path+'/'
        return {'title':pair[1],'url':url}
    context['translation']=entry(page.meta.get('id'),other)
    context['prerequisites']=[entry(pid) for pid in page.meta.get('depends_on',[])]
    return context

from mkdocs.plugins import event_priority
import json

@event_priority(-100)
def on_post_build(config):
    # MkDocs Core search does not implement Material's search.exclude metadata.
    # Filter the generated public JSON instead of relying on that unsupported key.
    target=Path(config['site_dir'])/'search/search_index.json'
    data=json.loads(target.read_text())
    data['docs']=[d for d in data['docs'] if '/99-source-atlas/generated/' not in d['location']]
    target.write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False))
    for lang in ('en','pt-br'):
        payload={'docs':[d for d in data['docs'] if d['location'].startswith(lang+'/')]}
        (target.parent/f'{lang}.json').write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False))
