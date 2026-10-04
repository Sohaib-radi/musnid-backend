"""
Ingestion of extracted questions into ``SourceDocument`` and ``SourceChunk``.

Idempotent by document slug: re-running replaces the document's chunks.
Embeddings are computed first; only then, in one transaction, the old chunks
are deleted and the new ones inserted, so a failed embedding call leaves the
previous data untouched.
"""

from django.db import transaction

from knowledge.chunking import chunk_question
from knowledge.models import SourceChunk, SourceDocument
from knowledge.normalize import normalize


def ingest(questions, embedder, *, slug, title, lang, url='', pdf_url='', license_note=''):
    """
    Chunk, embed and store ``questions`` as the document ``slug``.

    Returns:
        ``(document, chunk_count)``.
    """
    specs = [spec for question in questions for spec in chunk_question(question)]
    normalized = [normalize(spec.text) for spec in specs]
    vectors = embedder.embed(normalized)
    if len(vectors) != len(specs):
        raise ValueError(f'expected {len(specs)} embeddings, got {len(vectors)}')
    with transaction.atomic():
        document, _created = SourceDocument.objects.update_or_create(
            slug=slug, defaults={'title': title, 'lang': lang, 'url': url, 'pdf_url': pdf_url,
                                    'license_note': license_note},
        )
        document.chunks.all().delete()
        SourceChunk.objects.bulk_create([
            SourceChunk(
                document=document, question_number=spec.question_number, kind=spec.kind, lang=lang,
                title=spec.title, text=spec.text, text_norm=norm, embedding=vector, metadata=spec.metadata,
            )
            for spec, norm, vector in zip(specs, normalized, vectors)
        ], batch_size=500)
    return document, len(specs)
