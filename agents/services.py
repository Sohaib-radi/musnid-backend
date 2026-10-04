"""
``ask()``: answer a question with the flow and save the full trace.

Every question is saved with its ``Interaction`` (decision, retrieval,
citations, model, prompt version, latency, tokens, masked error), owned by
the default center. Without a default center nothing can be saved, so the
fixed abstain is returned with an unsaved interaction.
"""

import time

from agents.crews import prompt_version
from agents.flow import AskFlow, fixed_reply, mask_secrets
from core.models import AISettings, Center
from knowledge.embeddings import OpenAIEmbedder
from qa.models import Interaction, Question


def ask(text, session_id='', embedder=None, classify_crew=None, answer_crew=None):
    """
    Answer ``text`` and return the saved ``Interaction``.

    ``interaction.answer_text`` is what the asker sees. Crews and embedder can
    be injected (tests); by default the real ones are used.
    """
    started = time.monotonic()
    flow = AskFlow(embedder or OpenAIEmbedder(), classify_crew=classify_crew, answer_crew=answer_crew)
    try:
        flow.kickoff(inputs={'question': text})
    except Exception as error:  # a failure outside the steps: same fixed abstain
        flow.state.error = flow.state.error or mask_secrets(f'flow: {type(error).__name__}: {error}')
    state = flow.state
    if not state.decision:
        state.decision = 'abstain'
        state.answer = fixed_reply('abstain', state.language)
    interaction = Interaction(
        level=state.level, search_query=state.search_query, retrieved=state.retrieved,
        evidence_question_numbers=state.evidence_numbers, answer_text=state.answer,
        citations=state.citations, decision=state.decision, verifier_verdict=state.coverage,
        model_name=AISettings.load().chat_model, prompt_version=prompt_version(),
        latency_ms=int((time.monotonic() - started) * 1000),
        tokens_in=state.tokens_in, tokens_out=state.tokens_out, error=state.error,
    )
    center = Center.objects.filter(is_default=True).first()
    if center is None:
        interaction.error = (interaction.error + '\n' if interaction.error else '') + 'no default center'
        interaction.decision = Interaction.Decision.ABSTAIN
        interaction.answer_text = fixed_reply('abstain', state.language)
        return interaction
    question = Question.objects.create(center=center, text=text, lang=state.language, session_id=session_id)
    interaction.question = question
    interaction.save()
    return interaction
