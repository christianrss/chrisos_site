"""Coverage must not hide prose containing mathematical comparisons."""
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("docs_coverage", SCRIPTS / "coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class CoverageTests(unittest.TestCase):
    def test_comparisons_do_not_eat_later_prose(self):
        text = 'keys(left) < key(node) < keys(right)\n\nparent <= children.\n\n<code>main</code>'
        self.assertEqual(coverage.word_count(text), 9)

    def test_html_attributes_do_not_count_as_prose(self):
        self.assertEqual(coverage.word_count('<div class="abstract">estado <code>main</code></div>'), 2)

    def test_comments_and_fenced_code_are_excluded(self):
        self.assertEqual(coverage.word_count('prose\n<!-- hidden words -->\n```c\nint value;\n```'), 1)


if __name__ == "__main__":
    unittest.main()
