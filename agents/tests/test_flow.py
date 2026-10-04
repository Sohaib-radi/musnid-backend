"""Tests for agents/flow.py and agents/services.py: every route and safeguard, crews mocked."""

from types import SimpleNamespace

from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import translation

from agents.crews import prompt_version
from agents.flow import fixed_reply, mask_secrets, script_language
from agents.services import ask
from agents.tests.support import QUOTE, FakeCrew, answered, classified
from core.tests.support import make_center
from knowledge.services.ingest import ingest
from knowledge.tests.support import FakeEmbedder, make_question
from qa.models import Interaction, Question

QUESTION = 'هل انتشر الإسلام بالسيف؟'


@override_settings(LOW_THRESHOLD=0.30, EVIDENCE_QUESTIONS=3)
class FlowTestCase(TransactionTestCase):
    """
    Knowledge base with two questions (fake embeddings) and a default center.

    TransactionTestCase: CrewAI runs flow steps in worker threads with their own
    database connections, which cannot see data inside a TestCase transaction.
    """

    def setUp(self):
        self.embedder = FakeEmbedder()
        ingest([make_question(1), make_question(2, title='لماذا خلقنا الله؟', question='ما الحكمة من الخلق؟',
                                                 alternative_phrasings=['سؤال آخر'])],
               self.embedder, slug='bayyinat-ar', title='بينات', lang='ar')
        self.center = make_center(is_default=True)
        self.addCleanup(translation.activate, 'en')

    def run_ask(self, classify, answer=None, embedder=None, text=QUESTION, entailment=None):
        self.answer_crew = answer or answered()
        self.entailment_calls = []

        def all_supported(pairs):
            self.entailment_calls.append(pairs)
            return ['supported'] * len(pairs), SimpleNamespace(prompt_tokens=3, completion_tokens=1)
        return ask(text, session_id='s1', embedder=embedder or self.embedder, classify_crew=classify,
                   answer_crew=self.answer_crew, entailment=entailment or all_supported)


class RoutingTests(FlowTestCase):
    """Out of scope, level D, low score and failures end in fixed replies."""

    def test_out_of_scope_gets_the_fixed_refusal(self):
        interaction = self.run_ask(classified('out_of_scope', 'en', 'capital of France'),
                                   text='What is the capital of France?')
        self.assertEqual(interaction.decision, Interaction.Decision.OUT_OF_SCOPE)
        self.assertEqual(interaction.answer_text, fixed_reply('out_of_scope', 'en'))
        self.assertEqual(interaction.retrieved, [])
        self.assertEqual(self.answer_crew.inputs, [])

    def test_level_d_is_referred_without_search(self):
        interaction = self.run_ask(classified('D', 'ar'))
        self.assertEqual((interaction.decision, interaction.level), ('refer', 'D'))
        self.assertEqual(interaction.answer_text, fixed_reply('refer', 'ar'))
        self.assertEqual(interaction.retrieved, [])

    def test_low_score_abstains(self):
        interaction = self.run_ask(classified('B', 'ar', 'كلمات لا علاقة لها مطلقا'))
        self.assertEqual(interaction.decision, 'abstain')
        self.assertTrue(interaction.retrieved)
        self.assertLess(interaction.retrieved[0]['score'], 0.30)
        self.assertEqual(self.answer_crew.inputs, [])

    def test_classify_failure_abstains_with_masked_error(self):
        interaction = self.run_ask(FakeCrew(error=RuntimeError('401 for key sk-proj-abcdefghijklmnop')))
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('classify: RuntimeError', interaction.error)
        self.assertNotIn('abcdefghijklmnop', interaction.error)

    def test_retrieval_failure_abstains(self):
        interaction = self.run_ask(classified(), embedder=FakeEmbedder(fail=True))
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('retrieval', interaction.error)

    def test_answer_crew_failure_abstains(self):
        interaction = self.run_ask(classified(), answer=FakeCrew(error=ValueError('boom')))
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('answer crew: ValueError', interaction.error)

    def test_unreadable_output_abstains(self):
        interaction = self.run_ask(classified(), answer=FakeCrew(output=None))
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('answer crew', interaction.error)


