# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/), read for a data repository:

- **MAJOR** — text that normalized correctly under the previous release now
  normalizes differently. A rule's target changed, a rule was withdrawn, the
  pass order changed, or the CLI changed incompatibly.
- **MINOR** — new rules, new flags, new options. Text that was previously left
  alone may now be corrected; text that was already corrected is unaffected.
- **PATCH** — documentation, tests, tooling. No change to any output.

Every entry that touches a map cites the source for the change. See the Sources
section of the README for the four reference works and their short numbers.

---

## [2.0.0] — 2026-10-17

Rules checked against the audited headword lists of [4] and [1]. Only rows
verified by hand against the scan were used as evidence; row ids and scan
images are given so each decision can be re-checked.

MAJOR because rules were withdrawn and one target changed (see Changed and
Removed): text those rules rewrote under the previous release is now left as
written or comes out differently.

### Added

- Opt-in **usage pass** (pass 0, `--usage`; override with `--usage-map`):
  common misuses to their correct form, e.g. `ئاپارات`‎ → `ئاپپارات`‎.
  Off by default: it corrects word choice rather than spelling, and would also
  change regional or literary forms used on purpose. It runs before the calque
  pass, so a pre-2009 spelling in a replacement is corrected by the era and
  loan passes (`گىراپا`‎ → `گرافىك`‎ → `گىرافىك`‎).
- `normalizer/usage_map.tsv` — 543 rules from the 685 توغرىسى entries of [2],
  built by `tools/build_usage_map.py`. A pair is left out when its wrong form
  is a headword of [4] or [1] or a word inside one (100, e.g. `ئال`‎ "take",
  `گۈندە`‎ in `ئارا گۈندە`‎), when it has three letters or fewer (14), or
  when its correct form is not attested in [4] or [1] even after normalization
  (27, held for review). 54 rules carry `nosfx` because the wrong form begins
  a real word. Every rule's correct form is attested in a row of [4] or [1]
  checked against the scan. `normalizer/usage_map_origin.tsv` records the [2]
  row of each; `tools/usage_target_overrides.tsv` replaces [2]'s form where it
  is correct but pre-2009 (`چىڭگىلىماچ`‎ → `جىڭگىلىماچ`‎, [1] D01-12151).
- `tests/test_lexicon.py` also runs the usage pass over every verified
  headword; `tests/test_maps.py` applies the map invariants to it.
- `normalizer/provenance.tsv` gains an `origin` column ([2] row for usage rules);
  for passes 0–1 the evidence is looked up for the replacement as passes 2–3
  leave it.
- README: Pass 0 section; the lexicon test and the rebuild commands under Tests.
- `tests/test_lexicon.py` — the orthographic passes must leave every verified
  headword and sub-entry of [4] and [1] unchanged. Hits on unverified rows are
  reported, not failed: the extraction model was trained on web Uyghur and may
  have written a web form the book does not print. The calque pass is not
  tested this way, since it replaces attested words by editorial choice.
- `tests/data/lexicon_snapshot.tsv.gz` — 125,256 written forms from [4] and
  [1], 35,852 of them verified, built by `tools/build_lexicon_snapshot.py`.
- `tests/data/lexicon_exceptions.tsv` — forms printed against an imla rule,
  each with a verified row and its scan: `تەكىيىسىمان`‎, `تەكىيىلىك`‎,
  `كاربيۇراتور`‎.
- `tools/lexicon_review.py` — writes the review queue behind the lexicon test.
- `normalizer/imla_loan_map.tsv`: `گرېتسىيە`‎ → `گىرېتسىيە`‎
  (Greece). Only `گرېتسىيەدىكى`‎ and `گىرىتسىيە`‎ were covered, so the
  bare and most suffixed forms were left alone. Target per the 2011 country
  table, checked against the scan.

### Changed

- `normalizer/imla_loan_map.tsv`: `سلوۋاكيە`‎ → `سلوۋاكىيە`‎ corrected
  to `سلوۋاكيە`‎ → `سىلوۋاكىيە`‎ (Slovakia). **This changes output.**
  The replacement kept the initial cluster that §IX.2 of [4] breaks up; compare
  `سلوۋاك`‎ → `سىلوۋاك`‎ in the same map. Target per the 2011 country
  table, checked against the scan.

### Removed

- `normalizer/imla_loan_map.tsv` — 871 rules to 867. **Each of these changes
  output**: text the rules used to rewrite is now left as written.
  - `رادىئۇ`‎ → `رادىيو`‎. No dictionary uses `رادىئۇ`‎ for *radio*;
    every word that begins with it is *radius*, `رادىئۇس`‎ ([4] D_15644,
    verified). As a stem rule it turned `رادىئۇس`‎ into `رادىيوس`‎.
  - `رادىيۇ`‎ → `رادىيو`‎, for the same reason. `رادىيۇ`‎ is never
    *radio* in the dictionaries, and the rule turned `رادىيۇس`‎ (a variant
    spelling of *radius*) into `رادىيوس`‎.
  - `ئاستانە`‎ → `ئاستانا`‎. `ئاستانە`‎ is an ordinary word ([4]
    D_00891, [1] D01-21640, both verified). A Kingston-class collision with the
    capital `ئاستانا`‎.
  - `نىئوبىي`‎ → `نىيوبىي`‎ and `پاترىئارخال`‎ → `پاترىيارخال`‎.
    [1] prints the `ئ`‎ forms (D02-10355, D01-05516, D01-05517, checked
    against the scans); [4] lists neither word.

