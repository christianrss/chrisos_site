#!/usr/bin/env python3
import argparse
import subprocess
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--docs", default="docs")
    args = ap.parse_args()

    py = sys.executable
    commands = [
        [py, "scripts/build_diagrams.py"],
        [py, "scripts/inventory.py", "--source", args.source, "--docs", args.docs],
        [py, "scripts/source_map.py", "--docs", args.docs],
        [py, "scripts/coverage.py", "--docs", args.docs],
        [py, "scripts/stale_docs.py", "--source", args.source, "--docs", args.docs],
        [py, "scripts/validate_docs.py", "--source", args.source, "--docs", args.docs],
    ]
    for cmd in commands:
        subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
