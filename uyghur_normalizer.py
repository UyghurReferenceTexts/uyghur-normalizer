#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
uyghur_normalizer.py — orthographic and terminological normalizer for Uyghur text.

WHAT IT DOES
============
Applies find-and-replace maps to Uyghur text, in a fixed order, with a log:

    pass 1  calque_map.tsv       terminology  (Chinese calque -> Uyghur term)
    pass 2  era_map.tsv          orthography  (pre-2009 -> 2009 imla)
    pass 3  imla_loan_map.tsv    orthography  (2009/2011 loanword shape)
    pass 4  <your fix map>       OPT-IN: forms a model invents that were never
                                 in its training corpus (--fix-map)

The order is load-bearing: pass-3 inputs are pass-2 outputs, and pass 1 runs
first so its right-hand sides get normalized by passes 2-3 automatically.

Passes 1-3 are on by default; each can be switched off. Pass 4 is off unless
you point --fix-map at a file.

SUFFIX HANDLING
===============
A rule matches at a word boundary and may be followed by Uyghur suffixes.
Naive `replacement + suffix` is wrong whenever the two sides differ in vowel
harmony, final-consonant voicing, or vowel/consonant ending:

    زۇڭتۇڭلار  ->  پىرېزىدېنتلار   WRONG   (needs -لەر)
    گۇڭشېدە    ->  كوممۇنادە       WRONG   (needs -دا)
    داشۆگە     ->  ئالىي مەكتەپگە  WRONG   (needs -كە)

So the suffix is re-derived, morpheme by morpheme, against the replacement.
Three outcomes:

    SAFE      both sides agree on harmony / voicing / vowel-final
              -> concatenate unchanged (fast path, no behaviour change)
    REWRITE   they disagree and every morpheme is recognised
              -> emit the correct allomorphs
    SKIP      they disagree and some morpheme is NOT recognised, or the
              replacement has no harmony-bearing vowel
              -> LEAVE THE TEXT ALONE and record it for review

SKIP is deliberate. A normalizer that guesses is worse than one that declines.
Everything skipped is printed and can be written out with --review.

RULE FLAGS (optional third TSV column)
======================================
    variant <TAB> standard <TAB> flags

    nosfx    fire only on the bare form; if a suffix follows, skip and report.
             Use when the replacement is already inflected, e.g.
             سوغۇق ئۇرۇش <TAB> سوغۇقچىلىق ئۇرۇشى <TAB> nosfx
             (without it, سوغۇق ئۇرۇشى -> سوغۇقچىلىق ئۇرۇشىسى)

    raise    the replacement's final ا/ە raises to ى before a suffix:
             ئامېرىكا + دا -> ئامېرىكىدا. OFF by default, because the ـىيە
             class must NOT raise (تېررىتورىيە + سى -> تېررىتورىيەسى) and it
             dominates any 2009-imla map. Set it per rule where it applies.

Unknown flags are reported at load time and ignored.

SCAN FIRST, APPLY SECOND
========================
Default mode is SCAN: prints every proposed change, writes nothing.

    python uyghur_normalizer.py --in text.txt
    python uyghur_normalizer.py --in text.txt --apply
    python uyghur_normalizer.py --in text.txt --apply --out clean.txt
    python uyghur_normalizer.py --in text.txt --log fixes.csv --review skipped.csv
    python uyghur_normalizer.py --in out_ug.txt --fix-map normalizer/output_fix_map.tsv --apply

FORMATS: plain text (whole file), .jsonl (translation.ug field), and EN:/UG:
benchmark blocks (only UG lines touched) are auto-detected.

Never edits in place. --apply writes a NEW file.
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, OrderedDict

__version__ = '1.1.0'

# ---------------------------------------------------------------------------
# Character classes
# ---------------------------------------------------------------------------

# The modern Uyghur Arabic alphabet. Used for the suffix capture: only these
# letters may be absorbed as a suffix.
UG_ALPHABET = 'ئابپتجچخدرزژسشغفقكگڭلمنھوۇۆۈۋېەىي'
ZWNJ = '\u200c'
SFX_CLASS = UG_ALPHABET + ZWNJ

