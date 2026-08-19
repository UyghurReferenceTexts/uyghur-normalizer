# -*- coding: utf-8 -*-
"""Invariants every map must satisfy. Run: python -m unittest discover tests

These are the checks that used to be run by hand before accepting a change.
Running them in CI is the point: a map is data, and data rots quietly.
"""

import os
import sys
import unicodedata
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uyghur_normalizer import (  # noqa: E402
    KNOWN_FLAGS, UG_ALPHABET, ARABIC_RANGES, SFX_CLASS,
    load_map, process_text, build_pattern, Report,
)

MAPS = ['calque_map.tsv', 'era_map.tsv', 'imla_loan_map.tsv']
MAP_DIR = os.path.join(ROOT, 'normalizer')
PASS_ORDER = MAPS  # calque -> era -> imla_loan; this order is load-bearing


def raw_lines(name):
    with open(os.path.join(MAP_DIR, name), encoding='utf-8-sig') as fh:
        return [l.rstrip('\n') for l in fh]


def rules(name):
    return load_map(os.path.join(MAP_DIR, name), name, quiet=True)


class TestMapIntegrity(unittest.TestCase):

    def test_maps_exist_and_are_nonempty(self):
        for m in MAPS:
            with self.subTest(map=m):
                self.assertTrue(rules(m), f'{m} loaded zero rules')

    def test_every_data_line_has_two_fields(self):
        for m in MAPS:
            for i, line in enumerate(raw_lines(m), 1):
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                with self.subTest(map=m, line=i):
                    self.assertGreaterEqual(
                        len(line.split('\t')), 2,
                        f'{m}:{i} is not tab-separated: {line!r}')

    def test_no_stray_whitespace_in_fields(self):
        for m in MAPS:
            for i, line in enumerate(raw_lines(m), 1):
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                for k, field in enumerate(line.split('\t')[:2]):
                    with self.subTest(map=m, line=i, col=k):
                        self.assertEqual(field, field.strip(),
                                         f'{m}:{i} col{k} has padding: {field!r}')

    def test_all_text_is_nfc(self):
        for m in MAPS:
            for i, line in enumerate(raw_lines(m), 1):
                with self.subTest(map=m, line=i):
                    self.assertEqual(unicodedata.normalize('NFC', line), line,
                                     f'{m}:{i} is not NFC-normalised')

    def test_no_duplicate_left_hand_sides(self):
        for m in MAPS:
            c = Counter(r[0] for r in rules(m))
            dupes = [k for k, v in c.items() if v > 1]
            with self.subTest(map=m):
                self.assertEqual(dupes, [], f'{m} has duplicate LHS: {dupes}')

    def test_no_rule_is_a_no_op(self):
        for m in MAPS:
            bad = [r[0] for r in rules(m) if r[0] == r[1]]
            with self.subTest(map=m):
                self.assertEqual(bad, [], f'{m} maps a form to itself: {bad}')

    def test_no_self_loop_within_a_map(self):
        """No LHS may also be an RHS in the SAME map.

        Cross-map chains are fine and intended (calque output is normalised by
        era, era output by imla_loan). Within one map a chain means two rules
        fight, or that the new spelling of one word is the old spelling of a
        different one — which string rewriting cannot resolve.
        """
        for m in MAPS:
            rs = rules(m)
            lhs = {r[0] for r in rs}
            rhs = {r[1] for r in rs}
            with self.subTest(map=m):
                self.assertEqual(sorted(lhs & rhs), [],
                                 f'{m} rewrites into its own left-hand side')

    def test_no_rule_is_a_prefix_of_its_own_replacement(self):
        """If the replacement starts with the variant, then every ALREADY
        CORRECT occurrence looks like the variant plus a suffix, and the rule
        fires on text that was already right. لۇئاند -> لۇئاندا matches the
        correct لۇئاندا with ا captured as a suffix.

        Such a rule must carry `nosfx` so it only fires on the bare form.
        """
        for m in MAPS:
            for lhs, rhs, _lb, flags in rules(m):
                if rhs.startswith(lhs) and rhs != lhs:
                    with self.subTest(map=m, rule=lhs):
                        self.assertIn(
                            'nosfx', flags,
                            f'{m}: {lhs} -> {rhs} needs the nosfx flag; the '
                            f'replacement begins with the variant')

    def test_left_hand_sides_can_occur_word_initially(self):
        """Rules only fire at a word boundary, so a variant that cannot begin
        a Uyghur word is dead. In practice such entries are extraction
        fragments rather than words: no Uyghur word starts with ڭ, and a
        word-initial vowel always carries ئ."""
        impossible = set('ڭاەېوۆۈۇى')
        for m in MAPS:
            for lhs, rhs, _lb, _f in rules(m):
                with self.subTest(map=m, rule=lhs):
                    self.assertNotIn(
                        lhs[0], impossible,
                        f'{m}: {lhs} -> {rhs} can never match; no Uyghur word '
                        f'begins with {lhs[0]!r}')

    def test_flags_are_recognised(self):
        for m in MAPS:
            for lhs, _rhs, _lb, flags in rules(m):
                with self.subTest(map=m, rule=lhs):
                    self.assertTrue(flags <= KNOWN_FLAGS,
                                    f'{m}: {lhs} has unknown flag(s)')

    def test_boundary_class_covers_the_alphabet(self):
        import re
        self.assertRegex(UG_ALPHABET, f'^[{ARABIC_RANGES}]+$')
        self.assertRegex(UG_ALPHABET, f'^[{re.escape(SFX_CLASS)}]+$')


class TestPipeline(unittest.TestCase):
    """End-to-end properties of the three-pass pipeline."""

    def setUp(self):
        self.passes = [build_pattern(rules(m)) for m in PASS_ORDER]

    def run_passes(self, text):
        return process_text(text, self.passes, Report())

    def test_idempotent(self):
        """Normalising twice must equal normalising once.

        If this fails, some pass produces a form that another pass rewrites,
        and the result depends on how many times the tool was run.
        """
        sample = ' '.join(r[0] for m in MAPS for r in rules(m)[:200])
        once = self.run_passes(sample)
        twice = self.run_passes(once)
        self.assertEqual(once, twice, 'pipeline is not idempotent')

    def test_every_rule_fires_on_its_own_left_hand_side(self):
        """A rule that cannot match its own LHS is dead — usually a boundary
        or encoding problem rather than a linguistic one."""
        for m in MAPS:
            for lhs, rhs, _lb, flags in rules(m):
                with self.subTest(map=m, rule=lhs):
                    self.assertNotEqual(
                        self.run_passes(lhs), lhs,
                        f'{m}: rule {lhs}->{rhs} does not fire on its own input')

    def test_output_is_stable_under_a_trailing_suffix(self):
        """Applying a rule to an inflected form must not produce a form that a
        later pass then rewrites again."""
        for m in MAPS:
            for lhs, _rhs, _lb, flags in rules(m)[:300]:
                if 'nosfx' in flags:
                    continue
                probe = lhs + 'نىڭ'
                with self.subTest(map=m, rule=lhs):
                    once = self.run_passes(probe)
                    self.assertEqual(once, self.run_passes(once))


if __name__ == '__main__':
    unittest.main(verbosity=2)
