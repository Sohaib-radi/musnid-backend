"""Print the top questions for each query, to check retrieval by hand."""

from django.core.management.base import BaseCommand

from knowledge.embeddings import OpenAIEmbedder
from knowledge.services.search import search


class Command(BaseCommand):
    help = 'Search the knowledge base: search_test "question 1" "question 2" [-k 5]'

    def add_arguments(self, parser):
        parser.add_argument('queries', nargs='+')
        parser.add_argument('-k', type=int, default=5)

    def handle(self, *args, **options):
        embedder = OpenAIEmbedder()
        for query in options['queries']:
            self.stdout.write(f'\n{query}')
            for rank, result in enumerate(search(query, options['k'], embedder), 1):
                self.stdout.write(f'  {rank}. {result.score:.3f}  #{result.question_number} '
                                  f'[{result.kind}] {result.title}')
