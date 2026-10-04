"""Tests for knowledge/admin.py: read-only, Unfold."""

from django.contrib import admin
from django.test import TestCase
from unfold.admin import ModelAdmin

from core.tests.support import make_user
from knowledge.models import SourceChunk, SourceDocument
from knowledge.services.ingest import ingest
from knowledge.tests.support import FakeEmbedder, make_question


class KnowledgeAdminTests(TestCase):
    """Documents and chunks can be viewed, not added, edited or deleted."""

    def setUp(self):
        self.client.force_login(make_user(is_staff=True, is_superuser=True))
        ingest([make_question()], FakeEmbedder(), slug='bayyinat-ar', title='بينات', lang='ar')

    def test_unfold_and_read_only(self):
        for model in (SourceDocument, SourceChunk):
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertIsInstance(model_admin, ModelAdmin)
                self.assertFalse(model_admin.has_add_permission(None))
                self.assertFalse(model_admin.has_change_permission(None))
                self.assertFalse(model_admin.has_delete_permission(None))

    def test_pages_respond_without_the_embedding(self):
        chunk = SourceChunk.objects.first()
        for url in ('/admin/knowledge/sourcedocument/', '/admin/knowledge/sourcechunk/',
                    f'/admin/knowledge/sourcechunk/{chunk.pk}/change/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="embedding"')
