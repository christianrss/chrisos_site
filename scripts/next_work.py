#!/usr/bin/env python3
from pathlib import Path
import argparse, yaml
from frontmatter import iter_pages, read_page

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--docs",default="docs")
    ap.add_argument("--manifest",default="data/documentation-manifest.yml")
    ap.add_argument("--volume")
    ap.add_argument("--limit",type=int,default=12)
    args=ap.parse_args()
    docs=Path(args.docs)
    existing={read_page(p)[0].get("id") for p in iter_pages(docs)}
    data=yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    rows=[]
    for volume,v in data["volumes"].items():
        if args.volume and volume!=args.volume:
            continue
        for ch in v.get("chapters",[]):
            if ch["id"] not in existing:
                score=0 if ch.get("priority")=="foundation" else 1
                rows.append((score,volume,ch["id"],ch["title"],ch.get("priority","expansion")))
    rows.sort()
    for _,vol,pid,title,priority in rows[:args.limit]:
        print(f"{vol}/{pid} [{priority}] — {title}")
    print(f"remaining={len(rows)}")

if __name__=="__main__":
    main()
