"""
Export reviewed answers as fine-tuning datasets (``qa.dataset``): ``sft.jsonl`` and
``dpo.jsonl`` in ``data/finetuning/`` by default (git-ignored: examples contain askers'
questions). Read-only on the database.
"""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from qa import dataset


class Command(BaseCommand):
    help = 'Write sft.jsonl and dpo.jsonl from reviewed answers (see docs/rag/06-finetuning-dataset.md).'

    def add_arguments(self, parser):
        parser.add_argument('--output', default=str(settings.BASE_DIR / 'data' / 'finetuning'),
                            help='Folder for the files (default: data/finetuning/).')
        parser.add_argument('--since', type=date.fromisoformat, help='Only answers from this date (YYYY-MM-DD).')
        parser.add_argument('--language', choices=['ar', 'en', 'fr'], help='Only questions in this language.')
        parser.add_argument('--with-metadata', action='store_true',
                            help='Add a metadata key to each line (uuid, language, prompt version, model).')

    def handle(self, *args, **options):
        interactions = dataset.usable_interactions(options['since'], options['language'])
        sft, dpo = dataset.build(interactions, with_metadata=options['with_metadata'])
        folder = Path(options['output'])
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for name, examples in (('sft.jsonl', sft), ('dpo.jsonl', dpo)):
                with open(folder / name, 'w', encoding='utf-8') as file:
                    for example in examples:
                        file.write(json.dumps(example, ensure_ascii=False) + '\n')
        except OSError as error:
            raise CommandError(f'Cannot write to {folder}: {error}') from None
        self.stdout.write(f'Usable answers: {interactions.count()}; SFT examples: {len(sft)}; '
                          f'DPO pairs: {len(dpo)}; written to {folder}')
