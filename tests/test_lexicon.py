"""Lexicon test: the orthographic passes must leave the dictionaries alone.

Every headword and sub-entry of the 2009 imla dictionary [4] and the 2011
izahliq lughet [1] is already in the target orthography, so running passes
2-3 over them must change nothing. A change means one of two things:

  * the rule is wrong (it rewrites a real word: ئاستانە, رادىئۇس), or
  * the headword is an extraction error (the OCR model, trained on web
    Uyghur, wrote the web form the book does not print).

Only rows checked against the scan by hand ("verified") can tell these
apart, so only they fail the test. Hits on unverified rows are listed for
the headword audit; run  python tools/lexicon_review.py  for the full queue.

The calque pass is excluded on purpose: it replaces real, attested words
by editorial choice, so the dictionaries cannot validate it.

The snapshot is rebuilt with tools/build_lexicon_snapshot.py.
"""
import csv, gzip, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uyghur_normalizer import load_map, build_pattern, process_text, Report  # noqa: E402

MAP_DIR = os.path.join(ROOT, 'normalizer')
DATA = os.path.join(HERE, 'data')
ORTHO = ['era_map.tsv', 'imla_loan_map.tsv']   # pass order, calque excluded
USAGE = 'usage_map.tsv'                          # opt-in pass 0, tested with ORTHO


def tsv(path, opener=open):
    with opener(path, 'rt', encoding='utf-8') as fh:
        return list(csv.DictReader((l for l in fh if not l.startswith('#')),
                                   delimiter='\t', quoting=csv.QUOTE_NONE))


def ortho_passes():
    return [build_pattern(load_map(os.path.join(MAP_DIR, m), m, quiet=True)) for m in ORTHO]


def hits(rows, passes):
    """Rows whose form the pipeline changes, as (row, output, rules fired)."""
    out = []
    for r in rows:
        rep = Report()
        got = process_text(r['form'], passes, rep)
        if got != r['form']:
            out.append((r, got, sorted({f'{k[0]}->{k[1]}' for k in rep.hits})))
    return out


class TestLexicon(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.passes = ortho_passes()
        cls.lexicon = tsv(os.path.join(DATA, 'lexicon_snapshot.tsv.gz'), gzip.open)
        cls.exceptions = tsv(os.path.join(DATA, 'lexicon_exceptions.tsv'))
        cls.accepted = {e['form'] for e in cls.exceptions if e['kind'] == 'accepted'}

    def test_snapshot_loaded(self):
        self.assertGreater(len(self.lexicon), 100000)

    def test_exceptions_unchanged(self):
        for e in self.exceptions:
            with self.subTest(form=e['form']):
                self.assertEqual(process_text(e['form'], self.passes, Report()), e['form'],
                                 f"exception {e['form']} ({e['row_id']}) is rewritten")

    def test_verified_headwords_unchanged(self):
        rows = [r for r in self.lexicon
                if r['status'] == 'verified' and r['form'] not in self.accepted]
        bad = hits(rows, self.passes)
        msg = '\n'.join(f"  {r['form']} -> {got}  [{r['source']} {r['row_id']} {r['scan']}]  {', '.join(fired)}"
                        for r, got, fired in bad[:40])
        if bad:
            self.fail(f'{len(bad)} verified headword(s) rewritten:\n{msg}')

    def test_usage_pass_leaves_verified_headwords(self):
        """The usage pass corrects misuses; it must never rewrite a real word."""
        passes = [build_pattern(load_map(os.path.join(MAP_DIR, USAGE), USAGE, quiet=True))] + self.passes
        rows = [r for r in self.lexicon
                if r['status'] == 'verified' and r['form'] not in self.accepted]
        bad = hits(rows, passes)
        msg = '\n'.join(f"  {r['form']} -> {got}  [{r['source']} {r['row_id']} {r['scan']}]  {', '.join(fired)}"
                        for r, got, fired in bad[:40])
        if bad:
            self.fail(f'{len(bad)} verified headword(s) rewritten with --usage:\n{msg}')

    def test_unverified_headwords_report(self):
        """Never fails. Reports hits on unchecked rows for the headword audit."""
        rows = [r for r in self.lexicon if r['status'] != 'verified']
        bad = hits(rows, self.passes)
        if bad:
            sys.stderr.write(f'\n[lexicon] {len(bad)} unverified headword(s) rewritten '
                             f'- run tools/lexicon_review.py for the review queue\n')


if __name__ == '__main__':
    unittest.main()
