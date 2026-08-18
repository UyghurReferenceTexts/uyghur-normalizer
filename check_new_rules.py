#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
check_new_rules.py — vet a batch of proposed rules before they enter a map.

Reads a two-column sheet (old form, new form) and checks the batch against the
maps you already have. Writes nothing to the maps: it emits a clean TSV of the
rules that are safe to append, and a CSV of everything a human has to decide.

    python check_new_rules.py --xlsx era_new_list.xlsx ^
        --maps normalizer\calque_map.tsv normalizer\era_map.tsv normalizer\imla_loan_map.tsv ^
        --out-dir review

By default it reads the first two columns of the first sheet, skipping a header
row. Use --old-col/--new-col to pick columns by header name.

REASON CODES (worst first; a row gets the first that applies)
  REVERSE      an existing map already rewrites new->old. You are proposing the
               opposite direction. One of the two is wrong. Always resolve.
  CONFLICT     LHS already mapped, to a DIFFERENT target.
  CHAIN        something else rewrites INTO this rule's LHS, so a second run --
               or another rule in the same batch -- would rewrite it again.
               Often this means two entries collide: the NEW spelling of one
               word is the OLD spelling of a different word, and no amount of
               ordering can tell them apart. Usually the rule must be dropped.
  DUPLICATE    already present with the same target. Drop it.
  DUP_IN_SHEET the same LHS appears twice in this batch.
  NAMING       the two sides differ in word count. That is a naming/terminology
               change, not an orthographic one, and belongs in a different map.
  SUBSTRING    this LHS is contained in another LHS. Longest-first ordering
               handles it, but check that the shorter rule is not over-broad.
  SHORT        LHS <= --min-len characters. Short literals over-match.
  HYGIENE      stray whitespace or non-NFC codepoints in the cell.
  OK           safe to append.
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict


def fold(s):
    return unicodedata.normalize('NFC', (s or '').strip())


