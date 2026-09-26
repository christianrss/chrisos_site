# ChrisOS Documentation Site

Official documentation site for the ChrisOS ecosystem.

- Source OS repository: https://github.com/christianrss/ChrisOS
- Documentation source: Markdown under `docs/`
- Languages: English and Brazilian Portuguese
- Deployment: GitHub Actions + GitHub Pages

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
mkdocs serve
```

## Build

```bash
mkdocs build --strict
```

The generated site is written to `site/` and is deployed by `.github/workflows/pages.yml`.
