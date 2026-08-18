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

## [1.1.0] — unreleased

## [1.0.1] — 2026-08-18
DOI: [10.5281/zenodo.22000837](https://doi.org/10.5281/zenodo.22000837)

## [1.0.0] — 2026-08-18
Not archived — the release predates Zenodo integration.

First public release.

Source numbers [1]–[4] refer to the four reference works listed under
[Sources](../../#sources) in the README.

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
- `normalizer/era_map.tsv` — 1,245 rules. Pre-2009 `ىيى`‎ forms brought to the
  2009 `ىيە`‎ standard: 163 confirmed directly against [4], 1,082 by class
  rule, and 5 exceptions recorded where [4] mapped toward `ى`‎.
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

- Kingstown, `كىڭستون → كىڭستوۋن`‎, was dropped from the 2026-08-17 batch.
  The 2009 spelling of Kingston is identical to the 2006 spelling of Kingstown,
  so the rule would corrupt every correctly-spelled Kingston. Kingston,
  `كىنگستون → كىڭستون`‎, is kept. Caught by the idempotence test.
- Terminology preferences among forms that are all attested. The Cold War is
  written at least three ways in published Uyghur, and choosing between them is
  an editorial act, not a correction.
