---
id: development-log
title: Development log
sidebar_position: 4
description: Problems met while building the RAG pipeline and how they were fixed.
---

# Development log

| Date | Problem | Fix |
| --- | --- | --- |
| 2026-10-04 | Lam-alef ligatures extracted reversed, indistinguishable from a genuine "ال" in text | Detected from character boxes: the ligature's alef has zero width |
| 2026-10-04 | Spans and punctuation in visual order | Lines rebuilt from character x positions; LTR runs reversed back; brackets mirrored |
| 2026-10-04 | Tanween rule added a second alef to "جدًّا" (regex backtracked into the shadda) and an alef before ى in "هدًى" | Possessive quantifier; lookahead on alef and alef maksura |
| 2026-10-04 | Alternative phrasings merged | The bullet "3" sits 6 pt off the text baseline and formed its own line; a bullet-only line now marks the next line |
| 2026-10-04 | ﷺ dropped from a title (set in a body font on the title line) | Title keeps every character except the "المسألة" label |
| 2026-10-04 | Validator flagged 255 questions for "unrepaired ligatures" | It matched the correct "الأ…"; it now flags two adjacent alefs |
| 2026-10-04 | "الدَّلاالت" in 3 questions | In-word "لاال" repaired to "لالا" |
