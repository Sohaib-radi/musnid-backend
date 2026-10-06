# Musnid documentation

Musnid answers questions about Islam **only from vetted sources**, with every sentence
linked to the passage that supports it. Questions the AI must not answer (personal rulings,
topics the sources do not cover) are sent, at the asker's choice, to **centers of
specialists**, who answer them from Telegram or their dashboard.

This folder is the complete technical documentation of the backend. Every page is plain
Markdown and reads directly on GitHub.

The website that calls this backend is a separate repository:
**[musnid-frontend](https://github.com/Sohaib-radi/musnid-frontend)**. Its integration
contract is in [Frontend integration](#frontend-integration).

> [!IMPORTANT]
> **Crucial:** a center registered on the website must be **approved** before its center
> admin can use the center dashboard, and made the **default center** to receive questions
> in Telegram. See [Approve a center](guides/approve-a-center.md).

## Start here (jury and first-time readers)

| Step | Read | What you learn |
| --- | --- | --- |
| 1 | [Introduction](intro.md) | What is built today, feature by feature |
| 2 | [How a question is answered](architecture/decisions/0016-question-answering-flow.md) | The flow: classify, search, write, verify, decide |
| 3 | [RAG pipeline](rag/02-pipeline.md) and [validation](rag/03-validation.md) | From the book's PDF to cited answers, with measured results |
| 4 | [Telegram bot](reference/telegram-bot.md) | How specialists receive and answer questions, with a real example |
| 5 | [Admin](reference/admin.md) | What a platform administrator sees: every question, its evidence and checks |
| 6 | [Fine-tuning dataset](rag/06-finetuning-dataset.md) | How reviewed answers become training data |
| 7 | [Sources and credits](sources-and-credits.md) | Where the answers come from, and the tools used |

## How it works, in one picture

```text
Asker (website) ─► 1. Classifier (AI): language, level, Arabic search query
                     ├─ personal ruling / out of scope ─► fixed reply (+ specialist offer)
                     ▼
                   2. Search (pgvector): official glossary + Bayyinat book
                     ▼
                   3. Writer (AI): answers ONLY from the evidence, every claim cited
                     ▼
                   4. Verifier (AI) + code checks: exact quotes, entailment, main ask
                     ▼
                   5. Decision (code): answer · partial · refer
                     ▼
Asker sees each sentence with its quote and source.
If the AI does not answer: "Ask a specialist now" (live) or "Save as a ticket"
  ─► Telegram: every linked specialist of the center, in their language, with a
     translation ─► first answer wins ─► the asker sees it, signed by the center.
```

The AI writes and judges; **code decides**. Refusals, referrals and notes are fixed,
translated texts, never generated.

## Sections

### Guides (step by step, with screenshots)

| Guide | For |
| --- | --- |
| [Approve a center](guides/approve-a-center.md) | Platform administrators: approve a registered center and make it the default |

### Getting started

| Page | About |
| --- | --- |
| [Local development](getting-started/local-development.md) | Python 3.12 virtualenv, PostgreSQL in Docker, running Django |
| [Docker](getting-started/docker.md) | Compose services and the application image |
| [Configuration](getting-started/configuration.md) | Every environment variable, defaults and parsing rules |
| [Deployment](getting-started/deployment.md) | Production on one VPS at api.musnid.online, step by step |

### Architecture

| Page | About |
| --- | --- |
| [Data model](architecture/data-model.md) | Entities, relations and database constraints |
| [Tenancy](architecture/tenancy.md) | How data is scoped to centers and reached through memberships |
| [Decision records (ADR)](#decision-records) | Every significant design choice, with its context and consequences |

### RAG (retrieval-augmented generation)

| Page | About |
| --- | --- |
| [Extraction findings](rag/01-extraction-findings.md) | Measured facts about the Bayyinat PDF |
| [Pipeline and decisions](rag/02-pipeline.md) | Processing stages from PDF to search results |
| [Validation results](rag/03-validation.md) | Measured results of extraction, ingestion and search |
| [Development log](rag/04-development-log.md) | Problems met and how they were fixed, with measurements |
| [Known limitations](rag/05-limitations.md) | What the pipeline does not do yet |
| [Fine-tuning dataset](rag/06-finetuning-dataset.md) | Data kept for training, the export and its formats |
| [Official glossary](rag/07-official-glossary.md) | The competition's glossary of core terms as a knowledge source |

### Reference

| Page | About |
| --- | --- |
| [REST API](reference/api.md) | Every endpoint, request, response and error code |
| [Models](reference/models.md) | Every model, field, queryset, constraint and service |
| [Admin](reference/admin.md) | Every admin page, list, filter, action and guide |
| [Telegram bot](reference/telegram-bot.md) | Linking, notices, answering, languages |
| [Provider API keys](reference/api-keys.md) | How OpenAI keys are stored encrypted and revoked |

### Frontend integration

| Page | About |
| --- | --- |
| [Authentication and routing](frontend/authentication.md) | Registration, login, tokens, routing, user language |
| [Dashboards API](frontend/dashboards.md) | User and center dashboards, Telegram connection, asking a specialist |

### Development

| Page | About |
| --- | --- |
| [Testing](development/testing.md) | Running the suite and what each test module covers |
| [Translations](development/translations.md) | Arabic and French workflow, glossary, right-to-left |
| [Migrations](development/migrations.md) | Migration history and conventions |
| [Technology stack](technology-stack.md) | Every dependency with its version, role and license |
| [Sources and credits](sources-and-credits.md) | Knowledge sources (Bayyinat, official glossary), AI services, tools used to build Musnid (Claude Code) |

### Decision records

| ADR | Decision |
| --- | --- |
| [0001](architecture/decisions/0001-python-3-12.md) | Python 3.12 |
| [0002](architecture/decisions/0002-custom-user-model.md) | Custom user model |
| [0003](architecture/decisions/0003-pgvector-in-initial-migration.md) | pgvector enabled in the initial migration |
| [0004](architecture/decisions/0004-single-default-center.md) | A single default center |
| [0005](architecture/decisions/0005-explicit-center-scoping.md) | Explicit center scoping |
| [0006](architecture/decisions/0006-email-login.md) | Email as the login identifier |
| [0007](architecture/decisions/0007-membership-links-users-to-centers.md) | Memberships link users to centers |
| [0008](architecture/decisions/0008-unfold-admin-theme.md) | Unfold admin theme |
| [0009](architecture/decisions/0009-translations-in-every-change.md) | Translations in every change |
| [0010](architecture/decisions/0010-jwt-authentication.md) | JWT authentication |
| [0011](architecture/decisions/0011-api-design.md) | API design |
| [0012](architecture/decisions/0012-cors-policy.md) | CORS policy |
| [0013](architecture/decisions/0013-center-registration-with-review.md) | Center registration with review |
| [0014](architecture/decisions/0014-encrypted-api-keys.md) | Encrypted API keys |
| [0015](architecture/decisions/0015-knowledge-base-and-retrieval.md) | Knowledge base and retrieval |
| [0016](architecture/decisions/0016-question-answering-flow.md) | Question-answering flow |
| [0017](architecture/decisions/0017-anonymous-ask-api.md) | Anonymous, synchronous ask API |
| [0018](architecture/decisions/0018-single-vps-deployment.md) | Single-VPS deployment behind nginx |
| [0019](architecture/decisions/0019-link-questions-to-logged-in-askers.md) | Questions linked to logged-in askers |
| [0020](architecture/decisions/0020-answer-revisions.md) | Specialists revise answers |
| [0021](architecture/decisions/0021-referral-tickets.md) | Referral tickets, sent at the asker's choice |
| [0022](architecture/decisions/0022-telegram-channel.md) | Telegram channel |
| [0023](architecture/decisions/0023-answer-from-telegram.md) | Answering from Telegram |
| [0024](architecture/decisions/0024-admin-for-platform-administrators.md) | The admin is for platform administrators only |

## Keeping this index current

Every new page in `docs/` is added to this index in the same commit (rule in
[CLAUDE.md](../CLAUDE.md)).
