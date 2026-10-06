---
id: sources-and-credits
title: Sources and credits
sidebar_position: 3
description: The knowledge sources Musnid answers from, the AI services it calls, the tools used to build it, and where the licenses of its software are listed.
---

# Sources and credits

## Knowledge sources

Musnid answers only from these sources. Both come from the competition's official
reference document («المرجعية والحزمة العلمية والبيانات - محدث»).

| Source | What it is | How it is used | Notes |
| --- | --- | --- | --- |
| **«بيِّنات: أسئلة منتقاة حول الإسلام»** (Bayyinat) | A book of selected questions about Islam with vetted answers, proposed by the competition. Public page: [dawa.center/file/7937](https://dawa.center/file/7937) | Extracted into 263 questions and 1,432 searchable chunks; every sentence of an answer quotes it and links to its page ([RAG pipeline](rag/02-pipeline.md)) | The book's text is not redistributed in this repository (`data/` is git-ignored); it is downloaded from its public page |
| **Official glossary** («نماذج قاموس المصطلحات الأساسية») | Ten core terms and how to explain and translate them, page 7 of the competition's reference document | One chunk per term, given to the writer first when it matches ([Official glossary](rag/07-official-glossary.md)) | Cited to askers as «نماذج قاموس المصطلحات الأساسية: <term>» |

## Repositories

| Repository | Content |
| --- | --- |
| [musnid-backend](https://github.com/Sohaib-radi/musnid-backend) | API, admin, RAG, AI agents, Telegram bot (this repository) |
| [musnid-frontend](https://github.com/Sohaib-radi/musnid-frontend) | The website: asking, history, user and center dashboards |

## AI services

| Service | Model | Role |
| --- | --- | --- |
| OpenAI | `gpt-4o-mini` | Classifier, writer, translation of questions and answers |
| OpenAI | `gpt-4o` | Verifier and entailment check |
| OpenAI | `text-embedding-3-small` | Embeddings of the sources and of search queries |

The models are configured in the admin (AI settings); keys are stored encrypted
([Provider API keys](reference/api-keys.md)).

## Tools used to build Musnid

| Tool | Role |
| --- | --- |
| **Claude Code** (Anthropic) | AI coding assistant used throughout development: code, tests, translations and documentation, under the author's direction and review. Commits it helped write carry a `Co-Authored-By: Claude` line. |
| Django, Django REST Framework, CrewAI, Unfold and the other open-source packages | The application's framework and libraries, listed with their versions and licenses in the [technology stack](technology-stack.md) |
| Readex Pro typeface | Admin typeface, SIL Open Font License 1.1 (`OFL.txt` alongside the fonts) |

## Licenses

- Every dependency's license is listed in the [technology stack](technology-stack.md),
  taken from each package's metadata.
- The project itself does not declare a license yet.
