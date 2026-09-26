# ChrisOS Documentation Site

Official, bilingual documentation for the ChrisOS ecosystem.

## Design

The site intentionally uses a strong late-80s/90s workstation/desktop visual language while keeping a modern responsive layout underneath:

- official `ChrisOS_Monolito.png` identity;
- CRT/terminal texture, hard bevels, pixel-like treatment and system panels;
- responsive navigation provided by MkDocs Material;
- mobile-safe tables and code blocks;
- no JavaScript framework;
- all documentation content is Markdown.

## Source

- OS: https://github.com/christianrss/ChrisOS
- Documentation: this repository
- Baseline at migration: `main @ da3df29`

## Local development

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
mkdocs serve
```

## Production build

```bash
mkdocs build --strict
```

## GitHub Pages

Every push to `main` triggers `.github/workflows/pages.yml`.

Expected URL:

```text
https://christianrss.github.io/chrisos_site/
```
