"""
Retrieval (docs/rag/02-pipeline.md).

``search`` finds the questions closest to a query; ``get_evidence`` returns
what the writer may read for chosen questions: their summary and answer
chunks, never the question chunks (which only serve to find).
"""

from dataclasses import dataclass

from django.db import connection, transaction
from pgvector.django import CosineDistance

from knowledge.models import SourceChunk
from knowledge.normalize import normalize

CANDIDATES_PER_RESULT = 8
MIN_CANDIDATES = 40


@dataclass
class SearchResult:
    """The best chunk of one question for a query. ``score`` = 1 - cosine distance."""

    question_number: int
    title: str
    score: float
    kind: str
    document: str


def search(query, k, embedder, document=None):
    """
    Return the ``k`` questions closest to ``query``, best first.

    The query is normalized and embedded; ``hnsw.ef_search`` is raised to the
    number of candidates fetched (default 40 is too low when several chunks
    of one question compete); the best chunk per question is kept.
    """
    vector = embedder.embed([normalize(query)])[0]
    candidates = max(MIN_CANDIDATES, k * CANDIDATES_PER_RESULT)
    chunks = SourceChunk.objects.select_related('document')
    if document is not None:
        chunks = chunks.filter(document__slug=document)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL hnsw.ef_search = %s', [candidates])
        rows = list(
            chunks.annotate(distance=CosineDistance('embedding', vector)).order_by('distance')[:candidates]
        )
    best = {}
    for chunk in rows:
        key = (chunk.document_id, chunk.question_number)
        if key not in best:
            best[key] = SearchResult(chunk.question_number, chunk.title, 1 - chunk.distance, chunk.kind,
                                     chunk.document.slug)
    return list(best.values())[:k]


def get_evidence(question_numbers, document=None):
    """
    Summary and answer chunks of ``question_numbers``, in the given question
    order, summary first, then answer pieces in reading order.
    """
    order = {number: index for index, number in enumerate(question_numbers)}
    chunks = SourceChunk.objects.filter(
        question_number__in=question_numbers,
        kind__in=[SourceChunk.Kind.SUMMARY, SourceChunk.Kind.ANSWER],
    )
    if document is not None:
        chunks = chunks.filter(document__slug=document)
    return sorted(chunks, key=lambda c: (order[c.question_number], c.kind != SourceChunk.Kind.SUMMARY,
                                         c.metadata.get('position', 0)))
