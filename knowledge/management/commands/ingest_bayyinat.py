"""Ingest data/processed/bayyinat_ar.json into the knowledge base (OpenAI embeddings)."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge.embeddings import OpenAIEmbedder
from knowledge.services.ingest import ingest

SLUG = 'bayyinat-ar'
# The book's page and PDF on dawa.center. The PDF is byte-identical to the ingested
# source (SHA-256 checked on 2026-10-04), so its page numbers match the chunks'.
URL = 'https://dawa.center/file/7937'
PDF_URL = 'https://dawa.center/storage/files/AMYj6DfmHlSnZ766Zz0VlBNwmYtdwhAl31XMETlT.pdf'


class Command(BaseCommand):
    help = 'Chunk, embed and store the extracted Bayyinat questions (replaces the previous ingestion).'

    def add_arguments(self, parser):
        parser.add_argument('--json', default=str(settings.BASE_DIR / 'data' / 'processed' / 'bayyinat_ar.json'))

    def handle(self, *args, **options):
        questions = json.loads(Path(options['json']).read_text(encoding='utf-8'))
        document, count = ingest(
            questions, OpenAIEmbedder(), slug=SLUG, lang='ar',
            title='بيِّنات: أسئلة منتقاة حول الإسلام', url=URL, pdf_url=PDF_URL,
            license_note='Vetted source for the AI Challenge; text not redistributed in the repository.',
        )
        self.stdout.write(f'{document.slug}: {len(questions)} questions, {count} chunks stored')
