"""
The question-answering flow (CrewAI Flow; ADR 0016).

    classify ─┬─ out_of_scope → fixed refusal
              ├─ level D      → fixed referral
              ├─ failure      → fixed abstain
              └─ search(k=8) ─┬─ best score < LOW_THRESHOLD or failure → fixed abstain
                              └─ evidence of the top 3 questions → answer crew → decide

``decide`` is deterministic: invalid [Q<n>] citations are removed; no valid
citation or coverage "none" → referral; "partial" → answer + fixed note;
level C → answer + fixed notice. Fixed replies are translated, never generated.
Any failure ends in the fixed abstain, with the error saved and keys masked.
"""

import re
import threading
from types import SimpleNamespace

from crewai.flow.flow import Flow, listen, router, start
from crewai.events.listeners.tracing.utils import is_first_execution, mark_first_execution_done
from django.conf import settings
from django.db import connection
from django.utils import translation
from django.utils.translation import gettext as _
from pydantic import BaseModel

from knowledge.normalize import normalize
from knowledge.services.search import get_evidence, search

# CrewAI asks "view your execution traces? [y/N]" on a machine's first run, which
# blocks a server process; the environment switches in settings do not stop it.
# Recording the decline in CrewAI's user file (what `crewai traces disable` does)
# prevents the prompt.
if is_first_execution():
    mark_first_execution_done(user_consented=False)

SEARCH_K = 8
CITATION = re.compile(r'\s*\[Q(\d+)\]')
SECRET = re.compile(r'(sk-[A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]+|(Bearer\s+)\S+')
REPLY_LANGUAGES = {'ar', 'en', 'fr'}
MIN_QUOTE_CHARS = 15
NON_WORD = re.compile(r'[^\w\s]|_')


def fixed_reply(kind, language):
    """A fixed, translated reply. ``kind``: out_of_scope, refer, abstain, partial, disagreement."""
    with translation.override(language if language in REPLY_LANGUAGES else 'en'):
        return {
            'out_of_scope': _('This service only answers questions about Islam. '
                              'Please ask a question about Islam.'),
            'refer': _('Your question needs a specialist. It has been referred to a center of '
                       'specialists, who will answer you.'),
            'abstain': _('We could not find an answer to this question in our sources. '
                         'Please rephrase it or ask a center of specialists.'),
            'partial': _('Note: our sources answer this question only in part.'),
            'disagreement': _('This matter involves scholarly disagreement; consult a specialist '
                              'for your situation.'),
        }[kind]


def script_language(text, guess):
    """
    The asker's language, with the Arabic case decided by script, not by the model.

    Text that is mostly Arabic script is "ar". The classifier's guess is kept for
    other text, except "ar", which the model sometimes returns for English
    questions (observed 2026-10-04): it falls back to "en".
    """
    letters = [char for char in text if char.isalpha()]
    arabic = sum('\u0600' <= char <= '\u06ff' for char in letters)
    if letters and arabic / len(letters) > 0.5:
        return 'ar'
    return 'en' if guess == 'ar' else guess


def mask_secrets(text):
    """Mask API keys and bearer tokens in ``text`` (for stored errors)."""
    return SECRET.sub(lambda m: f'{m.group(1)}…' if m.group(1) else f'{m.group(2)}…', text)


class QAState(BaseModel):
    """Everything the flow learns about one question; saved as an Interaction."""

    question: str = ''
    language: str = 'en'
    level: str | None = None
    search_query: str = ''
    retrieved: list[dict] = []
    evidence_numbers: list[int] = []
    evidence: str = ''
    coverage: str = ''
    answer: str = ''
    citations: list[int] = []
    decision: str = ''
    error: str = ''
    tokens_in: int = 0
    tokens_out: int = 0
    dropped: list[dict] = []  # sentences removed by the quote check, with their quote