class AnswerTests(FlowTestCase):
    """The writer gets evidence only; decide() applies the safeguards."""

    def test_full_answer_with_citations(self):
        interaction = self.run_ask(classified())
        self.assertEqual(interaction.decision, 'answer')
        self.assertEqual(interaction.citations, [1])
        self.assertEqual(interaction.evidence_question_numbers[0], 1)
        self.assertEqual(interaction.verifier_verdict, 'full')
        self.assertEqual(interaction.answer_text, 'لم ينتشر الإسلام بالسيف [Q1].')

    def test_writer_receives_evidence_never_question_chunks(self):
        self.run_ask(classified())
        inputs = self.answer_crew.inputs[0]
        self.assertIn('[Q1]', inputs['evidence'])
        self.assertIn('لم ينتشر الإسلام بالسيف.', inputs['evidence'])
        self.assertNotIn('هل أكره الناس على الإسلام؟', inputs['evidence'])  # a question-chunk phrasing
        self.assertEqual((inputs['language'], inputs['level']), ('ar', 'B'))

    def test_evidence_is_limited_to_the_top_questions(self):
        with self.settings(EVIDENCE_QUESTIONS=1):
            interaction = self.run_ask(classified())
        self.assertEqual(interaction.evidence_question_numbers, [1])

    def test_citations_outside_the_evidence_are_stripped(self):
        interaction = self.run_ask(classified(), answered('جواب [Q1] وادعاء [Q99].'))
        self.assertEqual(interaction.answer_text, 'جواب [Q1] وادعاء.')
        self.assertEqual(interaction.citations, [1])

    def test_sentence_with_a_quote_not_in_the_evidence_is_dropped(self):
        interaction = self.run_ask(classified(), answered([
            ('جملة مدعومة [Q1].', QUOTE),
            ('استنتاج غير مدعوم [Q1].', 'نص مخترع لا يوجد في الأدلة إطلاقا'),
        ]))
        self.assertEqual(interaction.answer_text, 'جملة مدعومة [Q1].')

    def test_sentence_without_quote_or_with_a_short_one_is_dropped(self):
        interaction = self.run_ask(classified(), answered([
            ('جملة مدعومة [Q1].', QUOTE), ('بلا اقتباس [Q1].', ''), ('اقتباس قصير [Q1].', 'الإسلام'),
        ]))
        self.assertEqual(interaction.answer_text, 'جملة مدعومة [Q1].')

    def test_entailment_is_one_batched_call_with_every_quoted_pair(self):
        self.run_ask(classified(), answered([('أ [Q1].', QUOTE), ('ب [Q1].', QUOTE), ('ج [Q1].', 'غير موجود في الأدلة أبدا')]))
        self.assertEqual(self.entailment_calls, [[('أ [Q1].', QUOTE), ('ب [Q1].', QUOTE)]])

    def test_not_supported_sentences_are_dropped(self):
        def judge(pairs):
            return ['supported', 'not_supported'], SimpleNamespace(prompt_tokens=0, completion_tokens=0)
        interaction = self.run_ask(classified(), answered([
            ('لم ينتشر الإسلام بالسيف [Q1].', QUOTE), ('مما يدل على أمر آخر [Q1].', QUOTE),
        ]), entailment=judge)
        self.assertEqual(interaction.answer_text, 'لم ينتشر الإسلام بالسيف [Q1].')

    def test_entailment_failure_abstains(self):
        def broken(pairs):
            raise ValueError('entailment returned 1 verdicts for 2 pairs')
        interaction = self.run_ask(classified(), entailment=broken)
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('answer crew: ValueError', interaction.error)

    def test_translated_quote_counts_as_missing(self):
        interaction = self.run_ask(classified(language='en'), answered([
            ('Islam did not spread by the sword [Q1].', 'Islam did not spread by the sword.'),
        ]))
        self.assertEqual(interaction.decision, 'refer')

    def test_quote_matching_ignores_diacritics_and_punctuation(self):
        interaction = self.run_ask(classified(), answered(quote='لَمْ يَنتشرِ الإسلامُ - بالسيف'))
        self.assertEqual(interaction.decision, 'answer')

    def test_all_sentences_dropped_is_referred(self):
        interaction = self.run_ask(classified(), answered(quote='نص مخترع لا يوجد في الأدلة إطلاقا'))
        self.assertEqual(interaction.decision, 'refer')

    def test_no_valid_citation_is_referred(self):
        interaction = self.run_ask(classified(), answered('جواب بلا مصدر [Q99].'))
        self.assertEqual(interaction.decision, 'refer')
        self.assertEqual(interaction.answer_text, fixed_reply('refer', 'ar'))

    def test_coverage_none_is_referred(self):
        interaction = self.run_ask(classified(), answered(coverage='none'))
        self.assertEqual(interaction.decision, 'refer')

    def test_partial_gets_the_fixed_note(self):
        interaction = self.run_ask(classified(), answered(coverage='partial'))
        self.assertEqual(interaction.decision, 'partial')
        self.assertTrue(interaction.answer_text.endswith(fixed_reply('partial', 'ar')))

    def test_level_c_gets_the_fixed_notice(self):
        interaction = self.run_ask(classified('C'))
        self.assertEqual(interaction.decision, 'answer')
        self.assertTrue(interaction.answer_text.endswith(fixed_reply('disagreement', 'ar')))


