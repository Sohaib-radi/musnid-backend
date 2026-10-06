"""Tests for agents/flow.py and agents/services.py: every route and safeguard, crews mocked."""

from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import translation

from agents.crews import prompt_version
from agents.flow import _comparable, mask_secrets, quote_matches, script_language
from agents.replies import fixed_reply, note_codes, notes
from agents.services import DailyLimitReached, ask
from agents.tests.support import QUOTE, FakeCrew, answered, classified
from core.tests.support import make_center, make_user
from knowledge.services.ingest import ingest
from knowledge.tests.support import FakeEmbedder, make_question
from qa.models import Interaction, Question, Referral

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

    def run_ask(self, classify, answer=None, embedder=None, text=QUESTION, entailment=None, asker=None):
        self.answer_crew = answer or answered()
        self.entailment_calls = []

        def all_supported(pairs):
            self.entailment_calls.append(pairs)
            return ['supported'] * len(pairs), SimpleNamespace(prompt_tokens=3, completion_tokens=1)
        return ask(text, session_id='s1', asker=asker, embedder=embedder or self.embedder, classify_crew=classify,
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
        self.assertEqual(interaction.evidence, '')  # nothing given to a writer
        self.assertEqual((interaction.decision, interaction.level), ('refer', 'D'))
        self.assertEqual(interaction.answer_text, fixed_reply('refer_personal', 'ar'))  # says why
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
        self.assertEqual(interaction.answer_text, fixed_reply('refer_no_evidence', 'ar'))  # says why

    def test_coverage_none_is_referred(self):
        interaction = self.run_ask(classified(), answered(coverage='none'))
        self.assertEqual(interaction.decision, 'refer')

    def test_related_material_without_the_main_ask_is_referred(self):
        # The verifier says "partial", but the kept sentences do not answer what was asked
        interaction = self.run_ask(classified(), answered(coverage='partial', answers_main_ask=False))
        self.assertEqual((interaction.decision, interaction.verifier_verdict), ('refer', 'none'))
        self.assertEqual(interaction.answer_text, fixed_reply('refer_no_evidence', 'ar'))

    def test_partial_gets_the_fixed_note(self):
        interaction = self.run_ask(classified(), answered(coverage='partial'))
        self.assertEqual(interaction.decision, 'partial')
        self.assertTrue(interaction.answer_text.endswith(fixed_reply('partial', 'ar')))

    def test_level_c_gets_the_fixed_notice(self):
        interaction = self.run_ask(classified('C'))
        self.assertEqual(interaction.decision, 'answer')
        self.assertTrue(interaction.answer_text.endswith(fixed_reply('disagreement', 'ar')))


class SavingTests(FlowTestCase):
    """Questions and interactions are saved with their trace; nothing is sent to the specialists by itself."""

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
        # The exact evidence the writer received is kept with the answer
        self.assertEqual(interaction.evidence, self.answer_crew.inputs[0]['evidence'])
        self.assertIn('[Q1]', interaction.evidence)

    def test_asker_is_saved_when_given(self):
        user = make_user()
        self.run_ask(classified(), asker=user)
        self.assertEqual(Question.objects.get().asker, user)

    def test_anonymous_question_has_no_asker(self):
        self.run_ask(classified())
        self.assertIsNone(Question.objects.get().asker)

    def test_daily_limit_raises_before_any_model_call(self):
        self.run_ask(classified())
        crew = classified()
        with override_settings(ASK_DAILY_LIMIT=1), self.assertRaises(DailyLimitReached):
            ask(QUESTION, session_id='s1', embedder=self.embedder, classify_crew=crew)
        self.assertEqual(crew.inputs, [])
        self.assertEqual(Question.objects.count(), 1)

    def test_without_default_center_nothing_is_saved(self):
        self.center.is_default = False
        self.center.save()
        interaction = self.run_ask(classified())
        self.assertIsNone(interaction.pk)
        self.assertEqual(interaction.decision, 'abstain')
        self.assertIn('no default center', interaction.error)
        self.assertFalse(Question.objects.exists())

    def test_no_question_is_sent_to_the_specialists_without_the_askers_choice(self):
        self.run_ask(classified('D', 'ar'))
        self.run_ask(classified(), answered(coverage='none'))
        self.run_ask(classified('B', 'ar', 'كلمات لا علاقة لها مطلقا'))
        self.assertEqual(sorted(Interaction.objects.values_list('decision', flat=True)), ['abstain', 'refer', 'refer'])
        self.assertFalse(Referral.objects.exists())


class FixedReplyTests(TestCase):
    """Fixed replies are translated, never generated; secrets are masked."""

    def tearDown(self):
        translation.activate('en')

    def test_translated_and_other_falls_back_to_english(self):
        for kind in ('out_of_scope', 'refer', 'abstain', 'partial', 'disagreement', 'daily_capacity'):
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


class QuoteMatchTests(SimpleTestCase):
    """``quote_matches``: 90% of the quote's words, in order, in one passage."""

    EVIDENCE = _comparable(
        'مقدمة لا علاقة لها. الإسلامُ لم ينتشِرْ بالسيف، وإنما انتشَرَ بالدعوةِ والحُجَّة، '
        'وإذا كان للفتحِ أثرٌ في انتشارِ الإسلامِ، فمِن جهةِ أنَّ فتحَ البلادِ يستدعي قصدَ كثيرٍ '
        'مِن المسلِمين للرحلةِ إليها. خاتمة أخرى عن موضوع مختلف تماما.')
    # 10 words of the evidence, copied exactly.
    TEN = 'الإسلام لم ينتشر بالسيف وإنما انتشر بالدعوة والحجة وإذا كان'

    def matches(self, quote):
        return quote_matches(_comparable(quote), self.EVIDENCE)

    def test_exact_copy_matches(self):
        self.assertTrue(self.matches(self.TEN))

    def test_one_changed_word_in_ten_matches(self):
        self.assertTrue(self.matches(self.TEN.replace('والحجة', 'والبرهان')))

    def test_one_dropped_word_in_ten_matches(self):
        self.assertTrue(self.matches(self.TEN.replace(' وإنما', '')
                                     + ' للفتح'))

    def test_two_changed_words_in_ten_do_not_match(self):
        self.assertFalse(self.matches(self.TEN.replace('والحجة', 'والبرهان').replace('كان', 'صار')))

    def test_short_quote_must_be_exact(self):
        self.assertTrue(self.matches('الإسلام لم ينتشر بالسيف'))
        self.assertFalse(self.matches('لم ينتشر الإسلام بالسيف'))

    def test_words_gathered_from_across_the_evidence_do_not_match(self):
        self.assertFalse(self.matches('مقدمة لا علاقة لها خاتمة أخرى عن موضوع مختلف تماما'))

    def test_invented_text_does_not_match(self):
        self.assertFalse(self.matches('الإسلام انتشر بالقوة والإكراه في جميع البلاد التي فتحها المسلمون'))


class SentenceRecordTests(FlowTestCase):
    """Kept sentences are saved with their quote and source; drops with their reason."""

    def test_kept_sentences_saved_without_markers_with_their_source(self):
        interaction = self.run_ask(classified())
        self.assertEqual(interaction.sentences, [{'text': 'لم ينتشر الإسلام بالسيف.', 'quote': QUOTE, 'number': 1}])
        self.assertEqual(interaction.dropped, [])

    def test_source_is_the_question_whose_evidence_holds_the_quote(self):
        other = 'ورد في المسألة الثانية نص مختلف تماما عن الأولى.'
        ingest([make_question(1), make_question(2, title='لماذا خلقنا الله؟', answer_sections={'detailed': other})],
               self.embedder, slug='bayyinat-ar', title='بينات', lang='ar')
        interaction = self.run_ask(classified(), answered([('جملة [Q1].', other)]))
        self.assertEqual(interaction.sentences[0]['number'], 2)
        self.assertEqual(interaction.answer_text, 'جملة [Q1].')

    def test_dropped_sentences_saved_with_their_reason(self):
        def judge(pairs):
            return ['supported', 'not_supported'], SimpleNamespace(prompt_tokens=0, completion_tokens=0)
        interaction = self.run_ask(classified(), answered([
            ('مدعومة [Q1].', QUOTE), ('استنتاج [Q1].', QUOTE), ('مخترعة [Q1].', 'نص مخترع لا يوجد في الأدلة إطلاقا'),
        ]), entailment=judge)
        self.assertEqual([s['text'] for s in interaction.sentences], ['مدعومة.'])
        self.assertEqual([(d['text'], d['reason']) for d in interaction.dropped],
                         [('مخترعة [Q1].', 'quote'), ('استنتاج [Q1].', 'entailment')])

    def test_referral_shows_no_sentences_but_keeps_the_drops(self):
        interaction = self.run_ask(classified(), answered([
            ('جملة [Q1].', QUOTE), ('مخترعة [Q1].', 'نص مخترع لا يوجد في الأدلة إطلاقا'),
        ], coverage='none'))
        self.assertEqual(interaction.decision, 'refer')
        self.assertEqual(interaction.sentences, [])
        self.assertEqual(len(interaction.dropped), 1)


class NoteTests(SimpleTestCase):
    """Notes after an answer: codes for the client, fixed translated text."""

    def test_codes_by_decision_and_level(self):
        self.assertEqual(note_codes('answer', 'B'), [])
        self.assertEqual(note_codes('partial', 'B'), ['partial'])
        self.assertEqual(note_codes('answer', 'C'), ['level_c'])
        self.assertEqual(note_codes('partial', 'C'), ['partial', 'level_c'])
        for decision in ('refer', 'abstain', 'out_of_scope'):
            self.assertEqual(note_codes(decision, 'C'), [])

    def test_note_text_is_the_fixed_reply(self):
        self.assertEqual(notes('partial', 'C', 'fr'), [
            {'code': 'partial', 'text': fixed_reply('partial', 'fr')},
            {'code': 'level_c', 'text': fixed_reply('disagreement', 'fr')},
        ])


class GlossaryEvidenceTests(FlowTestCase):
    """Glossary terms above the threshold come first in the evidence, before Bayyinat."""

    def test_matching_term_goes_first(self):
        from knowledge.glossary import FIRST_NUMBER, TERMS, chunk_text, ingest_glossary
        ingest_glossary(self.embedder)
        interaction = self.run_ask(classified('A', 'ar', chunk_text(*TERMS[1])))
        self.assertEqual(interaction.evidence_question_numbers[0], FIRST_NUMBER + 1)
        self.assertTrue(interaction.evidence.startswith(f'[Q{FIRST_NUMBER + 1}] التوحيد (Tawhid / Oneness of God)'))

