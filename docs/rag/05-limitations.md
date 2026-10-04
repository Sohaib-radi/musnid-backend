---
id: limitations
title: Known limitations
sidebar_position: 5
description: Known limitations of the extraction and retrieval.
---

# Known limitations

- Quran verses are replaced by `[آية]`: the private-use glyphs cannot be mapped to text
  without the QCF4 font tables. The verse reference ("[يس: 40]") is kept.
- The glyph U+F072 of `KFGQPCArabicSymbols01` follows "النبي" 7 times and may be a ﷺ
  variant; like every glyph of that font, it is removed.
- Poetry lines keep the book's spacing and tatweel; some hemistichs are joined
  ("شَـيْءإِذَا").
- Letter spacing in the PDF can leave a stray space inside a word, e.g. the title of
  #246 "أتب اعِ" for "أتباعِ".
- `LOW_THRESHOLD` (0.30) rests on three queries until the 60-question evaluation.
- The quote check proves that a quote exists in the evidence, not that it states the
  sentence: 1 unsupported claim in 12 sentences remained with gpt-4o as verifier.
- Quotes under 10 words must still match exactly (90% of fewer than 10 words leaves no
  room), so a short quote with reordered words drops its sentence.
- Sentences dropped by the quote or entailment check are kept in the flow state only, not
  saved on the `Interaction`, so a past drop cannot be inspected afterwards.
- Coverage strictness ("full" for questions the book does not ask exactly) is calibrated
  on 2026-10-06.
- `keywords` is empty: the book has no keyword lists.
- Numbers come from order, not from the garbled "المسألة (n)" labels.
- 2 questions have no separate question text, 2 no summary, 1 no detailed answer (as in
  the book).
