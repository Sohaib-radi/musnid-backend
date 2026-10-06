"""Read-only admin for the knowledge base: documents are ingested by commands, not edited."""

from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from knowledge.models import SourceChunk, SourceDocument


class ReadOnlyAdmin(ModelAdmin):
    """No add, change or delete: content comes from ingest commands."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SourceDocument)
class SourceDocumentAdmin(ReadOnlyAdmin):
    """Ingested documents with their chunk counts."""

    list_display = ['title', 'slug', 'lang', 'chunk_count', 'updated_at']
    list_before_template = 'admin/knowledge/sourcedocument/list_help.html'
    search_fields = ['title', 'slug']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(chunk_total=Count('chunks'))

    @display(description=_('chunks'), ordering='chunk_total')
    def chunk_count(self, document):
        return document.chunk_total


@admin.register(SourceChunk)
class SourceChunkAdmin(ReadOnlyAdmin):
    """Chunks, searchable by text; the embedding vector is not displayed."""

    list_display = ['question_number', 'kind', 'title', 'document']
    list_before_template = 'admin/knowledge/sourcechunk/list_help.html'
    list_filter = ['kind', 'document']
    search_fields = ['title', 'text', '=question_number']
    list_select_related = ['document']
    exclude = ['embedding']
    readonly_fields = ['document', 'question_number', 'kind', 'lang', 'title', 'text', 'text_norm', 'metadata',
                       'created_at', 'updated_at']