# Broader Arabic-script test, used only for word boundaries. A rule must not
# fire inside a longer Arabic-script word, even one containing letters outside
# the modern alphabet (ع ص ض ط ظ ث ذ ح, common in older or Arabic-loan text).
ARABIC_RANGES = (
    '\u0620-\u064a'   # Arabic letters
    '\u066e-\u06d3'   # extended, incl. Uyghur/Persian letters
    '\u06d5'          # ARABIC LETTER AE — Uyghur ە. Sits ABOVE the range above,
                      # separated from it by U+06D4 (a full stop). Omitting it
                      # silently breaks word-boundary detection for most Uyghur
                      # words; the assertion below exists to catch that class of
                      # error if these ranges are ever edited.
    '\u06fa-\u06ff'
    '\u0750-\u077f'   # Arabic Supplement
    + ZWNJ
)

_boundary_check = re.compile(f'^[{ARABIC_RANGES}]+$')
assert _boundary_check.match(UG_ALPHABET), \
    'ARABIC_RANGES does not cover the whole Uyghur alphabet'

BACK_VOWELS = set('اوۇ')
FRONT_VOWELS = set('ەېۆۈ')
NEUTRAL_VOWELS = set('ى')
VOWELS = BACK_VOWELS | FRONT_VOWELS | NEUTRAL_VOWELS
ROUNDED = set('وۇۆۈ')
VOICELESS = set('پتكقچسشخفھ')

# Arabic presentation forms. These get folded to their base letters on load so
# that a stray ﭙ or ﻻ in scanned/OCR'd input does not defeat the matcher.
PRESENTATION_RE = re.compile(r'[\uFB50-\uFDFF\uFE70-\uFEFF]')


def fold_text(s):
    """NFKC-fold Arabic presentation forms only, then NFC the whole string."""
    if PRESENTATION_RE.search(s):
        s = PRESENTATION_RE.sub(lambda m: unicodedata.normalize('NFKC', m.group(0)), s)
    return unicodedata.normalize('NFC', s)


# ---------------------------------------------------------------------------
# Phonology
# ---------------------------------------------------------------------------

def harmony(word):
    """'back', 'front', or None. Rightmost non-neutral vowel decides.

    None means the word carries only ى (or no vowel at all) and its class
    cannot be read off the spelling. Callers must treat None as 'unknown'.
    """
    for ch in reversed(word):
        if ch in BACK_VOWELS:
            return 'back'
        if ch in FRONT_VOWELS:
            return 'front'
    return None


def last_letter(word):
    for ch in reversed(word):
        if ch in SFX_CLASS and ch != ZWNJ:
            return ch
    return ''


def ends_vowel(word):
    return last_letter(word) in VOWELS


def ends_voiceless(word):
    return last_letter(word) in VOICELESS


def is_rounded(word):
    """Rightmost non-neutral vowel rounded? Used only for -لىق/-لۇق."""
    for ch in reversed(word):
        if ch in BACK_VOWELS or ch in FRONT_VOWELS:
            return ch in ROUNDED
    return None


# ---------------------------------------------------------------------------
# Suffix allomorphy
# ---------------------------------------------------------------------------
# Each entry: (name, {surface variants seen in input}, selector(stem) -> str|None)
# The selector returns the correct allomorph for the given stem, or None when
# it cannot be determined (which aborts the whole rewrite).

def _harm(back, front):
    def sel(stem, hint):
        if hint is None:
            return None
        return back if hint == 'back' else front
    return sel


def _inv(form):
    return lambda stem, hint: form


def _dative(stem, hint):
    if hint is None:
        return None
    if hint == 'back':
        return 'قا' if ends_voiceless(stem) else 'غا'
    return 'كە' if ends_voiceless(stem) else 'گە'


def _locative(stem, hint):
    if hint is None:
        return None
    if ends_voiceless(stem):
        return 'تا' if hint == 'back' else 'تە'
    return 'دا' if hint == 'back' else 'دە'


def _loc_rel(stem, hint):    # -دىكى / -تىكى  (locative + relativiser)
    return 'تىكى' if ends_voiceless(stem) else 'دىكى'


