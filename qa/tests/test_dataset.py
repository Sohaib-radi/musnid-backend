"""Tests for qa/dataset.py and the export_finetuning command: which answers become examples, and their format."""

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from core.tests.support import make_interaction, make_membership, make_question, make_user
from qa import dataset
from qa.models import AnswerRevision, HumanLabel
from qa.services import label, revise

EVIDENCE = '[Q229] الإسلام لم ينتشر بالسيف.'


class DatasetTests(TestCase):
    """Reviewed answers with kept evidence become SFT examples and DPO pairs; nothing else does."""

    def setUp(self):
        self.asker = make_user(email='asker@example.com')
        self.reviewer = make_membership(user=make_user(full_name='Reviewer Name')).user

    def answer(self, text='Did Islam spread by the sword?', **fields):
        question = make_question(center=self.reviewer.memberships.get().center, text=text, lang='en', asker=self.asker)
        fields.setdefault('evidence', EVIDENCE)
        return make_interaction(question=question, answer_text='No, it spread by invitation [Q229].',
                                prompt_version='abc123', model_name='gpt-4o-mini', **fields)

    def build(self, **options):
        return dataset.build(dataset.usable_interactions(), **options)

    def test_an_approved_answer_is_an_sft_example_with_the_exact_evidence(self):
        label(self.answer(), self.reviewer, HumanLabel.Verdict.APPROVE)
        [example], dpo = self.build()
        system, user, assistant = example['messages']
        self.assertEqual((system['role'], user['role'], assistant['role']), ('system', 'user', 'assistant'))
        self.assertIn(EVIDENCE, user['content'])
        self.assertIn('Did Islam spread by the sword?', user['content'])
        self.assertEqual(assistant['content'], 'No, it spread by invitation [Q229].')
        self.assertEqual(dpo, [])

    def test_a_correction_is_the_target_and_a_preference_pair(self):
        label(self.answer(), self.reviewer, HumanLabel.Verdict.CORRECT, corrected_answer='Better answer [Q229].')
        [example], [pair] = self.build()
        self.assertEqual(example['messages'][-1]['content'], 'Better answer [Q229].')
        self.assertEqual(pair['preferred_output'], [{'role': 'assistant', 'content': 'Better answer [Q229].'}])
        self.assertEqual(pair['non_preferred_output'][0]['content'], 'No, it spread by invitation [Q229].')
        self.assertEqual(len(pair['input']['messages']), 2)

    def test_a_specialists_correction_also_counts(self):
        interaction = self.answer()
        revise(interaction.question, self.reviewer, 'Corrected by the center [Q229].', AnswerRevision.Reason.CORRECTION)
        [example], [pair] = self.build()
        self.assertEqual(pair['preferred_output'][0]['content'], 'Corrected by the center [Q229].')

    def test_excluded_answers(self):
        label(self.answer(evidence=''), self.reviewer, HumanLabel.Verdict.APPROVE)  # saved before step 1
        label(self.answer(error='flow: TimeoutError'), self.reviewer, HumanLabel.Verdict.APPROVE)
        label(self.answer(), self.reviewer, HumanLabel.Verdict.REJECT, reason='Wrong.')
        self.answer()  # not reviewed
        self.assertEqual(self.build(), ([], []))

    def test_no_personal_data_and_optional_metadata(self):
        interaction = self.answer()
        label(interaction, self.reviewer, HumanLabel.Verdict.APPROVE, reason='Internal reason')
        text = json.dumps(self.build(), ensure_ascii=False)
        for private in ('asker@example.com', 'Reviewer Name', 'Internal reason', interaction.question.session_id or '§'):
            self.assertNotIn(private, text)
        self.assertNotIn('metadata', self.build()[0][0])
        metadata = self.build(with_metadata=True)[0][0]['metadata']
        self.assertEqual((metadata['prompt_version'], metadata['source']), ('abc123', 'approved_ai_answer'))


class ExportCommandTests(TestCase):
    """The command writes two JSONL files and reports the counts."""

    def test_writes_both_files(self):
        reviewer = make_membership().user
        interaction = make_interaction(question=make_question(center=reviewer.memberships.get().center),
                                       evidence=EVIDENCE)
        label(interaction, reviewer, HumanLabel.Verdict.CORRECT, corrected_answer='Better.')
        with tempfile.TemporaryDirectory() as folder:
            out = StringIO()
            call_command('export_finetuning', '--output', folder, stdout=out)
            lines = Path(folder, 'sft.jsonl').read_text(encoding='utf-8').splitlines()
            pairs = Path(folder, 'dpo.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual((len(lines), len(pairs)), (1, 1))
        self.assertEqual(json.loads(lines[0])['messages'][-1]['content'], 'Better.')
        self.assertIn('SFT examples: 1; DPO pairs: 1', out.getvalue())
