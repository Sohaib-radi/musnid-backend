"""
Translating questions for the specialists (the translation crew's first use).

A question reaches specialists who may work in another language: the notice shows
the original and a translation into each specialist's language. One structured
call to the chat model per language, saved on ``Question.translations``, so a
language is translated once whatever the number of specialists. A failure returns
``None`` and is logged: the notice is then sent with the original only.

This module does not import CrewAI at import time (``build_llm`` does, lazily),
so channels can import it during app setup.
"""

import logging

from pydantic import BaseModel, Field

from agents.crews import build_llm
from core.services import credentials

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {'ar': 'Arabic', 'en': 'English', 'fr': 'French'}

TRANSLATION_PROMPT = """You translate questions about Islam for scholars.
Translate the user's text into {language}. Rules:
- Faithful: keep every detail and the asker's wording; add, remove or explain nothing.
- Never answer the question and never comment on it.
- Quran verses and hadith quoted in Arabic stay in Arabic, followed by their translation in parentheses.
- Religious terms stay consistent (salah, zakat, fatwa, ...): keep the usual term of the
  target language, with the Arabic term in parentheses the first time when it helps.
- Return only the translation."""


class Translation(BaseModel):
    """Output of the translation call."""

    text: str = Field(description='The translation, nothing else.')


def translate(text, language):
    """``text`` translated into ``language`` (ar, en, fr); ``None`` without an OpenAI key or when the call fails."""
    if not credentials.get_openai_key():
        return None
    try:
        llm = build_llm(Translation)
        result = llm.call(
            [{'role': 'system', 'content': TRANSLATION_PROMPT.format(language=LANGUAGE_NAMES[language])},
             {'role': 'user', 'content': text}],
            response_model=Translation,
        )
        if isinstance(result, str):
            result = Translation.model_validate_json(result)
        return result.text.strip() or None
    except Exception as error:  # a missing translation must never block the notice
        logger.warning('Translation into %s failed: %s', language, type(error).__name__)
        return None


def translate_question(question, language):
    """
    The question's text in ``language``: the original when it is already in it, else a
    saved or new translation (saved on ``question.translations``); ``None`` on failure.
    """
    if language == question.lang:
        return question.text
    if language in question.translations:
        return question.translations[language]
    translated = translate(question.text, language)
    if translated:
        question.translations = {**question.translations, language: translated}
        question.save(update_fields=['translations', 'updated_at'])
    return translated
