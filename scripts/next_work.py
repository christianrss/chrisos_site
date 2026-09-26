#!/usr/bin/env python3
"""Choose useful work in curriculum order, including existing thin chapters."""
from pathlib import Path
import argparse
from curriculum import load_catalog
from coverage import DEPTH_TARGET_WORDS, DEFAULT_TARGET_WORDS

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--docs',default='docs');ap.add_argument('--volume')
    ap.add_argument('--lang',choices=['en','pt-br'],default='en')
    ap.add_argument('--limit',type=int,default=12)
    args=ap.parse_args()
    curriculum,planned,pages=load_catalog(Path(args.docs))
    rows=[]
    for level in curriculum['levels']:
        for module in level['modules']:
            for pid in module['chapters']:
                if args.volume and planned[pid]['volume']!=args.volume: continue
                page=pages.get((pid,args.lang))
                target=DEPTH_TARGET_WORDS.get((page or {}).get('type'),DEFAULT_TARGET_WORDS)
                if not page or page['words']<target:
                    state='missing' if not page else f'expand ({page["words"]}/{target} words; length signal only)'
                    blocked=[p for p in (page or {}).get('depends_on',[]) if (p,args.lang) not in pages]
                    rows.append(f'{level["id"]} / {pid}: {state}'+(f'; missing prerequisites={blocked}' if blocked else ''))
    print('\n'.join(rows[:args.limit])); print(f'remaining={len(rows)}')

if __name__=='__main__': main()
