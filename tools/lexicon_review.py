#!/usr/bin/env python3
"""
lexicon_review.py — write the review queue behind tests/test_lexicon.py.

Every headword in tests/data/lexicon_snapshot.tsv.gz that the orthographic
passes would change, with its row id, verification status and scan image.
For each line, check the scan and decide:

    the print shows the form as listed  ->  the rule is wrong: fix the map
                                            (or add a lexicon_exceptions entry)
    the print shows the 2009 form       ->  the headword is an OCR error:
                                            fix it in the headword lists

    python tools/lexicon_review.py [--out lexicon_review.csv]
"""
import argparse, csv, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
sys.path.insert(0, ROOT)
from test_lexicon import DATA, tsv, ortho_passes, hits  # noqa: E402
import gzip  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='lexicon_review.csv')
    a = ap.parse_args()
    lex = tsv(os.path.join(DATA, 'lexicon_snapshot.tsv.gz'), gzip.open)
    exc = {e['form'] for e in tsv(os.path.join(DATA, 'lexicon_exceptions.tsv'))}
    bad = hits([r for r in lex if r['form'] not in exc], ortho_passes())
    bad.sort(key=lambda x: (x[0]['status'] != 'verified', x[0]['source'], x[0]['row_id']))
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['status', 'source', 'row_id', 'scan', 'as_extracted', 'pipeline_output', 'rules', 'verdict'])
        for r, got, fired in bad:
            w.writerow([r['status'], r['source'], r['row_id'], r['scan'], r['form'], got, '; '.join(fired), ''])
    v = sum(1 for r, *_ in bad if r['status'] == 'verified')
    print(f'{len(bad)} rows ({v} verified, {len(bad) - v} unverified) -> {a.out}')


if __name__ == '__main__':
    main()
