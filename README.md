# uyghur-normalizer
[![DOI](https://zenodo.org/badge/1338525628.svg)](https://doi.org/10.5281/zenodo.22000836)

Normalizes Uyghur text (Arabic script) to the 2009/2011 orthographic standard,
and replaces terminology calqued from Chinese with Uyghur equivalents.

Two files, no dependencies, no network. Python 3.9+.

```bash
python uyghur_normalizer.py --in text.txt            # scan: report only
python uyghur_normalizer.py --in text.txt --apply    # write text_fixed.txt
```

It never edits in place, and by default it writes nothing at all.

---

## What it does

Three passes, in a fixed order:

| pass | map | fixes |
|---|---|---|
| 1 | `calque_map.tsv` | terminology calqued from Chinese |
| 2 | `era_map.tsv` | pre-2009 spellings |
| 3 | `imla_loan_map.tsv` | loanword shape under the 2009 reform |

The order is load-bearing. Pass 1 runs first so its replacements are themselves
normalized by passes 2–3; pass 3 consumes pass 2's output.

Each pass can be switched off (`--no-calque`, `--no-era`, `--no-loan`). That
matters more than it sounds: pass 1 makes editorial changes, and someone
correcting OCR on a 1980s manuscript may want the orthography fixed and the
vocabulary of the period left exactly as printed.

A fourth, opt-in pass handles forms produced by a specific machine-translation
model. See [Pass 4](#pass-4-model-specific-fixes).

### Orthographic authority

The standard followed throughout is the **2009 orthography dictionary**,
*Hazirqi zaman Uyghur edebiy tilining imla lughiti (imla we teleppuz qa'idisi)*
— reference [4] below. Its rule prose and its word list are two parts of one
book, and where they disagree **the word list wins**: the example lists inside
the rule prose carry transcription noise and were not used as evidence.

The explanatory dictionaries [1] and [2] are used to arbitrate and to confirm
that a form is actually attested. The 2006 Uyghur–Chinese dictionary [3] is the
opposite kind of source: it documents the *older* spellings, so it supplies the
left-hand side of a rule, never the right.

The target is the **codified 2009 standard**, not contemporary web or diaspora
usage. The clearest case is the `ـىيە` class: this tool produces
`تېررىتورىيەسى`, not the widely-seen `تېررىتورىيىسى`. If you want to match how
Uyghur is written online today, this is the wrong tool.

---

## Suffixes

A rule matches at a word boundary and may be followed by suffixes. Concatenating
the replacement and the suffix is wrong whenever the two sides differ in vowel
harmony, final-consonant voicing, or vowel-versus-consonant ending:

```
زۇڭتۇڭلار  →  پىرېزىدېنتلار    wrong, needs -لەر
گۇڭشېدە    →  كوممۇنادە        wrong, needs -دا
داشۆگە     →  ئالىي مەكتەپگە   wrong, needs -كە
```

So the suffix is re-derived morpheme by morpheme against the replacement. There
are three outcomes:

- **safe** — both sides agree, so concatenation cannot change any allomorph.
- **rewrite** — they disagree and every morpheme is recognized; correct
  allomorphs are emitted.
- **decline** — a morpheme is unrecognized, or the replacement carries no
  harmony-bearing vowel. **The text is left untouched** and the case is
  reported.

Declining is deliberate. A normalizer that guesses is worse than one that says
it doesn't know, because a plausible wrong form is harder to find later than an
unchanged one. Everything declined is printed, and `--review` writes it to CSV
so the cases can be added to a map explicitly.

### Rule flags

An optional third column carries per-rule flags:

```
variant<TAB>standard<TAB>flags
```

**`nosfx`** — fire only on the bare form. Use when the replacement is already
inflected:

```
سوغۇق ئۇرۇش	سوغۇقچىلىق ئۇرۇشى	nosfx
```

Without it, `سوغۇق ئۇرۇشى` matches this rule with `ى` captured as a suffix, and
the possessive is applied a second time.

**`raise`** — the replacement's final `ا/ە` raises to `ى` before a suffix
(`ئامېرىكا + دا → ئامېرىكىدا`).

Raising is **off by default**, which is a deliberate and slightly surprising
choice. The rule is real and productive, but the exceptions are not marginal:
the `ـىيە` class does not raise, and in a 2009-imla map it dominates. In the era
map shipped here, 362 of the 364 `ە`-final replacements are in classes that must
not raise. Turning raising on globally would mean:

```
پارتىيى + لەر  →  پارتىيىلەر
```

— the rule returning its own input, silently undoing the reform it exists to
enforce while the report still claims a substitution. So it is opt-in, per rule.

Raising *between* suffixes (`تىبەت + تا + مۇ → تىبەتتىمۇ`) is always on and is
not affected by the flag: only the locative and dative end in `ا/ە`, and only
`مۇ` can follow them, so that case is narrow and well attested.

---

## Pass 4: model-specific fixes

Machine translation models produce forms that are not in their fine-tuning data
and cannot be fixed by correcting that data. The finding this pass exists for:
a rule was added to `calque_map.tsv`, the training corpus was verified at 100%
compliance — zero occurrences of the wrong form — and every checkpoint still
emitted it. Fine-tuning did not overwrite what the base model had already
learned.

Correcting the corpus cannot fix a form that was never in the corpus. That
requires an output-side pass:

```bash
python uyghur_normalizer.py --in output.txt --fix-map my_fixes.tsv --apply
```

There is no default path, and no map of this kind ships enabled. These rules
describe one model, not the language. `examples/output_fix_map.example.tsv`
shows the shape and the level of evidence expected — every rule cites the
checkpoint and the measured cost. Yours will be different, because your base
model is different.

**Do not add these rules to `calque_map.tsv`.** A corpus-compliance check
counts occurrences in the corpus; adding forms that were never there makes the
check report violations that do not exist.

---

## Vetting new rules

`check_new_rules.py` audits a batch of proposed rules before any of them reach a
map. It writes nothing to the maps: a clean TSV of what is safe to append, and a
CSV of everything a human has to decide.

```bash
python check_new_rules.py --xlsx new_terms.xlsx \
    --maps normalizer/*.tsv \
    --target-map normalizer/imla_loan_map.tsv \
    --out-dir review
```

Codes: `REVERSE` (an existing map already rewrites the other way — one of the
two is wrong), `CONFLICT`, `CHAIN`, `DUPLICATE`, `NAMING` (word counts differ,
so it is a terminology change rather than an orthographic one), `SUBSTRING`,
`SHORT`, `HYGIENE`.

`CHAIN` is scoped to a single map on purpose. Passes run calque → era →
imla_loan, so era producing a form that imla_loan then rewrites is the design.
A chain *within* one map is a real defect, and it is often subtler than it
looks. A worked example from this repo's own history: a dictionary batch
proposed both

```
كىنگستون → كىڭستون      (Kingston, Jamaica)
كىڭستون  → كىڭستوۋن     (Kingstown, St Vincent)
```

The 2011 spelling of Kingston is identical to the 2006 spelling of Kingstown.
No rule ordering can separate them, and the second rule would corrupt every
correctly-spelled Kingston. It was dropped. String rewriting has limits, and the
useful thing a tool can do is find them before a human does.

---

## Input formats

Plain text, `.jsonl` (rewrites `translation.ug`), and `EN:` / `UG:` benchmark
blocks (only `UG:` lines are touched) are detected automatically.

Arabic presentation forms are folded and text is NFC-normalized on load, so
badly-encoded OCR output still matches.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

`tests/test_suffix.py` covers the morphology. `tests/test_maps.py` enforces the
invariants on the map data itself: no duplicate left-hand sides, no rule mapping
a form to itself, no map rewriting into its own left-hand side, NFC throughout,
no padded fields, recognized flags only, every rule fires on its own input, and
the pipeline is idempotent — normalizing twice equals normalizing once.

The idempotence test is the one that catches real damage. It is how the Kingston
collision above was found.

---

## Limitations

- Rules are literal strings, so a form the map has never seen is not corrected.
- Vowel raising alters the stem, so `ئامېرىكىدا` does not match a rule whose
  left-hand side is `ئامېرىكا`. Inflected forms may need their own entries.
- Raised suffix allomorphs are not recognized on the *input* side: `شىزاڭدىمۇ`
  is declined rather than derived, and wants an explicit entry.
- The tool has no idea what a word means. `ئۈزۈك سەپ` and `مىللىي دۆلەت` are
  terminological preferences, not corrections, and reasonable translators
  disagree. Read `calque_map.tsv` before trusting it on your text.

---

## Maps as data

The maps are the substance here; the script is a few hundred lines of regex
around them. They were built word by word against the sources below, and the
2009 word list was treated as final throughout. Frequency-zero rules are kept:
a rule that has never fired is dormant, not wrong.

---

## Sources

Every rule in this repository is traceable to one of these four books.

**[1]** ھازىرقى زامان ئۇيغۇر تىلىنىڭ ئىزاھلىق لۇغىتى (قىسقارتىلمىسى)
*Hazirqi zaman Uyghur tilining izahliq lughiti (qisqartilmisi)*.
Sh.U.A.R. Milletler Til-Yéziq Xizmiti Komitéti (comp.); chief compilers
Hemdulla Abdurehman Imam, Perhat Nur, Esqer Abduqadir.
Shinjang Xelq Neshriyati, Ürümchi, 2011. ISBN 978-7-228-13933-0.
(1st ed. 1999, chief editors Abliz Yaqup and Ghenizat Gheyurani.)
→ Attestation and arbitration.

**[2]** ئۇيغۇر ئەدەبىي تىلىنىڭ ئىزاھلىق لۇغىتى، 1–6 توم
*Uyghur edebiy tilining izahliq lughiti*, vols. 1–6.
Compilers Abliz Yaqup, Ghenizat Gheyurani, Ismail Qadir, Hemdulla Abduraxman,
Perhat Nur, Abliz Emet, Esqer Abduqadir, Abduzahir Tahir, Ablikim Réhimjan,
Zayit Héwil. Milletler Neshriyati, Beijing, 1990–1999.
ISBN 7-105-00928-4 (vol. 1, 1990); 7-105-01431-8 (vol. 2, 1991);
7-105-01692-2 (vol. 3, 1992); 7-105-02248-5 (vol. 4, 1994);
7-105-02578-6 (vol. 5, 1996); 7-105-03227-8 (vol. 6, 1999).
→ Attestation for words absent from [1].

**[3]** ئۇيغۇرچە - خەنزۇچە لۇغەت
*Uyghurche–Xenzuche lughet*.
Sh.U.A.R. Milletler Til-Yéziq Xizmiti Komitéti (comp.); responsible editor
Yaqup Muhemmetrozi. Milletler Neshriyati, Beijing, 2006. ISBN 7-105-07803-0.
→ Source of pre-reform spellings — the left-hand side of a rule. The country
and capital names added to `imla_loan_map.tsv` were aligned from this edition
against [4].

**[4]** ھازىرقى زامان ئۇيغۇر ئەدەبىي تىلىنىڭ ئىملا لۇغىتى (ئىملا ۋە تەلەپپۇز قائىدىسى)
*Hazirqi zaman Uyghur edebiy tilining imla lughiti (imla we teleppuz qa'idisi)*.
Mirsultan Osmanof, Tahir Abduweli, Abdughappar Abduraxman, Memet'éli Abdurehim,
Anargül Abdurehim, Enwer Exmet. Shinjang Xelq Neshriyati, Ürümchi, 2009.
ISBN 978-7-228-12817-4.
**The orthographic standard followed throughout this repository.** The rule
prose cited in the map headers as the *imla qa'idisi* is the introductory
section of this book, not a separate work.

None of these are distributed here. They are in print, and a correction is far
easier to act on if it cites one of them by page.

---

## Contributing and corrections

A correction is more valuable than a new rule, and both are welcome.

**If you think a rule is wrong**, open an issue. Include the form, the rule as
it stands, what you think it should be, and a citation — book and page from the
list above. "This looks wrong to me" is a fine issue too, but it will sit until
someone can check it against a dictionary.

**If you want to add rules**, run them through `check_new_rules.py` first and
say in the pull request what it reported. Rules that arrive already vetted get
merged; rules that arrive as a raw list get vetted by whoever reviews them,
which is slower.

**Whether a form is correct is a discussion, not a patch.** Open the issue
before the pull request. The tests will tell you if a rule breaks the map; they
cannot tell you if a rule is bad Uyghur.

---

## License

Code (`uyghur_normalizer.py`, `check_new_rules.py`, `tests/`): MIT.

Map data (`normalizer/*.tsv`): CC BY 4.0.
