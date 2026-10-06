"""Store the competition's official glossary as a knowledge source (``knowledge.glossary``); idempotent."""

from django.core.management.base import BaseCommand

from knowledge.embeddings import OpenAIEmbedder
from knowledge.glossary import SLUG, ingest_glossary


class Command(BaseCommand):
    help = "Embed and store the competition's official glossary (one chunk per term)."

    def handle(self, *args, **options):
        count = ingest_glossary(OpenAIEmbedder())
        self.stdout.write(f'{SLUG}: {count} terms stored.')
