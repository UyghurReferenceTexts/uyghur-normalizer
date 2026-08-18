# -*- coding: utf-8 -*-
"""Suffix engine: harmony, voicing, vowel-final, raising, and declining.

Each case is (variant, replacement, suffix_in_text, expected_output[, flags]).
expected_output of None means the engine MUST decline and leave the text alone.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uyghur_normalizer import (  # noqa: E402
    harmony, concat_is_safe, rewrite_suffix, needs_raising,
)

CASES = [
    # --- the three suffixed duplicates currently in calque_map.tsv ---
    ('شىزاڭ', 'تىبەت', 'دىمۇ', None),   # raised LOC+ALSO — declines by design
    # --- harmony crossing on the flagship rule ---
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'لار', 'پىرېزىدېنتلەر'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'قا', 'پىرېزىدېنتكە'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'نىڭ', 'پىرېزىدېنتنىڭ'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'دا', 'پىرېزىدېنتتە'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'دىن', 'پىرېزىدېنتتىن'),
    # --- voicing only (same harmony) ---
    ('داشۆ', 'ئالىي مەكتەپ', 'گە', 'ئالىي مەكتەپكە'),
    ('داشۆ', 'ئالىي مەكتەپ', 'دە', 'ئالىي مەكتەپتە'),
    # --- vowel-final vs consonant-final: possessive allomorph ---
    ('خەنزۇ', 'خىتاي', 'سى', 'خىتايى'),
    # --- safe cases must be untouched ---
    ('خەنزۇ', 'خىتاي', 'لار', 'خىتايلار'),
    ('جۇڭگو', 'خىتاي', 'غا', 'خىتايغا'),
    # --- plural+poss3 is invariant, and leaves a vowel-final stem ---
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'لىرى', 'پىرېزىدېنتلىرى'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'لىرىغا', 'پىرېزىدېنتلىرىگە'),
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'لىرىدا', 'پىرېزىدېنتلىرىدە'),
    # --- stacked: poss3 + case ---
    ('فاڭجېن', 'يۆنىلىش', 'ىغا', 'يۆنىلىشىگە'),
    ('فاڭجېن', 'يۆنىلىش', 'ىنى', 'يۆنىلىشىنى'),
    # --- locative-relative ---
    # --- vowel raising: final ا/ە -> ى before a suffix ---
    ('مېيگو', 'ئامېرىكا', 'دا', 'ئامېرىكىدا', ['raise']),
    ('مېيگو', 'ئامېرىكا', 'غا', 'ئامېرىكىغا', ['raise']),
    ('مېيگو', 'ئامېرىكا', 'سى', 'ئامېرىكىسى', ['raise']),
    ('مېيگو', 'ئامېرىكا', 'لار', 'ئامېرىكىلار', ['raise']),
    # raising must NOT flip the harmony class read off the raised stem
    ('لۇشيەن', 'مۇساپە', 'دا', 'مۇساپىدە', ['raise']),
    ('لۇشيەن', 'مۇساپە', 'سى', 'مۇساپىسى', ['raise']),
    # the ـىيە class must NOT raise — this is the era reform
    ('تراگېدىيى', 'تراگېدىيە', 'سى', 'تراگېدىيەسى'),
    ('تېررىتورىيى', 'تېررىتورىيە', 'گە', 'تېررىتورىيەگە'),
    # lexical exception, marked noraise
    ('گۇڭشې', 'كوممۇنا', 'دە', 'كوممۇنادا', []),
    ('گۇڭشې', 'كوممۇنا', 'دىكى', 'كوممۇنادىكى', []),
    # same rule WITHOUT the flag raises, which is why the flag has to exist
    ('گۇڭشې', 'كوممۇنا', 'دە', 'كوممۇنىدا', ['raise']),
    # --- raising between suffixes: تىبەت+تا+مۇ -> تىبەتتىمۇ ---
    ('شىزاڭ', 'تىبەت', 'دامۇ', 'تىبەتتىمۇ'),
    ('شىزاڭ', 'تىبەت', 'غامۇ', 'تىبەتكىمۇ'),
    ('شىزاڭ', 'تىبەت', 'لارمۇ', 'تىبەتلەرمۇ'),
    # --- unrecognised morpheme must DECLINE, not guess ---
    ('زۇڭتۇڭ', 'پىرېزىدېنت', 'لىقلاشتۇرۇش', None),
]


class TestSuffixEngine(unittest.TestCase):
    pass


def _make(case):
    lhs, rhs, sfx, want = case[:4]
    flags = frozenset(case[4]) if len(case) > 4 else frozenset()

    def test(self):
        if concat_is_safe(lhs, rhs) and not needs_raising(rhs, sfx, flags):
            got = rhs + sfx
        else:
            r = rewrite_suffix(rhs, sfx, flags)
            got = None if r is None else r[0] + r[1]
        self.assertEqual(got, want, f'{lhs}+{sfx} -> {got}, expected {want}')
    return test


for _i, _c in enumerate(CASES):
    _name = f'test_{_i:02d}_{_c[0]}_{_c[2] or "bare"}'
    setattr(TestSuffixEngine, _name, _make(_c))


class TestHarmony(unittest.TestCase):
    def test_back(self):
        for w in ('زۇڭتۇڭ', 'كوممۇنا', 'خىتاي'):
            self.assertEqual(harmony(w), 'back', w)

    def test_front(self):
        for w in ('پىرېزىدېنت', 'مەكتەپ', 'يۆنىلىش'):
            self.assertEqual(harmony(w), 'front', w)

    def test_undecidable_returns_none(self):
        """A word with only neutral ى has no readable class. The engine must
        say so rather than guess, so callers can decline."""
        self.assertIsNone(harmony('كىشى'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
