"""
Shared pieces of the crews: output shapes, the LLM, the prompt version.

Output shapes are Pydantic models given to tasks as ``output_pydantic``, so a
crew returns validated data or fails (the flow then abstains). The LLM is
built from ``AISettings`` (model, temperature) and the encrypted OpenAI key.
"""

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from core.models import AISettings
from core.services import credentials

CREWS_DIR = Path(__file__).resolve().parent
LLM_TIMEOUT_SECONDS = 60


class Classification(BaseModel):
    """Output of the classify crew."""

    language: Literal['ar', 'en', 'fr', 'other'] = Field(
        description='The language the question is WRITTEN in (not the language of search_query).',
    )
    level: Literal['A', 'B', 'C', 'D', 'out_of_scope'] = Field(description='Level, see the task.')
    search_query: str = Field(description='The question rewritten in Modern Standard Arabic for search.')


class SupportedSentence(BaseModel):
    """One kept sentence of the answer and the evidence that supports it."""

    text: str = Field(description=(
        'The sentence, in the answer language, with its [Q<n>] citation marker exactly as written, '
        'e.g. "Islam spread through invitation [Q229]."'
    ))
    quote: str = Field(description=(
        'An exact, contiguous passage copied word for word from the evidence, in the evidence\'s '
        'original language (Arabic), even when the sentence is in English or French. Never translate '
        'or paraphrase it: a translated or paraphrased quote counts as missing and the sentence is '
        'dropped. Empty if there is none.'
    ))


class VerifiedAnswer(BaseModel):
    """
    Output of the answer crew: the kept sentences with their supporting quotes.

    The flow checks every quote against the evidence and drops sentences whose
    quote is missing or not found, so support is enforced by code, not trusted.
    """

    sentences: list[SupportedSentence] = Field(description='The sentences of the answer that the evidence supports.')
    coverage: Literal['full', 'partial', 'none'] = Field(description='How far the evidence answers the question.')


class EntailmentVerdicts(BaseModel):
    """Output of the entailment check: one verdict per sentence-quote pair, in order."""

    verdicts: list[Literal['supported', 'not_supported']] = Field(
        description='One verdict per numbered pair, in the same order.',
    )


ENTAILMENT_PROMPT = """You check whether quotes support sentences.
Each numbered pair has a SENTENCE (any language) and a QUOTE copied from an Arabic source.
For each pair answer "supported" only if the quote alone states the sentence's claim:
same facts, nothing added. Answer "not_supported" if the sentence adds anything the quote
does not state: a conclusion or inference ("which shows that", "مما يدل على", "this means"),
a contrast ("rather than", "instead of"), a cause, a generalization, a summary, a date,
a number, a place or any other detail. Judge meaning across languages. Ignore [Q<n>] markers.
Return exactly one verdict per pair, in order."""


def check_entailment(pairs):
    """
    Judge all ``(sentence, quote)`` pairs in ONE request to the verifier model.

    Returns:
        ``(verdicts, usage)``: one "supported"/"not_supported" per pair, and the
        call's ``UsageMetrics``.

    Raises:
        ValueError: if the number of verdicts differs from the number of pairs.
    """
    llm = build_llm(EntailmentVerdicts, model=AISettings.load().verifier_model or None)
    numbered = '\n\n'.join(f'{n}. SENTENCE: {text}\n   QUOTE: {quote}' for n, (text, quote) in enumerate(pairs, 1))
    result = llm.call(
        [{'role': 'system', 'content': ENTAILMENT_PROMPT}, {'role': 'user', 'content': numbered}],
        response_model=EntailmentVerdicts,
    )
    if isinstance(result, str):
        result = EntailmentVerdicts.model_validate_json(result)
    if len(result.verdicts) != len(pairs):
        raise ValueError(f'entailment returned {len(result.verdicts)} verdicts for {len(pairs)} pairs')
    return result.verdicts, llm.get_token_usage_summary()


def build_llm(response_format=None, model=None):
    """
    The crews' LLM, from AISettings and the active OpenAI key.

    ``response_format`` (a Pydantic model) turns on OpenAI structured outputs, so
    the API enforces the shape: without it gpt-4o-mini sometimes returned the
    JSON schema itself instead of an instance (docs/rag/04-development-log.md).
    """
    from crewai import LLM  # imported lazily: CrewAI is heavy and reads its env at import

    ai = AISettings.load()
    # timeout: a stuck provider call becomes an error (fixed abstain) instead of blocking.
    return LLM(model=model or ai.chat_model, temperature=float(ai.temperature), api_key=credentials.get_openai_key(),
               response_format=response_format, timeout=LLM_TIMEOUT_SECONDS)


def prompt_version():
    """
    Short hash of the crews' YAML and of this module (output shapes, whose field
    descriptions are part of the prompt): changes whenever a prompt changes.
    """
    digest = hashlib.sha256()
    for path in [*sorted(CREWS_DIR.glob('*/config/*.yaml')), Path(__file__)]:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]
