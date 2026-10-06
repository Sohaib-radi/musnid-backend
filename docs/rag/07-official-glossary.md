---
id: official-glossary
title: Official glossary
sidebar_position: 7
description: The competition's official glossary of core terms as a knowledge source, how it is searched and cited, and the writer rules that use it.
---

# Official glossary

The competition's reference document («المرجعية والحزمة العلمية والبيانات - محدث», page 7,
«نماذج قاموس المصطلحات الأساسية») defines how ten core terms must be explained and
translated. It is now a knowledge source next to Bayyinat.

## Source

| Item | Value |
| --- | --- |
| Document | slug `official-glossary`, title «المرجعية العلمية للتحدي — نماذج قاموس المصطلحات الأساسية (ص 7)», language `ar` |
| License note | From the competition's official reference document (المرجعية والحزمة العلمية والبيانات - محدث), page 7 |
| Chunks | one per term (10), kind `glossary`, text «<term> (<english>): <rule>», metadata `{term, english}`, embedded with `text-embedding-3-small` |
| Numbers | reserved `9001`–`9010` (Bayyinat ends at 263), so `[Q<n>]` citations never collide |
| Data and loading | `knowledge/glossary.py` (`TERMS`); `manage.py ingest_glossary` (idempotent) |

Terms: الإسلام (Islam), التوحيد (Tawhid / Oneness of God), العبادة (Worship), النبوة
(Prophethood), الوحي (Revelation), الشريعة (Sharia / Islamic law and guidance), الحديث
(Hadith), السنة (Sunnah), الفتوى (Fatwa), الدعوة (Da'wah / Invitation to Islam).

## Retrieval and citation

- One embedding of the search query serves two searches: Bayyinat (glossary chunks
  excluded, unchanged rules) and the glossary (top 3 terms).
- Every glossary term scoring at least `LOW_THRESHOLD` (0.30) goes into the evidence
  **before** the Bayyinat evidence. The flow abstains only when neither source passes.
- A sentence quoted from a glossary term shows the source «نماذج قاموس المصطلحات الأساسية:
  <term>», with no Bayyinat page or PDF link.
- The entailment check knows the format: «term (English): rule» states the English
  equivalent.

## Writer rules

- Term and definition questions: a simple explanation first, then the term. Translations
  copy exactly the English equivalent of the glossary entry and keep the original term.
- Order: framing sentences of the evidence first, then the direct answer, then the reasons;
  never open a sensitive answer with its most controversial sentence.

## Validation (2026-10-06, `ask_test`, prompt version `fe78c263d3c8` for the last run)

| Question | Result |
| --- | --- |
| ما معنى التوحيد لشخص لم يسمع بالمصطلح من قبل؟ | `answer`, evidence 9002, 9005, 2, 36, 63; first sentence cited [Q9002]: «التوحيد (Tawhid / Oneness of God) … إفراد الله بالربوبية والألوهية…» |
| Translate التوحيد into English | first run `refer` (entailment rejected the translation sentence); after the entailment rule and the exact-equivalent rule: «التوحيد is translated as Tawhid or Oneness of God [Q9002].» |
| لماذا لا يبيح الإسلام للمرأة أن تكون رأس الدولة؟ | `answer`; first sentence [Q218] «الإسلام اهتم بالمرأة وحفظ حقوقها ومكانتها وكرامتها…», then the ruling |
| هل انتشر الإسلام بالسيف؟ | `answer`; first sentence [Q229] «الإسلام لم ينتشر بالسيف، وإنما انتشر بالدعوة والحجة.» |

## Limitations

- The term questions were run once each; answers vary between runs.
- The glossary's rules are guidance for explaining terms, not answers to questions; a
  question about a term not in the list falls back to Bayyinat only.
- Production needs `ingest_glossary` once after deploying (see the deployment page).
