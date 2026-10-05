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
from collections import Counter
from difflib import SequenceMatcher
from types import SimpleNamespace

from crewai.flow.flow import Flow, listen, router, start
from django.conf import settings
from django.db import connection
from pydantic import BaseModel

from agents.replies import fixed_reply, notes
from knowledge.normalize import normalize
from knowledge.services.search import get_evidence, search

# CrewAI's first-run trace prompt is declined in AgentsConfig.ready(), before this
# import of CrewAI (agents/tracing.py).

SEARCH_K = 8
CITATION = re.compile(r'\s*\[Q(\d+)\]')
SECRET = re.compile(r'(sk-[A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]+|(Bearer\s+)\S+')
MIN_QUOTE_CHARS = 15
# A quote matches when this share of its words appears, in order, in one passage of
# the evidence: the writer may fix an extraction typo or change a word or two. A
# quote under 10 words must still match exactly. Entailment checks support anyway.
QUOTE_MATCH_PERCENT = 90
NON_WORD = re.compile(r'[^\w\s]|_')


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
    # Comparable text (see _comparable) of each evidence question, to find a quote's source.
    evidence_by_number: dict[int, str] = {}
    coverage: str = ''
    answer: str = ''
    citations: list[int] = []
    decision: str = ''
    error: str = ''
    tokens_in: int = 0
    tokens_out: int = 0
    sentences: list[dict] = []  # kept sentences: text (no markers), quote, source number
    dropped: list[dict] = []  # sentences removed by the quote or entailment check, with the reason


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
        chunks = get_evidence(self.state.evidence_numbers)
        texts = {}
        for chunk in chunks:
            texts.setdefault(chunk.question_number, []).append(chunk.text)
        self.state.evidence_by_number = {number: _comparable('\n'.join(parts)) for number, parts in texts.items()}
        self.state.evidence = '\n\n'.join(
            f'[Q{chunk.question_number}] {chunk.text}' for chunk in chunks
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
            self.state.sentences = [
                {'text': CITATION.sub('', sentence.text).strip(), 'quote': sentence.quote, 'number': number}
                for sentence, number in kept
            ]
            self.decide(' '.join(sentence.text.strip() for sentence, _number in kept), verified.coverage)
        except Exception as error:
            self._fail('answer crew', error)
            self._fixed('abstain')

    @listen('out_of_scope')
    def reply_out_of_scope(self):
        self._fixed('out_of_scope')

    @listen('refer')
    def reply_refer(self):
        self._fixed('refer', reply='refer_personal')  # level D: a ruling on the asker's own situation

    @listen('abstain')
    def reply_abstain(self):
        self._fixed('abstain')

    # Decision

    def quoted(self, sentences):
        """
        Keep the sentences whose quote really is in the evidence, each paired with
        the number of the evidence question the quote comes from.

        Quotes are compared after Arabic normalization and with punctuation
        removed, so diacritics or punctuation differences do not matter, and
        ``quote_matches`` tolerates a few changed words. The quote must lie within
        one question's evidence; that question, found by code, is the sentence's
        source (the writer's [Q<n>] marker is not trusted for it). A quote shorter
        than ``MIN_QUOTE_CHARS`` or not found drops its sentence. Quotes must be in
        the evidence's language (Arabic): a translated or paraphrased quote cannot
        match, so it counts as missing. The level-C sentence is the writer's, so it
        needs a quote too.
        """
        kept = []
        for sentence in sentences:
            number = self._quote_source(_comparable(sentence.quote))
            if number is None:
                self._drop(sentence, 'quote')
            else:
                kept.append((sentence, number))
        return kept

    def _quote_source(self, quote):
        """The first evidence question (in ranking order) containing ``quote``, or None."""
        if len(quote) < MIN_QUOTE_CHARS:
            return None
        for number in self.state.evidence_numbers:
            text = self.state.evidence_by_number.get(number, '')
            if text and quote_matches(quote, text):
                return number
        return None

    def entailed(self, kept):
        """
        Keep the ``(sentence, number)`` pairs whose quote states the sentence's
        claim, judged by ONE batched request to the verifier model
        (``check_entailment``). Failures propagate and end in the fixed abstain.
        """
        if not kept:
            return []
        check = self.entailment or _default_entailment
        verdicts, usage = check([(sentence.text, sentence.quote) for sentence, _number in kept])
        self._count_tokens(SimpleNamespace(token_usage=usage))
        supported = []
        for pair, verdict in zip(kept, verdicts):
            if verdict == 'supported':
                supported.append(pair)
            else:
                self._drop(pair[0], 'entailment')
        return supported

    def _drop(self, sentence, reason):
        """Record a removed sentence; saved on the Interaction for review."""
        self.state.dropped.append({'text': sentence.text, 'quote': sentence.quote, 'reason': reason})

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
            self._fixed('refer', reply='refer_no_evidence')  # the verified sources do not support an answer
            return
        self.state.decision = 'partial' if coverage == 'partial' else 'answer'
        notes_text = [note['text'] for note in notes(self.state.decision, self.state.level, self.state.language)]
        self.state.answer = '\n\n'.join([text, *notes_text])

    # Helpers

    def _fixed(self, kind, reply=None):
        """
        End with decision ``kind`` and a fixed reply; no sentence of the writer is shown.

        ``reply`` picks a more precise fixed text than ``kind``'s, such as why a
        question is referred; the decision stays ``kind``.
        """
        self.state.answer = fixed_reply(reply or kind, self.state.language)
        self.state.decision = kind
        self.state.sentences = []

    def _fail(self, step, error):
        self.state.error = mask_secrets(f'{step}: {type(error).__name__}: {error}')

    def _count_tokens(self, output):
        usage = getattr(output, 'token_usage', None)
        self.state.tokens_in += getattr(usage, 'prompt_tokens', 0) or 0
        self.state.tokens_out += getattr(usage, 'completion_tokens', 0) or 0


def quote_matches(quote, evidence):
    """
    True when ``QUOTE_MATCH_PERCENT`` of the quote's words appear, in order, in one
    passage of ``evidence``. Both arguments are ``_comparable`` text.

    The passage may hold as many extra words as the quote may miss, so a match is
    a lightly reworded copy of one place, never words gathered from across the
    evidence. Words are matched in order with ``difflib.SequenceMatcher``; windows
    without enough shared words are skipped before it runs.
    """
    if quote in evidence:
        return True
    words, source = quote.split(), evidence.split()
    needed = -(-len(words) * QUOTE_MATCH_PERCENT // 100)  # ceiling, in integers
    if needed >= len(words):
        return False
    width = len(words) + (len(words) - needed)
    wanted = Counter(words)
    for start in range(max(1, len(source) - width + 1)):
        window = source[start:start + width]
        if window[0] not in wanted or sum((wanted & Counter(window)).values()) < needed:
            continue
        matcher = SequenceMatcher(None, words, window, autojunk=False)
        if sum(block.size for block in matcher.get_matching_blocks()) >= needed:
            return True
    return False


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
