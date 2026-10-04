---
id: extraction-findings
title: Extraction findings
sidebar_position: 1
description: Measured facts about the Bayyinat PDF that drive the extraction rules.
---

# Extraction findings: Bayyinat

Source: `data/raw/bayyinat_ar.pdf` (not committed). All numbers measured with PyMuPDF
1.28.2 on 2026-10-04.

## Document

| Fact | Measured |
| --- | --- |
| Pages | 1,259 (481.9 × 680.3 pt) |
| First question page | index 21 (the printed page number equals the PDF page index) |
| Pages with the title font `AbdoLine` | 263, one per question |
| Pages with the label font `DINNext` | 265 |
| Labels "السؤال" / "الجواب" (DINNext) | 263 / 263 |

## Structure by font

| Font | Role |
| --- | --- |
| `AbdoLine` 16 pt | Question title (may wrap to 2 lines) |
| `DINNextLTW23-Medium` 14.5 pt | "السؤال", "الجواب" |
| `(AH)-Manal-High` ≥ 20 pt | Part, e.g. "أولًا: الإيمان بالله" |
| `(AH)-Manal-High` 16–18 pt with letters | Chapter, e.g. "1- توحيد الربوبية" |
| `(AH)-Manal-High` 13–15 pt | Section labels; "المسألة (n)" |
| `(AH)-Manal-High` 16 pt "3" | Bullet of alternative phrasings, on a baseline 6 pt off its text |
| `adwa-assalaf`, `adwaassalaf-Bold` 15 pt | Body; a bold "3" is a bullet inside answers |
| `QCF4_Hafs_*` | Quran text as private-use glyphs (U+F6FA …) |
| `KFGQPCArabicSymbols01` | Honorific glyphs (Latin letters h, n, j, r, k, i, …) |
| `icomoon`, `fotograami-zkhref`, `AGA-Arabesque` | Decorations |

Section labels (Manal 14 pt, diacritics removed), counts over the book:

| Label | Count |
| --- | --- |
| الجواب التفصيلي | 262 |
| مختصر الإجابة / مختصر الجواب | 259 / 2 |
| عبارات مشابهة للسؤال | 253 |
| مضمون السؤال | 177 |
| توصية- خاتمة الجواب / خاتمة الجواب | 112 / 7 |

The "المسألة (n)" labels come out garbled ("( ةل10 -)سأ"), so questions are numbered by
order.

## Text order and ligatures

- Spans of a line come out in arbitrary order and neutral characters in visual order:
  sentence punctuation first ("‎.إنكارُ وجودِ…"), brackets mirrored ("]40 :[يس").
  Characters carry reliable boxes, so lines are rebuilt from x positions, right to left.
- **Lam-alef ligature**: the ligature's alef has a zero-width box just before the lam,
  e.g. "الإيمان" → `ا(267.1–272.0) إ(267.1–267.1) ل(252.1–267.1)`. A genuine "ال" has two
  boxes with widths ("السؤال": `ا(403.0–406.5) ل(394.3–403.0)`). Rule: a zero-width alef
  followed by lam is swapped.
- **Allah ligature**: "هللا" in the title font, "اهلل" in the body.
- **Tanween-alef**: the alef is missing entirely ("أولً" for "أولًا").
- **Double lam-alef after shadda**: "الدَّلاالت" for "الدَّلالات" (3 questions).
- The running header (page number, book title) lies above y = 45 pt; nothing was found
  below y = 640 pt.

## Symbols

| Symbol | Measured | Rule |
| --- | --- | --- |
| ﷺ (U+FDFA) in body fonts | 1,327 regular + 246 bold spans | kept |
| `KFGQPCArabicSymbols01` glyphs | h 304, n 244, j 96, U+F068 72, r 68, k 66, i 57, p 22, q 12, o 8, U+F072 7, s 4, l 2 | removed (context: n after "عيسى", h after "عثمان", i after "عائشة", …) |
| Quran glyph runs (`QCF*`) | | replaced by one `[آية]` per run |
