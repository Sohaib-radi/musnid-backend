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
        'An exact, contiguous passage copied from the evidence (in the evidence language) that '
        'states what the sentence says. Empty if there is none: the sentence will be dropped.'
    ))


class VerifiedAnswer(BaseModel):
    """
    Output of the answer crew: the kept sentences with their supporting quotes.

    The flow checks every quote against the evidence and drops sentences whose
    quote is missing or not found, so support is enforced by code, not trusted.
    """

    sentences: list[SupportedSentence] = Field(description='The sentences of the answer that the evidence supports.')
    coverage: Literal['full', 'partial', 'none'] = Field(description='How far the evidence answers the question.')


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
