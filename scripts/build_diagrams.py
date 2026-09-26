#!/usr/bin/env python3
from pathlib import Path
import argparse, shutil, subprocess

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="diagrams/src")
    ap.add_argument("--out", default="docs/assets/diagrams")
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dot = shutil.which("dot")
    if not dot:
        raise SystemExit("Graphviz 'dot' is required")
    for p in sorted(src.glob("*.dot")):
        target = out / (p.stem + ".svg")
        subprocess.run([dot, "-Tsvg", str(p), "-o", str(target)], check=True)
        print(f"diagram {p} -> {target}")

if __name__ == "__main__":
    main()
