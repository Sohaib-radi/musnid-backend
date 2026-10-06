"""
``ask()``: answer a question with the flow and save the full trace.

Every question is saved with its ``Interaction`` (decision, retrieval,
citations, model, prompt version, latency, tokens, masked error), owned by
the default center. A question the AI does not answer is sent to the
specialists only if the asker then asks for it (``qa.services.request_specialist``).
Without a default center nothing can be saved, so the fixed abstain is returned
with an unsaved interaction.

A global daily limit (``settings.ASK_DAILY_LIMIT`` questions since 00:00 UTC)
protects the OpenAI budget: past it, ``ask()`` raises ``DailyLimitReached``
before any model call and saves nothing (ADR 0017).
"""

import time

from django.conf import settings
from django.db import transaction

from agents.crews import prompt_version
from agents.flow import AskFlow, mask_secrets
from agents.replies import fixed_reply
from core.models import AISettings, Center
from knowledge.embeddings import OpenAIEmbedder
from qa.models import Interaction, Question


class DailyLimitReached(Exception):
    """The global daily limit of questions is reached; nothing was asked or saved."""


def daily_limit_reached():
    """
    True when ``settings.ASK_DAILY_LIMIT`` questions were saved since 00:00 UTC.

    Concurrent requests can pass the check together, so the limit can be exceeded
    by at most the number of requests in flight (6 with 3 workers x 2 threads).
    """
    return Question.objects.asked_today().count() >= settings.ASK_DAILY_LIMIT


def ask(text, session_id='', asker=None, embedder=None, classify_crew=None, answer_crew=None, entailment=None):
    """
    Answer ``text`` and return the saved ``Interaction``.

    Raises ``DailyLimitReached`` before any model call when the daily limit is reached.

    ``asker`` is the logged-in user who asked, or ``None`` for an anonymous asker.
    ``interaction.answer_text`` is what the asker sees. Crews and embedder can
    be injected (tests); by default the real ones are used.
    """
    if daily_limit_reached():
        raise DailyLimitReached
    started = time.monotonic()
    flow = AskFlow(embedder or OpenAIEmbedder(), classify_crew=classify_crew, answer_crew=answer_crew,
                   entailment=entailment)
    try:
        flow.kickoff(inputs={'question': text})
    except Exception as error:  # a failure outside the steps: same fixed abstain
        flow.state.error = flow.state.error or mask_secrets(f'flow: {type(error).__name__}: {error}')
    state = flow.state
    if not state.decision:
        state.decision = 'abstain'
        state.answer = fixed_reply('abstain', state.language)
        state.sentences = []
    interaction = Interaction(
        level=state.level, search_query=state.search_query, retrieved=state.retrieved,
        evidence_question_numbers=state.evidence_numbers, evidence=state.evidence, answer_text=state.answer,
        citations=state.citations, sentences=state.sentences, dropped=state.dropped,
        decision=state.decision, verifier_verdict=state.coverage,
        model_name=AISettings.load().chat_model, prompt_version=prompt_version(),
        latency_ms=int((time.monotonic() - started) * 1000),
        tokens_in=state.tokens_in, tokens_out=state.tokens_out, error=state.error,
    )
    center = Center.objects.filter(is_default=True).first()
    if center is None:
        interaction.error = (interaction.error + '\n' if interaction.error else '') + 'no default center'
        interaction.decision = Interaction.Decision.ABSTAIN
        interaction.answer_text = fixed_reply('abstain', state.language)
        interaction.sentences = []
        return interaction
    with transaction.atomic():
        question = Question.objects.create(center=center, text=text, lang=state.language, session_id=session_id,
                                           asker=asker)
        interaction.question = question
        interaction.save()
    return interaction
