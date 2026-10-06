"""
Building a fine-tuning dataset from reviewed answers (docs/rag/06-finetuning-dataset.md).

Only answers that kept their evidence (``Interaction.evidence``, saved since
2026-10-06) and ran without error are used: an example must show the model exactly
what the writer saw. Two sets, in the formats fine-tuning services expect:

- SFT (supervised): ``{"messages": [system, user, assistant]}``, where the assistant
  turn is the best known answer: a reviewer's correction, else a specialist's
  correction, else the AI answer when a reviewer marked it correct.
- DPO (preference pairs): ``{"input": {"messages": [system, user]},
  "preferred_output": [...], "non_preferred_output": [...]}``: the better answer
  (a correction) against the AI answer it replaced.

Never included: the asker (account, email, session), reviewers' names, internal
notes, answers a reviewer marked wrong.
"""

from qa.models import AnswerRevision, HumanLabel, Interaction

#: The task the examples teach; mirrors the writer's role in agents/crews (answer_crew)
SYSTEM_PROMPT = (
    'You answer questions about Islam for Musnid using only the evidence provided, which comes from '
    'vetted sources. Cite every claim with its [Q<n>] marker. Never add knowledge of your own and never '
    'quote the Quran or hadith from memory. Answer in the language of the question.'
)

#: Decisions where the AI wrote an answer (fixed replies teach nothing about answering)
ANSWERED = (Interaction.Decision.ANSWER, Interaction.Decision.PARTIAL)

#: Revisions that improve the answer itself (a specialist's answer, or a correction)
IMPROVING = (AnswerRevision.Reason.CORRECTION, AnswerRevision.Reason.SPECIALIST_ANSWER,
             AnswerRevision.Reason.CLARIFICATION)


def usable_interactions(since=None, language=None):
    """Interactions that can become examples: evidence kept, no error, an AI answer, optional filters."""
    interactions = (Interaction.objects.exclude(evidence='').filter(error='', decision__in=ANSWERED)
                    .select_related('question').prefetch_related('labels', 'question__revisions')
                    .order_by('created_at'))
    if since:
        interactions = interactions.filter(created_at__date__gte=since)
    if language:
        interactions = interactions.filter(question__lang=language)
    return interactions


def prompt_messages(interaction):
    """The system and user turns: the question and the exact evidence the writer received."""
    question = interaction.question
    user = f'Question ({question.lang or "unknown"}):\n{question.text}\n\nEvidence:\n{interaction.evidence}'
    return [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user}]


def better_answer(interaction):
    """
    The best known answer when it differs from the AI's: a reviewer's correction (newest),
    else the newest improving revision by a specialist; ``None`` when there is none.
    """
    corrections = sorted((label for label in interaction.labels.all()
                          if label.verdict == HumanLabel.Verdict.CORRECT and label.corrected_answer),
                         key=lambda label: label.updated_at, reverse=True)
    if corrections:
        return corrections[0].corrected_answer
    revisions = sorted((revision for revision in interaction.question.revisions.all()
                        if revision.reason in IMPROVING), key=lambda revision: revision.created_at, reverse=True)
    return revisions[0].shown_text if revisions else None  # in the question's language


def approved(interaction):
    """True when a reviewer marked the AI answer correct and nobody marked it wrong."""
    verdicts = {label.verdict for label in interaction.labels.all()}
    return HumanLabel.Verdict.APPROVE in verdicts and HumanLabel.Verdict.REJECT not in verdicts


def build(interactions, with_metadata=False):
    """
    Return ``(sft, dpo)``: two lists of examples (dicts ready for JSONL).

    ``with_metadata`` adds a ``metadata`` key (question uuid, language, prompt version,
    model, source) for auditing; leave it off for services that refuse extra keys.
    """
    sft, dpo = [], []
    for interaction in interactions:
        prompt = prompt_messages(interaction)
        better = better_answer(interaction)
        if better:
            target, source = better, 'correction'
            dpo.append(_with_metadata({
                'input': {'messages': prompt},
                'preferred_output': [{'role': 'assistant', 'content': better}],
                'non_preferred_output': [{'role': 'assistant', 'content': interaction.answer_text}],
            }, interaction, 'correction', with_metadata))
        elif approved(interaction):
            target, source = interaction.answer_text, 'approved_ai_answer'
        else:
            continue  # not reviewed yet, or marked wrong: not an example to learn from
        sft.append(_with_metadata({'messages': [*prompt, {'role': 'assistant', 'content': target}]},
                                  interaction, source, with_metadata))
    return sft, dpo


def _with_metadata(example, interaction, source, enabled):
    if enabled:
        example['metadata'] = {
            'question': str(interaction.question.uuid), 'language': interaction.question.lang,
            'prompt_version': interaction.prompt_version, 'model': interaction.model_name, 'source': source,
        }
    return example
