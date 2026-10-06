"""Fake crews for flow tests: they return fixed outputs or raise, without any LLM."""

from types import SimpleNamespace

from agents.crews import Classification, SupportedSentence, VerifiedAnswer


class FakeCrew:
    """Stands for a CrewAI crew: ``kickoff(inputs)`` returns ``output`` or raises ``error``."""

    def __init__(self, output=None, error=None, tokens=(10, 5)):
        self.output, self.error, self.tokens = output, error, tokens
        self.inputs = []

    def kickoff(self, inputs):
        self.inputs.append(inputs)
        if self.error:
            raise self.error
        usage = SimpleNamespace(prompt_tokens=self.tokens[0], completion_tokens=self.tokens[1])
        return SimpleNamespace(pydantic=self.output, token_usage=usage)


def classified(level='B', language='ar', query='هل انتشر الإسلام بالسيف؟'):
    return FakeCrew(Classification(language=language, level=level, search_query=query))


# A passage of the fake evidence (make_question's summary), usable as a supporting quote.
QUOTE = 'لم ينتشر الإسلام بالسيف.'


def answered(answer='لم ينتشر الإسلام بالسيف [Q1].', coverage='full', quote=QUOTE, answers_main_ask=True):
    """A verifier output; ``answer`` may be a list of (text, quote) pairs."""
    pairs = answer if isinstance(answer, list) else [(answer, quote)]
    sentences = [SupportedSentence(text=text, quote=q) for text, q in pairs]
    return FakeCrew(VerifiedAnswer(main_ask='Did Islam spread by the sword?', answers_main_ask=answers_main_ask,
                                   sentences=sentences, coverage=coverage))
