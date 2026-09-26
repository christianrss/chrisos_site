import contextlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from curriculum import load_catalog
from context_pack import symbol_extract

class CurriculumContracts(unittest.TestCase):
    @contextlib.contextmanager
    def corpus(self, ids=('a','b'), deps=None):
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                Path('data').mkdir()
                Path('data/documentation-manifest.yml').write_text(yaml.safe_dump({'volumes':{'v':{'chapters':[{'id':p,'title':p} for p in ['a','b']]}}}))
                Path('data/curriculum.yml').write_text(yaml.safe_dump({'levels':[{'id':'l','modules':[{'chapters':list(ids)}]}]}))
                for lang in ('en','pt-br'):
                    Path('docs',lang).mkdir(parents=True)
                    for pid in ('a','b'):
                        m={'id':pid,'lang':lang,'type':'concept','depends_on':(deps or {}).get(pid,[])}
                        Path('docs',lang,pid+'.md').write_text('---\n'+yaml.safe_dump(m)+'---\n# '+pid+'\n')
                yield Path('docs')
            finally: os.chdir(previous)

    def test_symbol_context_merges_overlapping_ranges(self):
        lines=[f"line_{i}" for i in range(400)]
        lines[150]="alpha();"; lines[160]="beta();"
        result=symbol_extract("\n".join(lines),["alpha","beta"])
        self.assertEqual(result.count("line_155"),1)
        self.assertIn("alpha();",result)
        self.assertIn("beta();",result)
        self.assertNotIn("line_399",result)

    def test_partition_and_acyclic_prerequisites(self):
        with self.corpus(deps={'b':['a']}) as docs:
            _,planned,pages=load_catalog(docs)
            self.assertEqual(len(planned),2)
            self.assertEqual(len(pages),4)

    def test_cycle_rejected(self):
        with self.corpus(deps={'a':['b'],'b':['a']}) as docs:
            with self.assertRaisesRegex(ValueError,'cycle'):load_catalog(docs)

    def test_unknown_prerequisite_rejected(self):
        with self.corpus(deps={'a':['unknown']}) as docs:
            with self.assertRaisesRegex(ValueError,'unknown prerequisite'):load_catalog(docs)

    def test_duplicate_or_missing_placement_rejected(self):
        for ids in [('a','a','b'),('a',)]:
            with self.corpus(ids=ids) as docs:
                with self.assertRaisesRegex(ValueError,'partition'):load_catalog(docs)

    def test_missing_planned_prerequisite_is_visible_not_cycle(self):
        with self.corpus(deps={'b':['a']}) as docs:
            for lang in ('en','pt-br'): (docs/lang/'a.md').unlink()
            _,planned,pages=load_catalog(docs)
            self.assertIn('a',planned)
            self.assertNotIn(('a','en'),pages)
            self.assertEqual(pages[('b','en')]['depends_on'],['a'])

if __name__=='__main__':unittest.main()
