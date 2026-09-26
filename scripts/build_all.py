#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()

    py = sys.executable
    commands = [
        [py, "-m", "unittest", "discover", "-s", "tests"],
        [py, "scripts/build_diagrams.py"],
        [py, "scripts/build_figures.py"],
        [py, "scripts/inventory.py", "--source", args.source, "--docs", args.docs],
        [py, "scripts/coverage.py", "--docs", args.docs],
        [py, "scripts/curriculum.py", "--docs", args.docs],
        [py, "scripts/stale_docs.py", "--source", args.source, "--docs", args.docs],
        [py, "scripts/validate_docs.py", "--source", args.source, "--docs", args.docs],
        [py, "scripts/source_map.py", "--docs", args.docs],
    ]

    for command in commands:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
