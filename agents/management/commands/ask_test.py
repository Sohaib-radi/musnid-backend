"""Ask questions through the full flow and print each trace (saved like real questions)."""

import json

from django.core.management.base import BaseCommand

from agents.services import ask


class Command(BaseCommand):
    help = 'Run questions through the flow: ask_test "question 1" "question 2"'

    def add_arguments(self, parser):
        parser.add_argument('questions', nargs='+')

    def handle(self, *args, **options):
        for text in options['questions']:
            i = ask(text, session_id='ask_test')
            trace = {
                'question': text, 'language': i.question.lang if i.pk else None, 'level': i.level, 'search_query': i.search_query,
                'retrieved': i.retrieved[:5], 'evidence': i.evidence_question_numbers,
                'decision': i.decision, 'verifier': i.verifier_verdict, 'citations': i.citations,
                'tokens': [i.tokens_in, i.tokens_out], 'latency_ms': i.latency_ms,
                'prompt_version': i.prompt_version, 'model': i.model_name, 'error': i.error,
            }
            self.stdout.write(json.dumps(trace, ensure_ascii=False, indent=1))
            self.stdout.write(f'ANSWER:\n{i.answer_text}\n{"-" * 60}')
