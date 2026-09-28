#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="site")
    args = parser.parse_args()
    site = Path(args.site)

    for name in ("robots.txt", "llms.txt", "llms-full.txt", "sitemap.xml"):
        path = site / name
        require(path.is_file(), f"missing discovery artifact: {name}")
        require(path.stat().st_size > 0, f"empty discovery artifact: {name}")

    robots = (site / "robots.txt").read_text(encoding="utf-8")
    require("Sitemap:" in robots, "robots.txt must advertise sitemap.xml")
    require("Allow: /" in robots, "robots.txt must allow public documentation")

    llms = (site / "llms.txt").read_text(encoding="utf-8")
    require("# ChrisOS" in llms, "llms.txt must identify ChrisOS")
    require("Operating-system" in llms or "operating-system" in llms, "llms.txt must disambiguate ChrisOS as an operating-system project")
    require("github.com/christianrss/ChrisOS" in llms, "llms.txt must link the source repository")
    require("llms-full.txt" in llms, "llms.txt must link the expanded corpus")

    pages = [site / "en" / "index.html", site / "pt-br" / "index.html"]
    for page in pages:
        require(page.is_file(), f"missing landing page: {page}")
        html = page.read_text(encoding="utf-8")
        require('rel="canonical"' in html, f"missing canonical link in {page}")
        require('hreflang="x-default"' in html, f"missing x-default alternate in {page}")
        require('property="og:title"' in html, f"missing Open Graph title in {page}")
        require('name="twitter:card"' in html, f"missing Twitter card in {page}")
        require('application/ld+json' in html, f"missing JSON-LD in {page}")
        require(re.search(r'<meta name="description" content="[^"]{50,}">', html), f"description too short or absent in {page}")

    full = (site / "llms-full.txt").read_text(encoding="utf-8")
    require(full.count("Document-ID:") >= 2, "llms-full.txt must contain authored corpus records")

    print("Discovery/SEO smoke checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"SEO/discovery check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
