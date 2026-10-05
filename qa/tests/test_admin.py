"""Tests for qa/admin.py: the read-only questions admin and what its pages show."""

from django.urls import reverse

from core.tests.support import make_center, make_interaction, make_question
from core.tests.test_admin import AdminTestCase
from qa.models import Interaction, Question


class QuestionAdminTests(AdminTestCase):
    """Questions list, filters, search and the answer details on each page."""

    def changelist(self, **params):
        return self.client.get(reverse('admin:qa_question_changelist'), params)

    def change_page(self, question):
        return self.client.get(reverse('admin:qa_question_change', args=[question.pk]))

    def test_list_shows_the_decision_badge(self):
        make_interaction(question=make_question(text='هل انتشر الإسلام بالسيف؟'),
                         decision=Interaction.Decision.REFER)
        response = self.changelist()
        self.assertContains(response, 'هل انتشر الإسلام بالسيف؟')
        self.assertContains(response, 'Referred to a center')

    def test_question_without_saved_answer_still_lists(self):
        make_question(text='Unanswered question?')
        self.assertContains(self.changelist(), 'Unanswered question?')

    def test_filter_by_decision(self):
        make_interaction(question=make_question(text='Answered?'))
        make_interaction(question=make_question(text='Referred?'), decision=Interaction.Decision.REFER)
        response = self.changelist(interaction__decision__exact='refer')
        self.assertContains(response, 'Referred?')
        self.assertNotContains(response, 'Answered?')

    def test_search_by_text_and_by_follow_up_number(self):
        wanted = make_question(text='About fasting?')
        make_question(text='About prayer?')
        by_text = self.changelist(q='fasting')
        self.assertContains(by_text, 'About fasting?')
        self.assertNotContains(by_text, 'About prayer?')
        by_number = self.changelist(q=f' {wanted.uuid} ')
        self.assertContains(by_number, 'About fasting?')
        self.assertNotContains(by_number, 'About prayer?')

    def test_change_page_shows_kept_and_removed_sentences(self):
        interaction = make_interaction(
            sentences=[{'text': 'Kept sentence.', 'quote': 'نص داعم', 'number': 229}],
            dropped=[{'text': 'Removed sentence.', 'quote': 'نص آخر', 'reason': 'entailment'}],
        )
        response = self.change_page(interaction.question)
        self.assertContains(response, 'Kept sentence.')
        self.assertContains(response, 'نص داعم')
        self.assertContains(response, 'Bayyinat question 229')
        self.assertContains(response, 'Removed sentence.')
        self.assertContains(response, 'Quote does not support the sentence')

    def test_answer_text_is_escaped(self):
        interaction = make_interaction(answer_text='<script>alert(1)</script>')
        response = self.change_page(interaction.question)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_change_page_without_saved_answer(self):
        response = self.change_page(make_question())
        self.assertContains(response, 'No answer was saved for this question.')

    def test_read_only(self):
        question = make_interaction().question
        self.assertEqual(self.client.get(reverse('admin:qa_question_add')).status_code, 403)
        page = self.change_page(question)
        self.assertNotContains(page, 'name="_save"')
        delete = self.client.post(reverse('admin:qa_question_delete', args=[question.pk]), {'post': 'yes'})
        self.assertEqual(delete.status_code, 403)
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())

    def test_center_filter_lists_centers(self):
        center = make_center(name='Center of Rabat')
        make_question(center=center)
        self.assertContains(self.changelist(), 'Center of Rabat')

    def test_list_explains_its_columns(self):
        response = self.changelist()
        self.assertContains(response, "showModal()")
        self.assertContains(response, '<dialog id="list_help-dialog"')
        self.assertContains(response, 'personal religious ruling (fatwa)')
        self.assertContains(response, 'musnid-badge-warning')

    def test_list_shows_time_tokens_and_error(self):
        make_interaction(question=make_question(text='Fine run?'), latency_ms=26800, tokens_in=33068, tokens_out=2946)
        make_interaction(question=make_question(text='Failed run?'), error='flow: TimeoutError')
        response = self.changelist()
        self.assertContains(response, '26.8 s')
        self.assertContains(response, '33068 in, 2946 out')
        html = response.content.decode()
        self.assertEqual(html.count('field-has_error'), 2)
        self.assertIn('>Yes<', html.replace(' ', '').replace('\n', ''))
        self.assertIn('>No<', html.replace(' ', '').replace('\n', ''))

    def test_change_page_explains_its_sections(self):
        response = self.change_page(make_interaction().question)
        self.assertContains(response, 'How to read this page')
        self.assertContains(response, 'Sentences the AI wrote but the checks removed')

