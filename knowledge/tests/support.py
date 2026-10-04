"""Test helpers: a deterministic fake embedder and a sample extracted question."""

import hashlib
import math

from knowledge.models import EMBEDDING_DIMENSIONS


class FakeEmbedder:
    """
    Deterministic embeddings without network: bag of hashed words, L2-normalized,
    so texts sharing words are close in cosine distance.
    """

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def embed(self, texts):
        if self.fail:
            raise RuntimeError('embedding failed')
        self.calls.append(list(texts))
        return [self.vector(text) for text in texts]

    @staticmethod
    def vector(text):
        values = [0.0] * EMBEDDING_DIMENSIONS
        for word in text.split():
            values[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


def make_question(number=1, title='هل انتشر الإسلام بالسيف؟', **overrides):
    """An extracted question dict as produced by extract_bayyinat."""
    question = {
        'number': number, 'part': 'ثانيًا', 'chapter': '1- الإسلام', 'title': title,
        'question': 'يقال إن الإسلام انتشر بالقوة.', 'alternative_phrasings': ['هل أكره الناس على الإسلام؟'],
        'keywords': [], 'answer_sections': {
            'content': 'مضمون السؤال.', 'summary': 'لم ينتشر الإسلام بالسيف.',
            'detailed': 'الفقرة الأولى.\nالفقرة الثانية.', 'conclusion': 'الخاتمة.',
        },
        'answer_summary': 'لم ينتشر الإسلام بالسيف.', 'page_start': 10, 'page_end': 12,
    }
    question.update(overrides)
    return question
