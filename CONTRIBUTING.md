# Contributing to ChrisOS Documentation

The documentation is maintained as a research corpus.

Before editing implementation-specific text:

```bash
git -C .source fetch origin main
git -C .source checkout main
git -C .source pull --ff-only
python scripts/stale_docs.py --source .source --docs docs
```

Use `scripts/context_pack.py` for focused work. After editing:

```bash
python scripts/build_all.py --source .source --docs docs
mkdocs build --strict
```

Generated files are rebuilt in CI and must not be hand-authored. The preferred change unit is one concept, one subsystem, one specification, or one source family.