def _ablative(stem, hint):   # harmony-invariant, voicing only
    return 'تىن' if ends_voiceless(stem) else 'دىن'


def _similative(stem, hint):  # -دەك / -تەك
    return 'تەك' if ends_voiceless(stem) else 'دەك'


def _poss3(stem, hint):      # -ى after consonant, -سى after vowel
    return 'سى' if ends_vowel(stem) else 'ى'


def _nominaliser(stem, hint, rounded=None):   # -لىق / -لىك / -لۇق / -لۈك
    if hint is None or rounded is None:
        return None
    if hint == 'back':
        return 'لۇق' if rounded else 'لىق'
    return 'لۈك' if rounded else 'لىك'


SUFFIXES = [
    ('PLUR.POSS3', {'لىرى'},                       _inv('لىرى')),
    ('LOC.REL',    {'دىكى', 'تىكى'},               _loc_rel),
    ('NMLZ',       {'لىق', 'لىك', 'لۇق', 'لۈك'},   _nominaliser),
    ('PLUR',       {'لار', 'لەر'},                 _harm('لار', 'لەر')),
    ('GEN',        {'نىڭ'},                        _inv('نىڭ')),
    ('ABL',        {'دىن', 'تىن'},                 _ablative),
    ('SIM',        {'دەك', 'تەك'},                 _similative),
    ('PRIV',       {'سىز'},                        _inv('سىز')),
    ('DAT',        {'غا', 'گە', 'قا', 'كە'},       _dative),
    ('LOC',        {'دا', 'دە', 'تا', 'تە'},       _locative),
    ('ACC',        {'نى'},                         _inv('نى')),
    ('POSS3',      {'ى', 'سى'},                    _poss3),
    ('AGT',        {'چى'},                         _inv('چى')),
    ('EQU',        {'چە'},                         _inv('چە')),
    ('ALSO',       {'مۇ'},                         _inv('مۇ')),
]

# Flattened, longest surface form first, so 'لىرى' beats 'لار', 'نىڭ' beats
# 'نى', 'دىكى' beats 'دا', 'سىز' beats 'سى'.
_SFX_TABLE = sorted(
    ((v, name, sel) for name, variants, sel in SUFFIXES for v in variants),
    key=lambda t: -len(t[0])
)


RAISING_VOWELS = set('اە')


def needs_raising(replacement, sfx, flags):
    """Does the replacement's final ا/ە raise to ى before this suffix?

    Uyghur often raises a final ا/ە when a suffix puts it in a non-final open
    syllable:  ئامېرىكا + دا -> ئامېرىكىدا,  دەرىجە + سى -> دەرىجىسى.

    But it is NOT general, and the exceptions are not marginal:

      * lexical exceptions —  كوممۇنا + دا -> كوممۇنادا, not كوممۇنىدا
      * the ـىيە class     —  تېررىتورىيە + سى -> تېررىتورىيەسى.
        Raising here would undo the 2009 imla reform outright: 96 of the
        ە-final replacements in a 1,245-rule era map are ـىيە words, and 362
        of 364 are in classes that must not raise.

    So raising is OPT-IN, per rule, via the `raise` flag. Default is off,
    which is also the historical behaviour of this normalizer. Turning it on
    globally would be a major version bump and a linguistic claim this tool
    is not in a position to make on someone else's map.

    (Raising BETWEEN suffixes — تىبەت+تا+مۇ -> تىبەتتىمۇ — is separate, always
    on, and handled in rewrite_suffix. Only LOC and DAT end in ا/ە and only مۇ
    can follow them, so that case is narrow and well attested.)
    """
    return bool(sfx) and 'raise' in flags and last_letter(replacement) in RAISING_VOWELS