### Upgrading

No change to the command line or the map format. Text processed with the
default passes changes only where a rule under Changed or Removed applies.
The usage pass is off unless you add `--usage`.

## [1.1.0] — 2026-08-19

### Added

- Two map invariants, enforced in CI:
  - a replacement may not begin with its own variant unless the rule carries
    `nosfx`;
  - a variant may not start with a character that cannot begin a Uyghur word.
- `check_new_rules.py` reports the same two conditions as `PREFIX` and
  `UNFIREABLE`.

### Changed

- The `لۇشيەن`‎ → `مۇساپە`‎ rule in `normalizer/calque_map.tsv` now
  carries the `raise` flag. **This changes output.** `مۇساپە`‎ is an ordinary
  `ە`‎-final noun, so its final vowel raises before a suffix. Suffixed
  forms now normalize to `مۇساپىسى`‎ and `مۇساپىدە`‎, where 1.0.x
  produced `مۇساپەسى`‎ and `مۇساپەدە`‎. The 1.0.x forms were wrong.
- The declined-matches report no longer tells you to add a map entry for
  `nosfx` skips, which are working as intended.

### Fixed

- `normalizer/imla_loan_map.tsv` — 873 rules to 871.
  - Vienna: `ۋىيېنا`‎ → `ۋيېننا`‎ corrected to `ۋىيېنا`‎ →
    `ۋىيېننا`‎. **This changes output.** The replacement had lost its
    `ى`‎, which made it the only rule in the map running against the
    epenthesis direction of §IX.2 — compare `ۋيېتنام`‎ →
    `ۋىيېتنام`‎, which inserts the same vowel. Checked against the source
    image: the post-2009 form is `ۋىيېننا`‎, the pre-2009 form
    `ۋىيېنا`‎. A transcription error, not a rule.
  - Kingstown-class defect: `لۇئاند`‎ → `لۇئاندا`‎ and
    `مالابو`‎ → `مالابوئا`‎ now carry `nosfx`. In both, the variant is
    a prefix of its own replacement, so every already-correct occurrence looked
    like the variant plus a suffix. The suffix engine declined rather than
    corrupting them, which is how they were found.
  - Removed `مىچىسى`‎ → `مچىسى`‎ and `ڭىنىڭ`‎ → `ڭنىڭ`‎.
    Neither variant is a word; both are extraction fragments. The second could
    never fire, as no Uyghur word begins with `ڭ`‎.

### Upgrading

Output changes for suffixed `لۇشيەن`‎ and for `ۋىيېنا`‎. If you
normalized a corpus with 1.0.0 or 1.0.1, re-run it.

## [1.0.0] — 2026-08-18

First public release.

### Added

- `uyghur_normalizer.py` — three ordered passes (calque → era → imla_loan) with
  an opt-in fourth pass for model-specific fixes (`--fix-map`).
- Suffix re-derivation against the replacement: vowel harmony, voicing
  assimilation, vowel-final versus consonant-final, and raising between
  suffixes. Where the derivation is not safe the tool declines and reports
  rather than guessing.
- Rule flags `nosfx` and `raise` (optional third TSV column).
- Per-pass switches `--no-calque`, `--no-era`, `--no-loan`.
- `check_new_rules.py` — vets a batch of proposed rules against the existing
  maps and against itself before anything is appended.
- `normalizer/calque_map.tsv` — 51 rules.
- `normalizer/era_map.tsv` — 1,245 rules. Pre-2009 `ىيى` forms to the 2009
  `ىيە` standard. 163 confirmed directly against [4], 1,082 by class rule,
  5 exceptions recorded where [4] mapped toward `ى`.
- `normalizer/imla_loan_map.tsv` — 873 rules. Loanword shape per the rule prose
  of [4] §V.3 (hiatus) and §IX.2.1–4 (initial clusters), arbitrated word by word
  against [1] and [2]. The example word lists inside the rule prose carry
  transcription noise and were not used as evidence.
  - 769 rules in the initial build.
  - 95 country, capital and language names added 2026-08-17, aligned from [3]
    against [4].
  - 9 loanword forms added 2026-08-18.
- `tests/test_suffix.py`, `tests/test_maps.py` — 46 tests. Map invariants and
  pipeline idempotence run in CI on every push.

### Not included

- `كىڭستون → كىڭستوۋن` (Kingstown) was dropped from the 2026-08-17 batch. The
  2009 spelling of Kingston is identical to the 2006 spelling of Kingstown, so
  the rule would corrupt every correctly-spelled Kingston. `كىنگستون → كىڭستون`
  is kept. Caught by the idempotence test.
- Terminology preferences among forms that are all attested. The Cold War is
  written at least three ways in published Uyghur, and choosing between them is
  an editorial act, not a correction.