class SavingTests(FlowTestCase):
    """Questions and interactions are saved with their trace."""

    def test_saved_with_trace_and_version_stamp(self):
        interaction = self.run_ask(classified())
        question = Question.objects.get()
        self.assertEqual((question.center, question.lang, question.session_id), (self.center, 'ar', 's1'))
        self.assertEqual(interaction.question, question)
        self.assertEqual(interaction.model_name, 'gpt-4o-mini')
        self.assertEqual(interaction.prompt_version, prompt_version())
        self.assertEqual((interaction.tokens_in, interaction.tokens_out), (23, 11))  # two crews + entailment
        self.assertGreaterEqual(interaction.latency_ms, 0)
        self.assertEqual(interaction.search_query, QUESTION)

    def test_without_default_center_nothing_is_saved(self):
        self.center.is_default = False
        self.center.save()
        interaction = self.run_ask(classified())
        self.assertIsNone(interaction.pk)
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('no default center', interaction.error)
        self.assertFalse(Question.objects.exists())


class FixedReplyTests(TestCase):
    """Fixed replies are translated, never generated; secrets are masked."""

    def tearDown(self):
        translation.activate('en')

    def test_translated_and_other_falls_back_to_english(self):
        for kind in ('out_of_scope', 'refer', 'abstain', 'partial', 'disagreement'):
            with self.subTest(kind=kind):
                english = fixed_reply(kind, 'en')
                self.assertNotEqual(fixed_reply(kind, 'ar'), english)
                self.assertNotEqual(fixed_reply(kind, 'fr'), english)
                self.assertEqual(fixed_reply(kind, 'other'), english)

    def test_disagreement_notice_text(self):
        self.assertEqual(fixed_reply('disagreement', 'en'),
                         'This matter involves scholarly disagreement; consult a specialist for your situation.')

    def test_script_language(self):
        self.assertEqual(script_language('هل انتشر الإسلام بالسيف؟', 'en'), 'ar')
        self.assertEqual(script_language('Did Islam spread by the sword?', 'ar'), 'en')
        self.assertEqual(script_language('L’islam s’est-il répandu par l’épée ?', 'fr'), 'fr')

    def test_mask_secrets(self):
        masked = mask_secrets('key sk-proj-abcdefghij and header Bearer abc.def')
        self.assertNotIn('abcdefghij', masked)
        self.assertNotIn('abc.def', masked)
        self.assertIn('sk-proj…', masked)