def rewrite_suffix(replacement, sfx, flags=frozenset()):
    """Re-derive `sfx` against `replacement`. Returns (stem, suffix) or None.

    None means at least one morpheme was unrecognised, or an allomorph could
    not be chosen. The caller must then leave the text untouched.

    The harmony class is fixed once, from the ORIGINAL replacement, and held
    for the whole chain. Raising is a surface process and must not be allowed
    to flip the class: مۇساپە + دا is مۇساپىدە, not مۇساپىدا, even though the
    raised stem مۇساپى reads as back if you re-scan it.
    """
    hint = harmony(replacement)
    rounded = is_rounded(replacement)

    stem = replacement
    if needs_raising(replacement, sfx, flags):
        if hint is None:
            return None
        stem = replacement[:-1] + 'ى'

    out = []
    rest = sfx
    guard = 0
    while rest:
        guard += 1
        if guard > 12:                       # runaway safety
            return None
        for surface, name, sel in _SFX_TABLE:
            if rest.startswith(surface):
                if name == 'NMLZ':
                    form = sel(stem, hint, rounded)
                else:
                    form = sel(stem, hint)
                if form is None:
                    return None
                # Raising between suffixes is always on and independent of the
                # `raise` flag, which governs the replacement's own final vowel:
                # تىبەت + تا + مۇ -> تىبەتتىمۇ.
                if len(stem) > len(replacement) and stem[-1] in RAISING_VOWELS:
                    stem = stem[:-1] + 'ى'
                    out[-1] = out[-1][:-1] + 'ى'
                out.append(form)
                stem += form
                rest = rest[len(surface):]
                break
        else:
            return None
    raised = stem[:len(replacement)]
    return raised, ''.join(out)


def concat_is_safe(lhs, rhs):
    """True when replacement+suffix cannot change any allomorph choice."""
    return (harmony(lhs) == harmony(rhs)
            and ends_voiceless(lhs) == ends_voiceless(rhs)
            and ends_vowel(lhs) == ends_vowel(rhs))


# ---------------------------------------------------------------------------
# Map loading
# ---------------------------------------------------------------------------

KNOWN_FLAGS = {'nosfx', 'raise'}


def load_map(path, label, quiet=False):
    """Read variant<TAB>standard[<TAB>flags]. '#' comments and blanks skipped."""
    rules = []
    if not os.path.exists(path):
        print(f'  [skip] {label:11} not found at {path}')
        return rules
    seen = {}
    bad_flags = Counter()
    dupes = 0
    with open(path, encoding='utf-8-sig') as fh:
        for ln, line in enumerate(fh, 1):
            line = line.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            lhs = fold_text(parts[0].strip())
            rhs = fold_text(parts[1].strip())
            if not lhs or not rhs or lhs == rhs:
                continue
            flags = set()
            if len(parts) > 2 and parts[2].strip():
                for f in parts[2].replace(',', ' ').split():
                    f = f.strip().lower()
                    if f.startswith('#'):
                        break
                    if f in KNOWN_FLAGS:
                        flags.add(f)
                    else:
                        bad_flags[f] += 1
            if lhs in seen:
                dupes += 1
                continue
            seen[lhs] = True
            rules.append((lhs, rhs, label, flags))
    if not quiet:
        multi = sum(1 for r in rules if ' ' in r[0])
        flagged = sum(1 for r in rules if r[3])
        extra = []
        if multi:
            extra.append(f'{multi} multiword')
        if flagged:
            extra.append(f'{flagged} flagged')
        if dupes:
            extra.append(f'{dupes} duplicate LHS dropped')
        tail = ('  (' + ', '.join(extra) + ')') if extra else ''
        print(f'  {label:11} {len(rules):5} rules{tail}')
        for f, n in bad_flags.most_common():
            print(f'    [warn] unknown flag {f!r} on {n} rule(s) — ignored')
    return rules


def build_pattern(rules):
    """One alternation per pass, longest LHS first so multiword rules win.

    A single capture group holds the matched variant and the rule is recovered
    by dict lookup. Do NOT give each rule its own named group: with a map of
    ~1,200 rules that is roughly 200x slower (108 s vs 0.5 s on 865 KB).
    """
    if not rules:
        return None, {}
    rules = sorted(rules, key=lambda r: -len(r[0]))
    lookup = {r[0]: r for r in rules}
    pat = re.compile(
        f'(?<![{ARABIC_RANGES}])'
        r'(?P<lhs>' + '|'.join(re.escape(r[0]) for r in rules) + r')'
        f'(?P<sfx>[{SFX_CLASS}]*)'
        f'(?![{ARABIC_RANGES}])'
    )
    return pat, lookup


# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.hits = Counter()        # (lhs, rhs, label, how) -> n
        self.changes = []            # (label, before, after, how)
        self.skips = Counter()       # (lhs, rhs, label, sfx, why) -> n

    @property
    def total(self):
        return sum(self.hits.values())

    @property
    def skipped(self):
        return sum(self.skips.values())


def apply_pass(text, pat, lookup, rep):
    if pat is None:
        return text

    def sub(m):
        lhs, rhs, label, flags = lookup[m.group('lhs')]
        sfx = m.group('sfx') or ''
        whole = m.group(0)

        if not sfx:
            rep.hits[(lhs, rhs, label, 'plain')] += 1
            rep.changes.append((label, whole, rhs, 'plain'))
            return rhs

        if 'nosfx' in flags:
            rep.skips[(lhs, rhs, label, sfx, 'nosfx: replacement already inflected')] += 1
            return whole

        if concat_is_safe(lhs, rhs) and not needs_raising(rhs, sfx, flags):
            rep.hits[(lhs, rhs, label, 'concat')] += 1
            rep.changes.append((label, whole, rhs + sfx, 'concat'))
            return rhs + sfx

        got = rewrite_suffix(rhs, sfx, flags)
        if got is None:
            rep.skips[(lhs, rhs, label, sfx, 'suffix not recognised / harmony undecidable')] += 1
            return whole
        stem, new_sfx = got

        how = 'rewrite' if (stem + new_sfx) != (rhs + sfx) else 'concat'
        rep.hits[(lhs, rhs, label, how)] += 1
        rep.changes.append((label, whole, stem + new_sfx, how))
        return stem + new_sfx

    return pat.sub(sub, text)


def process_text(text, passes, rep):
    for pat, lookup in passes:
        text = apply_pass(text, pat, lookup, rep)
    return text


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def detect_format(path, sample):
    if os.path.splitext(path)[1].lower() == '.jsonl':
        return 'jsonl'
    if re.search(r'^\s*EN:\s', sample, re.M) and re.search(r'^\s*UG:\s', sample, re.M):
        return 'blocks'
    return 'plain'


