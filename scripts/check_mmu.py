#!/usr/bin/env python3
"""Verify source-bound translation contracts and explicitly retain known gaps."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default='.source')
    parser.add_argument('--cc',default='cc')
    args=parser.parse_args()
    root=Path(args.source).resolve()/'chrisvm'
    source=root/'cpu/emulator/mmu.c'
    fixture=Path(__file__).resolve().parents[1]/'tests/source/mmu_contract.c'
    with tempfile.TemporaryDirectory(prefix='chris-mmu-') as tmp:
        executable=Path(tmp)/'mmu-probe'
        subprocess.run([args.cc,'-std=c11','-Wall','-Wextra','-Werror','-O2',f'-I{root}',str(fixture),str(source),'-o',str(executable)],check=True)
        subprocess.run([str(executable)],check=True)
    print('mmu.c SHA-256:',hashlib.sha256(source.read_bytes()).hexdigest())
    print('Scope: synthetic physical memory, stubbed exception delivery; no guest boot or hardware test.')

if __name__=='__main__':
    main()