def load_map(path):
    """variant<TAB>standard[<TAB>flags]; returns {lhs: rhs}."""
    out = {}
    if not os.path.exists(path):
        print(f'  [missing] {path}', file=sys.stderr)
        return out
    with open(path, encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            a, b = fold(parts[0]), fold(parts[1])
            if a and b and a not in out:
                out[a] = b
    return out


def read_sheet(path, old_col, new_col, sheet):
    try:
        import openpyxl
    except ImportError:
        sys.exit('needs openpyxl:  pip install openpyxl --break-system-packages')
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        sys.exit('empty sheet')
    header = [str(c).strip() if c is not None else '' for c in rows[0]]
    if old_col or new_col:
        try:
            i, j = header.index(old_col), header.index(new_col)
        except ValueError:
            sys.exit(f'columns {old_col!r}/{new_col!r} not in header {header}')
    else:
        i, j = 0, 1
        print(f'  using first two columns: {header[0]!r} -> {header[1]!r}')
    out = []
    for n, r in enumerate(rows[1:], 2):
        raw_a = r[i] if i < len(r) else None
        raw_b = r[j] if j < len(r) else None
        a, b = fold(raw_a), fold(raw_b)
        if not a and not b:
            continue
        dirty = (str(raw_a or '') != a) or (str(raw_b or '') != b)
        extra = ' | '.join(str(c) for k, c in enumerate(r)
                           if c is not None and k not in (i, j))
        out.append({'row': n, 'old': a, 'new': b, 'dirty': dirty, 'note': extra})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--sheet')
    ap.add_argument('--old-col', help='header name of the OLD/variant column')
    ap.add_argument('--new-col', help='header name of the NEW/standard column')
    ap.add_argument('--maps', nargs='+', required=True,
                    help='every map the pipeline uses — pass them ALL, or the '
                         'cross-checks are blind to whichever you leave out')
    ap.add_argument('--target-map',
                    help='the map these rules are destined for. Chains are only '
                         'an error WITHIN one map: passes run calque -> era -> '
                         'imla_loan, so an era rule feeding an imla_loan rule is '
                         'the design, not a bug. Without this, chain checking is '
                         'limited to collisions inside the batch itself.')
    ap.add_argument('--out-dir', default='review')
    ap.add_argument('--min-len', type=int, default=5)
    args = ap.parse_args()

    print('== maps ==')
    maps = {}
    for p in args.maps:
        m = load_map(p)
        maps[os.path.basename(p)] = m
        print(f'  {os.path.basename(p):24} {len(m)} rules')

    all_lhs = {}          # lhs -> (mapname, rhs), across every map
    for name, m in maps.items():
        for a, b in m.items():
            all_lhs.setdefault(a, (name, b))

    # Chains only matter within a single map. Passes run calque -> era ->
    # imla_loan, so era producing a form that imla_loan then rewrites is the
    # intended design and must not be flagged.
    target = os.path.basename(args.target_map) if args.target_map else None
    same_map_rhs = set(maps.get(target, {}).values()) if target else set()
    if target and target not in maps:
        sys.exit(f'--target-map {target} was not among --maps')
    print(f'\n  chain scope: {target or "batch only (no --target-map given)"}')

    print(f'\n== batch: {args.xlsx} ==')
    rows = read_sheet(args.xlsx, args.old_col, args.new_col, args.sheet)
    print(f'  {len(rows)} row(s) with content')

    seen = Counter(r['old'] for r in rows)
    batch_lhs = {r['old']: r['new'] for r in rows if r['old']}
    batch_rhs = defaultdict(list)
    for r in rows:
        if r['new']:
            batch_rhs[r['new']].append(r['old'])

    universe = sorted(set(batch_lhs) | set(all_lhs), key=len)
    contained = set()
    for a in batch_lhs:
        for b in universe:
            if a != b and len(b) > len(a) and a in b:
                contained.add(a)
                break

    for r in rows:
        a, b, reasons = r['old'], r['new'], []
        if not a or not b:
            reasons.append('HYGIENE:empty side')
        if a and a == b:
            reasons.append('DUPLICATE:no-op')
        if b in all_lhs:
            reasons.append(f'REVERSE:{all_lhs[b][0]} maps {b}->{all_lhs[b][1]}')
        if a in all_lhs:
            other = all_lhs[a]
            reasons.append(('DUPLICATE:' if other[1] == b else 'CONFLICT:')
                           + f'{other[0]} has {a}->{other[1]}')
        # something else rewrites INTO this LHS, inside the same map
        if a in same_map_rhs:
            reasons.append(f'CHAIN:{target} already produces {a}')
        producers = [x for x in batch_rhs.get(a, []) if x != a]
        if producers:
            reasons.append(f'CHAIN:batch row {producers[0]}->{a} feeds this rule')
        # this rule's OUTPUT is rewritten again by another batch row
        if b in batch_lhs and b != a and batch_lhs[b] != b:
            reasons.append(f'CHAIN:batch rewrites the output {b}->{batch_lhs[b]}')
        if seen[a] > 1:
            reasons.append(f'DUP_IN_SHEET:x{seen[a]}')
        if a and b and len(a.split()) != len(b.split()):
            reasons.append('NAMING:word count differs')
        if a in contained:
            reasons.append('SUBSTRING')
        if a and len(a) <= args.min_len:
            reasons.append(f'SHORT:{len(a)}')
        if r['dirty']:
            reasons.append('HYGIENE:whitespace/NFC')
        r['reasons'] = reasons

    order = ['REVERSE', 'CONFLICT', 'CHAIN', 'DUPLICATE', 'DUP_IN_SHEET',
             'NAMING', 'SUBSTRING', 'SHORT', 'HYGIENE']

    def worst(r):
        for k in order:
            for x in r['reasons']:
                if x.startswith(k):
                    return k
        return 'OK'

    for r in rows:
        r['code'] = worst(r)

    os.makedirs(args.out_dir, exist_ok=True)
    counts = Counter(r['code'] for r in rows)
    print('\n== verdict ==')
    for k in order + ['OK']:
        if counts[k]:
            print(f'  {k:14} {counts[k]:4}')

    clean = [r for r in rows if r['code'] == 'OK']
    p1 = os.path.join(args.out_dir, 'new_rules.tsv')
    with open(p1, 'w', encoding='utf-8', newline='') as fh:
        fh.write(f'# generated by check_new_rules.py from {os.path.basename(args.xlsx)}\n')
        fh.write('# reviewed: NO — read these before appending to any map\n')
        for r in clean:
            fh.write(f"{r['old']}\t{r['new']}\n")
    print(f'\n[clean] {len(clean)} rule(s) -> {p1}')

    flagged = [r for r in rows if r['code'] != 'OK']
    p2 = os.path.join(args.out_dir, 'review.csv')
    with open(p2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['row', 'code', 'old', 'new', 'all_reasons', 'sheet_note'])
        for r in sorted(flagged, key=lambda x: order.index(x['code'])):
            w.writerow([r['row'], r['code'], r['old'], r['new'],
                        '; '.join(r['reasons']), r['note']])
    print(f'[review] {len(flagged)} row(s) -> {p2}')
    print('\nNothing was written to any map.')


if __name__ == '__main__':
    main()