class AskFlow(Flow[QAState]):
    """
    The flow. Crews and the embedder are injected so tests can replace them;
    by default the real crews (``agents/crews``) are built when first needed.
    """

    def __init__(self, embedder, classify_crew=None, answer_crew=None, entailment=None, **kwargs):
        # suppress_flow_events: no console panels (they print regardless of verbose).
        super().__init__(suppress_flow_events=True, **kwargs)
        self.embedder = embedder
        self.classify_crew = classify_crew
        self.answer_crew = answer_crew
        self.entailment = entailment

    # Steps

    @start()
    def classify(self):
        try:
            crew = self.classify_crew or _default_classify_crew()
            output = crew.kickoff(inputs={'question': self.state.question})
            result = output.pydantic
            self._count_tokens(output)
            self.state.language = script_language(self.state.question, result.language)
            self.state.level = result.level
            self.state.search_query = result.search_query.strip() or self.state.question
        except Exception as error:  # any failure ends in the fixed abstain
            self._fail('classify', error)

    @router(classify)
    def route(self):
        if self.state.error:
            return 'abstain'
        if self.state.level == 'out_of_scope':
            return 'out_of_scope'
        if self.state.level == 'D':
            return 'refer'
        return 'search'

    @router('search')
    def retrieve(self):
        try:
            return self._retrieve()
        finally:
            # CrewAI runs steps in worker threads; their DB connections are not
            # managed by Django's request cycle and would leak.
            if threading.current_thread() is not threading.main_thread():
                connection.close()

    def _retrieve(self):
        try:
            results = search(self.state.search_query, SEARCH_K, self.embedder)
        except Exception as error:
            self._fail('retrieval', error)
            return 'abstain'
        self.state.retrieved = [
            {'question_number': r.question_number, 'score': round(r.score, 4), 'kind': r.kind} for r in results
        ]
        if not results or results[0].score < settings.LOW_THRESHOLD:
            return 'abstain'
        self.state.evidence_numbers = [r.question_number for r in results[:settings.EVIDENCE_QUESTIONS]]
        self.state.evidence = '\n\n'.join(
            f'[Q{chunk.question_number}] {chunk.text}' for chunk in get_evidence(self.state.evidence_numbers)
        )
        return 'answer'

    # Handler names must differ from the router labels: CrewAI also triggers a
    # listener of 'answer' when a method named answer completes, which loops forever.

    @listen('answer')
    def write_answer(self):
        try:
            crew = self.answer_crew or _default_answer_crew()
            output = crew.kickoff(inputs={
                'question': self.state.question, 'language': self.state.language,
                'level': self.state.level, 'evidence': self.state.evidence,
            })
            self._count_tokens(output)
            verified = output.pydantic
            kept = self.entailed(self.quoted(verified.sentences))
            self.decide(' '.join(s.text.strip() for s in kept), verified.coverage)
        except Exception as error:
            self._fail('answer crew', error)
            self._fixed('abstain')

    @listen('out_of_scope')
    def reply_out_of_scope(self):
        self._fixed('out_of_scope')

    @listen('refer')
    def reply_refer(self):
        self._fixed('refer')

    @listen('abstain')
    def reply_abstain(self):
        self._fixed('abstain')

    # Decision

    def quoted(self, sentences):
        """
        Keep the sentences whose quote really is in the evidence.

        Quotes are compared after Arabic normalization and with punctuation
        removed, so diacritics or punctuation differences do not matter; a quote
        shorter than ``MIN_QUOTE_CHARS`` or absent from the evidence drops its
        sentence. Quotes must be in the evidence's language (Arabic): a translated
        or paraphrased quote cannot match, so it counts as missing. The level-C sentence is the writer's, so it needs a quote too.
        """
        evidence = _comparable(self.state.evidence)
        kept = []
        for sentence in sentences:
            quote = _comparable(sentence.quote)
            if len(quote) >= MIN_QUOTE_CHARS and quote in evidence:
                kept.append(sentence)
            else:
                self.state.dropped.append({'text': sentence.text, 'quote': sentence.quote, 'reason': 'quote'})
        return kept

    def entailed(self, sentences):
        """
        Keep the sentences whose quote states their claim, judged by ONE batched
        request to the verifier model (``check_entailment``). Failures propagate
        and end in the fixed abstain.
        """
        if not sentences:
            return []
        check = self.entailment or _default_entailment
        verdicts, usage = check([(s.text, s.quote) for s in sentences])
        self._count_tokens(SimpleNamespace(token_usage=usage))
        kept = []
        for sentence, verdict in zip(sentences, verdicts):
            if verdict == 'supported':
                kept.append(sentence)
            else:
                self.state.dropped.append({'text': sentence.text, 'quote': sentence.quote, 'reason': 'entailment'})
        return kept

    def decide(self, answer, coverage):
        """Apply the safeguards to the verified answer (see the module docstring)."""
        self.state.coverage = coverage
        allowed = set(self.state.evidence_numbers)
        cited = []

        def keep_valid(match):
            number = int(match.group(1))
            if number in allowed:
                cited.append(number)
                return match.group(0)
            return ''
        text = CITATION.sub(keep_valid, answer).strip()
        self.state.citations = sorted(set(cited))
        if coverage == 'none' or not cited:
            self._fixed('refer')
            return
        notes = []
        if coverage == 'partial':
            notes.append(fixed_reply('partial', self.state.language))
        if self.state.level == 'C':
            notes.append(fixed_reply('disagreement', self.state.language))
        self.state.answer = '\n\n'.join([text, *notes])
        self.state.decision = 'partial' if coverage == 'partial' else 'answer'

    # Helpers

    def _fixed(self, kind):
        self.state.answer = fixed_reply(kind, self.state.language)
        self.state.decision = kind

    def _fail(self, step, error):
        self.state.error = mask_secrets(f'{step}: {type(error).__name__}: {error}')

    def _count_tokens(self, output):
        usage = getattr(output, 'token_usage', None)
        self.state.tokens_in += getattr(usage, 'prompt_tokens', 0) or 0
        self.state.tokens_out += getattr(usage, 'completion_tokens', 0) or 0


def _comparable(text):
    """Normalized text without punctuation or extra spaces, for quote matching."""
    return ' '.join(NON_WORD.sub(' ', normalize(text)).split())


def _default_entailment(pairs):
    from agents.crews import check_entailment
    return check_entailment(pairs)


def _default_classify_crew():
    from agents.crews.classify_crew.classify_crew import ClassifyCrew
    return ClassifyCrew().crew()


def _default_answer_crew():
    from agents.crews.answer_crew.answer_crew import AnswerCrew
    return AnswerCrew().crew()
