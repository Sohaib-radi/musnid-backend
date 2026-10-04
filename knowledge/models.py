"""
Source documents and their retrieval chunks (docs/rag/02-pipeline.md).

A ``SourceChunk`` is either a ``question`` chunk (title, question and
alternative phrasings: used to FIND the right question, never shown to the
writer), a ``summary`` chunk or an ``answer`` chunk (the evidence the writer
receives through ``knowledge.services.search.get_evidence``).
"""

from urllib.parse import urlencode

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

from core.models import BaseModel

EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small


class SourceDocument(BaseModel):
    """A vetted source (a book), identified by its slug."""

    slug = models.SlugField(_('slug'), unique=True)
    title = models.CharField(_('title'), max_length=300)
    lang = models.CharField(_('language'), max_length=2)
    url = models.URLField(_('URL'), blank=True, help_text=_('Public page of the document.'))
    pdf_url = models.URLField(_('PDF URL'), blank=True,
                              help_text=_('Public PDF of the document, the same file that was ingested.'))
    license_note = models.TextField(_('license note'), blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('source document')
        verbose_name_plural = _('source documents')

    def __str__(self):
        return self.title

    def page_url(self, language):
        """
        The document's public page with its interface in ``language``.

        ``?lang=`` is added only for a language the service supports; empty
        when the document has no ``url``.
        """
        if not self.url:
            return ''
        if language not in dict(settings.LANGUAGES):
            return self.url
        separator = '&' if '?' in self.url else '?'
        return f'{self.url}{separator}{urlencode({"lang": language})}'

    def pdf_page_url(self, page):
        """
        The public PDF opened at printed page ``page``; empty without ``pdf_url``.

        In the ingested books the printed page number equals the 0-based PDF page
        index (docs/rag/01-extraction-findings.md); PDF viewers count ``#page=``
        from 1, hence ``page + 1``.
        """
        if not self.pdf_url:
            return ''
        if page is None:
            return self.pdf_url
        return f'{self.pdf_url}#page={int(page) + 1}'


class SourceChunk(BaseModel):
    """A retrievable piece of a document, with its embedding."""

    class Kind(models.TextChoices):
        """What part of a question the chunk holds."""

        QUESTION = 'question', _('Question')
        SUMMARY = 'summary', _('Summary')
        ANSWER = 'answer', _('Answer')

    document = models.ForeignKey(
        SourceDocument, on_delete=models.CASCADE, related_name='chunks', verbose_name=_('document'),
    )
    question_number = models.PositiveIntegerField(_('question number'))
    kind = models.CharField(_('kind'), max_length=10, choices=Kind.choices)
    lang = models.CharField(_('language'), max_length=2)
    title = models.CharField(_('title'), max_length=500)
    text = models.TextField(_('text'))
    text_norm = models.TextField(_('normalized text'))
    embedding = VectorField(_('embedding'), dimensions=EMBEDDING_DIMENSIONS)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _('source chunk')
        verbose_name_plural = _('source chunks')
        ordering = ['document', 'question_number', 'id']
        indexes = [
            models.Index(fields=['document', 'question_number', 'kind'], name='chunk_question_kind'),
            HnswIndex(
                name='chunk_embedding_hnsw', fields=['embedding'],
                m=16, ef_construction=64, opclasses=['vector_cosine_ops'],
            ),
        ]

    def __str__(self):
        return f'{self.document.slug} #{self.question_number} {self.kind}'
