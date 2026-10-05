"""Tests for qa/admin.py: the read-only questions and referrals admins and what their pages show."""

from django.contrib.auth.models import Permission
from django.urls import reverse

from core.tests.support import make_center, make_interaction, make_membership, make_question, make_referral, make_user
from core.tests.test_admin import AdminTestCase
from qa.admin import pending_referrals_badge
from qa.models import AnswerRevision, Interaction, Question, Referral
from qa.services import revise


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

    def test_asker_column_and_search_by_email(self):
        make_question(text='Logged in?', asker=make_user(email='amina@example.com'))
        make_question(text='Anonymous question?')
        response = self.changelist()
        self.assertContains(response, 'amina@example.com')
        self.assertContains(response, 'Anonymous')
        by_email = self.changelist(q='amina@')
        self.assertContains(by_email, 'Logged in?')
        self.assertNotContains(by_email, 'Anonymous question?')

    def revise_url(self, question):
        return reverse('admin:qa_question_revise', args=[question.pk])

    def test_revise_page_is_prefilled_with_the_ai_answer_without_markers(self):
        interaction = make_interaction(sentences=[{'text': 'First.', 'quote': 'q', 'number': 1},
                                                  {'text': 'Second.', 'quote': 'q', 'number': 2}])
        response = self.client.get(self.revise_url(interaction.question))
        self.assertContains(response, 'First. Second.</textarea>')

    def test_referred_question_preselects_a_specialist_answer(self):
        interaction = make_interaction(decision=Interaction.Decision.REFER, answer_text='Fixed referral reply.')
        response = self.client.get(self.revise_url(interaction.question))
        self.assertContains(response, 'value="specialist_answer" selected')

    def test_saving_a_revision(self):
        question = make_interaction().question
        response = self.client.post(self.revise_url(question), {
            'text': 'Corrected by the center.', 'reason': 'correction', 'note': 'Checked the source.'})
        self.assertRedirects(response, self.change_page_url(question), fetch_redirect_response=False)
        revision = AnswerRevision.objects.get()
        self.assertEqual((revision.text, revision.author, revision.note),
                         ('Corrected by the center.', self.superuser, 'Checked the source.'))
        page = self.change_page(question)
        self.assertContains(page, 'Corrected by the center.')
        self.assertContains(self.changelist(), 'Center')

    def test_refused_revision_is_shown_on_the_form(self):
        question = make_interaction().question
        response = self.client.post(self.revise_url(question), {'text': ' ', 'reason': 'correction'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Write the answer the asker should see.')
        self.assertFalse(AnswerRevision.objects.exists())

    def test_staff_who_are_not_superusers_cannot_enter(self):
        viewer = make_user(is_staff=True)
        viewer.user_permissions.add(*Permission.objects.filter(codename__in=['view_question', 'add_answerrevision']))
        self.client.force_login(viewer)
        question = make_interaction().question
        for response in (self.change_page(question), self.client.get(self.revise_url(question))):
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('admin:login'), response['Location'])

    def test_answered_by_column(self):
        answered = make_interaction(question=make_question(text='Revised?')).question
        revise(answered, self.superuser, 'By the center.', AnswerRevision.Reason.CORRECTION)
        make_interaction(question=make_question(text='Not revised?'))
        html = self.changelist().content.decode()
        self.assertEqual(html.count('field-answered_by'), 2)

    def change_page_url(self, question):
        return reverse('admin:qa_question_change', args=[question.pk])


class ReferralAdminTests(AdminTestCase):
    """The referrals list, its actions through ``qa.services``, and the sidebar badge (ADR 0021)."""

    def setUp(self):
        super().setUp()
        self.referral = make_referral(question=make_interaction(
            question=make_question(text='Can I combine prayers while travelling?'), decision='refer').question)
        make_membership(center=self.referral.center, user=self.superuser)

    def changelist(self, **params):
        return self.client.get(reverse('admin:qa_referral_changelist'), params)

    def run_action(self, action, referrals, **extra):
        return self.client.post(reverse('admin:qa_referral_changelist'), {
            'action': action, '_selected_action': [referral.pk for referral in referrals], **extra,
        }, follow=True)

    def test_list_shows_the_question_and_the_status_badge(self):
        response = self.changelist()
        self.assertContains(response, 'Can I combine prayers while travelling?')
        self.assertContains(response, 'Not covered by the sources')
        self.assertContains(response, 'Open')

    def test_filter_by_status(self):
        make_referral(question=make_interaction(question=make_question(text='Already answered?'),
                                                decision='refer').question,
                      status=Referral.Status.ANSWERED, answered_at=self.referral.created_at)
        response = self.changelist(status__exact='open')
        self.assertContains(response, 'Can I combine prayers while travelling?')
        self.assertNotContains(response, 'Already answered?')

    def test_change_page_links_to_the_question(self):
        response = self.client.get(reverse('admin:qa_referral_change', args=[self.referral.pk]))
        self.assertContains(response, reverse('admin:qa_question_change', args=[self.referral.question_id]))

    def test_read_only(self):
        self.assertEqual(self.client.get(reverse('admin:qa_referral_add')).status_code, 403)
        response = self.client.get(reverse('admin:qa_referral_change', args=[self.referral.pk]))
        self.assertNotContains(response, 'name="_save"')

    def test_assign_to_me(self):
        response = self.run_action('assign_to_me', [self.referral])
        self.assertEqual(self.messages(response), ['1 referral was updated.'])
        self.referral.refresh_from_db()
        self.assertEqual((self.referral.status, self.referral.assigned_to),
                         (Referral.Status.IN_PROGRESS, self.superuser))

    def test_assign_to_me_reports_refusals(self):
        other = make_referral()  # another center: the superuser is not a member
        response = self.run_action('assign_to_me', [other])
        self.assertIn('Assign the referral to an active member of its center.', self.messages(response)[0])
        other.refresh_from_db()
        self.assertEqual(other.status, Referral.Status.OPEN)

    def test_close_asks_why_then_closes(self):
        response = self.run_action('close_selected', [self.referral])
        self.assertContains(response, 'name="close_note"')
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.OPEN)
        self.run_action('close_selected', [self.referral], apply='1', close_note='Duplicate.')
        self.referral.refresh_from_db()
        self.assertEqual((self.referral.status, self.referral.close_note), (Referral.Status.CLOSED, 'Duplicate.'))

    def test_sidebar_badge_counts_pending_referrals(self):
        self.assertEqual(pending_referrals_badge(None), '1')
        revise(self.referral.question, self.superuser, 'Answer.', AnswerRevision.Reason.SPECIALIST_ANSWER)
        self.assertEqual(pending_referrals_badge(None), '')