def main():
    ap = argparse.ArgumentParser(
        description='Normalize Uyghur text: 2009/2011 imla orthography and '
                    'de-calquing of PRC-era political vocabulary.')
    ap.add_argument('--in', dest='inp', required=True, help='file to normalize')
    ap.add_argument('--out', help='output path (default: <name>_fixed<ext>)')
    ap.add_argument('--normdir', default=os.path.join('.', 'normalizer'),
                    help='folder holding the three default maps')
    ap.add_argument('--calque-map', help='override path to calque_map.tsv')
    ap.add_argument('--era-map', help='override path to era_map.tsv')
    ap.add_argument('--loan-map', help='override path to imla_loan_map.tsv')
    ap.add_argument('--fix-map',
                    help='OPT-IN pass 4: model-invented forms. No default; '
                         'these rules describe one model, not the language.')
    ap.add_argument('--no-calque', action='store_true',
                    help='skip terminology pass (leave PRC-era vocabulary alone)')
    ap.add_argument('--no-era', action='store_true', help='skip pre-2009 imla pass')
    ap.add_argument('--no-loan', action='store_true', help='skip loanword-shape pass')
    ap.add_argument('--no-orthography', action='store_true',
                    help='shorthand for --no-era --no-loan')
    ap.add_argument('--apply', action='store_true',
                    help='write the file (default is scan only)')
    ap.add_argument('--log', help='CSV of every substitution made')
    ap.add_argument('--review', help='CSV of every match declined (needs a map entry)')
    ap.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        sys.exit(f'ERROR: input not found: {args.inp}')

    if args.no_orthography:
        args.no_era = args.no_loan = True

    print(f'== uyghur_normalizer {__version__} ==')
    print('== maps ==')

    def mp(override, name):
        return override or os.path.join(args.normdir, name)

    calque = [] if args.no_calque else load_map(mp(args.calque_map, 'calque_map.tsv'), 'calque')
    era    = [] if args.no_era    else load_map(mp(args.era_map, 'era_map.tsv'), 'era')
    loan   = [] if args.no_loan   else load_map(mp(args.loan_map, 'imla_loan_map.tsv'), 'imla_loan')
    fix    = load_map(args.fix_map, 'model_fix') if args.fix_map else []
    if not args.fix_map:
        print('  model_fix    (off — pass with --fix-map to enable)')

    passes = [build_pattern(r) for r in (calque, era, loan, fix) if r]
    if not passes:
        sys.exit('ERROR: no rules loaded — check --normdir and the --no-* flags.')

    raw = fold_text(open(args.inp, encoding='utf-8-sig').read())
    fmt = detect_format(args.inp, raw[:4000])
    print(f'\n[in]   {args.inp}   (format: {fmt})')
    print(f'[mode] {"APPLY" if args.apply else "SCAN (nothing written)"}')

    rep = Report()

    if fmt == 'jsonl':
        out_lines = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            t = obj.get('translation', obj)
            if 'ug' in t:
                t['ug'] = process_text(t['ug'], passes, rep)
            out_lines.append(json.dumps(obj, ensure_ascii=False))
        result = '\n'.join(out_lines) + '\n'
    elif fmt == 'blocks':
        out_lines = []
        for line in raw.splitlines():
            if line.startswith('UG:'):
                line = 'UG:' + process_text(line[3:], passes, rep)
            out_lines.append(line)
        result = '\n'.join(out_lines) + '\n'
    else:
        result = process_text(raw, passes, rep)

    # ---- report -----------------------------------------------------------
    byhow = Counter()
    for (_l, _r, _lb, how), n in rep.hits.items():
        byhow[how] += n
    detail = ', '.join(f'{how} {n}' for how, n in sorted(byhow.items())) or '—'
    print(f'\n[hits] {rep.total} substitution(s), {len(rep.hits)} distinct rule(s)   [{detail}]\n')

    if rep.total:
        bylabel = Counter()
        for (_l, _r, label, _h), n in rep.hits.items():
            bylabel[label] += n
        for label, n in bylabel.most_common():
            print(f'  --- {label}: {n} ---')
            for (lhs, rhs, lb, how), n2 in sorted(rep.hits.items(), key=lambda x: -x[1]):
                if lb == label:
                    tag = '' if how == 'plain' else f'   [{how}]'
                    print(f'    {n2:5}  {lhs}  ->  {rhs}{tag}')
    else:
        print('  nothing matched — text is already clean under these maps.')

    if rep.skipped:
        print(f'\n[declined] {rep.skipped} match(es) left untouched — the suffix could '
              f'not be re-derived safely.')
        by_design = sum(n for (_l, _r, _lb, _s, why), n in rep.skips.items()
                        if why.startswith('nosfx'))
        if by_design < rep.skipped:
            print('           Some need an explicit inflected entry in the map.')
        if by_design:
            print(f'           {by_design} of these are nosfx rules working as '
                  f'intended — no action needed.')
        for (lhs, rhs, label, sfx, why), n in sorted(rep.skips.items(), key=lambda x: -x[1]):
            print(f'    {n:5}  {lhs}+{sfx}   ({label}: {why})')

    if args.log and rep.changes:
        with open(args.log, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['pass', 'before', 'after', 'how'])
            w.writerows(rep.changes)
        print(f'\n[log] {len(rep.changes)} row(s) -> {args.log}')

    if args.review and rep.skips:
        with open(args.review, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['pass', 'variant', 'suffix', 'replacement', 'reason', 'count'])
            for (lhs, rhs, label, sfx, why), n in sorted(rep.skips.items(), key=lambda x: -x[1]):
                w.writerow([label, lhs, sfx, rhs, why, n])
        print(f'[review] {len(rep.skips)} row(s) -> {args.review}')

    if not args.apply:
        print('\n[scan] nothing written. Re-run with --apply to write.')
        return

    base, ext = os.path.splitext(args.inp)
    out = args.out or f'{base}_fixed{ext}'
    if os.path.abspath(out) == os.path.abspath(args.inp):
        sys.exit('ERROR: refusing to overwrite the input in place.')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(result)
    print(f'\n[done] {out}')


if __name__ == '__main__':
    main()
