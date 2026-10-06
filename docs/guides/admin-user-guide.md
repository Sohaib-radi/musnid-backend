---
id: admin-user-guide
title: Admin user guide
sidebar_position: 2
description: How to use every page of the Musnid admin, page by page, with the common tasks first.
---

# Admin user guide

The admin is for **platform administrators** (superusers). Askers, specialists and center
admins use the website instead.

- **Address:** [api.musnid.online/admin](https://api.musnid.online/admin/). The site's
  root, api.musnid.online, opens it too.
- **Sign in** with the superuser's email and password. For the jury, they are in the
  submission form, field «وصف المشروع» of «بيانات تسليم التحكيم النهائي».
- **Language:** the user menu at the bottom of the sidebar switches between العربية,
  English and Français. Arabic reads right to left.
- **Every list has a "How to read this page" button** at the top right. It explains each
  column, badge and action of that page.

## Common tasks

| I want to… | Go to | Do |
| --- | --- | --- |
| Let a new center work | **Centers** | **Approve** on its row; tick *Also make it the default center* to send it the questions ([guide](approve-a-center.md)) |
| Choose which center receives questions | **Centers** → the center | **Make default** at the top of its page |
| See every question and what the AI did | **Questions** | Expand a row (arrow at its start), or open it |
| Correct or complete an answer | **Questions** → the question | **Revise the answer** |
| Judge the AI's answer (for evaluation and training data) | **Questions** → the question | **AI verdict** |
| Follow the questions sent to specialists | **Tickets** | Filter by status; **Assign to me** or **Close** |
| Check that Telegram messages went out | **Telegram messages** | Filter on *Failed*; **Send again** |
| Find a person's account | **Users** | Search by email or name |
| Add a specialist to a center by hand | **Memberships** | **+** (add), choose user, center and role |
| Change the AI models | **AI settings** | Edit the models and temperature |

## Centers

The centers of specialists, and their review.

- **Columns:** name, country, review status (*Pending review*, *Approved*, *Rejected*),
  active, default center, created at; **Review** shows Approve / Reject on pending rows.
- **Approve:** opens a dialog. The red card *Also make it the default center* is optional:
  ticked, the center also becomes the one that receives the questions askers send to
  specialists, and the previous default stops receiving new ones.
- **Reject:** asks for a reason, shown to the applicant.
- **Open a center:** contact details, languages served, Telegram group, review history.
  An approved center that is not the default has **Make default** at the top.
- **Suspend** a center: open it, untick **Active**, save. Its history stays. Centers are
  never deleted from the admin, because that would delete their questions and memberships.
- **Actions** (tick rows, then the action bar): approve, reject, or make the selected
  center the default (with a confirmation).

## Memberships

Who works in which center, and with which role.

- **Columns:** user, center, role (*Center admin* or *Specialist*), active, created at, left
  at. Filters: role, active, center.
- Center admins normally add their specialists from their own dashboard on the website.
  Here you can add one by hand: **+**, then user, center and role. The person must have an
  account first.
- **Offboard** (action): ends a membership with a date. Memberships are never deleted, and
  a center always keeps at least one center admin.

## Questions

Every question asked on the website, with the AI's full work.

- **The list is compact:** question, asker (email, or *Anonymous*), decision, center.
- **Expand a row** with the arrow at its start to see the rest: language, answered by (AI
  or Center), level, response time, tokens, error, ticket, follow-up number, and what the
  asker sees.
- **Decision badges:** *Answer* (green), *Partial answer* (blue), *Referred to a center*
  (amber), *Abstain* and *Out of scope* (red).
- **Search** by question text or asker email, or paste a follow-up number. **Filters:**
  decision, level, language, center, date.
- **Open a question** to see:
  - **Answer:** the text the asker saw, each kept sentence with the exact quote from the
    book that supports it, the sentences the checks removed and why, and the AI verdicts.
  - **Retrieval** (collapsed): the search query, the ranked results, and the exact evidence
    the writer received.
  - **Run** (collapsed): model, prompt version, response time, tokens, error.
  - **Revisions:** every answer written by a specialist, newest first.
- **Revise the answer** (button at the top): write the answer the asker will see, choose a
  reason and an optional internal note. The asker sees it at once, signed with the center's
  name. The AI's answer is kept for audit.
- **AI verdict** (button at the top): mark the AI answer *Correct*, *To correct* (write the
  corrected answer) or *Wrong* (write why). This feeds the evaluation and the fine-tuning
  dataset, and does not change what the asker sees.

## Tickets

The questions askers chose to send to specialists.

- **Columns:** question, mode (*Asked a specialist now*, live with a one-minute window, or
  *Saved as a ticket*), status (*Open*, *In progress*, *Answered*, *Closed without an
  answer*), reason (personal ruling, or not covered by the sources), assigned to, center,
  dates. The sidebar badge counts the open ones.
- **Filters:** status, mode, reason, assigned to, center.
- **Assign to me** (action): step in on a ticket. To answer it, open its question and use
  **Revise the answer**.
- **Close without an answer** (action): for duplicates or abusive questions; a note is
  required.
- When a specialist answers in Telegram, the ticket becomes *Answered* automatically, and
  every other specialist's message shows who answered.

## AI verdicts

Every verdict given with **AI verdict** on a question's page.

- **Columns:** question, verdict (*Correct*, *To correct*, *Wrong*), language, reviewer,
  date. Filters: verdict, language, AI decision.
- Open one to see the AI's answer next to the correction. Verdicts are read-only here.
- The `export_finetuning` command turns them into training data
  ([Fine-tuning dataset](../rag/06-finetuning-dataset.md)).

## Telegram messages

Every message the bot sent, or tried to send.

- **Columns:** date, kind (*New referral notice* with the Answer button, or *Answer
  prompt*), status (*Sent* or *Failed*), chat, question, error.
- A **Failed** message shows Telegram's reason, for example a specialist who blocked the
  bot. Tick it and use **Send again**.

## Users

Every account: askers, specialists, center admins, administrators.

- **Search** by email or name. **Filters:** active, staff, superuser, verified, language,
  group.
- Open an account to see its memberships (read-only), change its name or language, reset
  its password, or untick **Active** to deactivate it. Accounts are deactivated, not
  deleted.
- Only **superusers** can open the admin. Tick *Superuser status* only for platform
  administrators.

## Groups

Django's permission groups. Musnid does not need them for daily use, because the admin is
reserved to superusers.

## Source documents and source chunks

The knowledge the AI answers from. Both pages are read-only.

- **Source documents:** the Bayyinat book and the official glossary, with their number of
  chunks.
- **Source chunks:** each searchable piece. *Question* chunks only help find the right
  place; *Summary*, *Answer* and *Glossary term* chunks are the evidence the AI may quote.
  Filter by kind or document.

## API keys

The OpenAI keys the platform uses.

- **+** (add): a name and the key. The key is stored encrypted and never shown again; the
  list shows it masked.
- Adding a key revokes the previous one. **Revoke** (action) a key that may have leaked:
  the platform stops using it at once.

## AI settings

One page with the models: **chat model** (classifier, writer, translation), **verifier
model** (verifier and entailment check) and **temperature**. Changes apply to the next
question.

## Tokens (Security)

*Outstanding tokens* and *Blacklisted tokens* list the website's login sessions. You only
need them to investigate a security issue.

More detail on every field, filter and rule: [Admin reference](../reference/admin.md).
