"""
Questions of a center, for its specialists (center dashboard): the queue of
questions sent to the center, one question with its AI answer and revision
history, and the answer form. Internal to the center: the asker is never shown;
specialists' names are (they are colleagues).
"""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from qa.models import AnswerRevision, Question, Referral
from qa.services import TEXT_MAX


class TicketSerializer(serializers.ModelSerializer):
    """The referral (ticket) of a question sent to the center."""

    class Meta:
        model = Referral
        fields = ['status', 'mode', 'reason', 'live_until', 'answered_at', 'closed_at', 'created_at']
        read_only_fields = fields


class RevisionSerializer(serializers.ModelSerializer):
    """One revision of the answer, with its author's name (internal to the center)."""

    author = serializers.SerializerMethodField(help_text="The specialist's name; null if the account was deleted.")

    class Meta:
        model = AnswerRevision
        fields = ['text', 'lang', 'translated_text', 'reason', 'note', 'author', 'created_at']
        read_only_fields = fields

    def get_author(self, revision) -> str | None:
        return revision.author.full_name if revision.author else None


class CenterQuestionSerializer(serializers.ModelSerializer):
    """A question in the center's queue."""

    language = serializers.CharField(source='lang')
    ticket = serializers.SerializerMethodField()
    answered_by = serializers.SerializerMethodField(help_text='ai, or center once a specialist answered.')

    class Meta:
        model = Question
        fields = ['uuid', 'text', 'language', 'created_at', 'ticket', 'answered_by']
        read_only_fields = fields

    @extend_schema_field(TicketSerializer(allow_null=True))
    def get_ticket(self, question):
        try:
            return TicketSerializer(question.referral).data
        except ObjectDoesNotExist:
            return None

    def get_answered_by(self, question) -> str:
        return 'center' if question.latest_revision() else 'ai'


class CenterQuestionDetailSerializer(CenterQuestionSerializer):
    """One question: what the AI did, what the asker sees now, and every revision (newest first)."""

    decision = serializers.SerializerMethodField(help_text='answer, partial, refer, abstain or out_of_scope.')
    level = serializers.SerializerMethodField()
    ai_answer = serializers.SerializerMethodField(help_text='The AI answer or fixed reply, never changed.')
    current_answer = serializers.SerializerMethodField(help_text='What the asker sees now: the latest revision, '
                                                                 'else the AI answer.')
    revisions = serializers.SerializerMethodField()

    class Meta(CenterQuestionSerializer.Meta):
        fields = [*CenterQuestionSerializer.Meta.fields, 'decision', 'level', 'ai_answer', 'current_answer',
                  'revisions']
        read_only_fields = fields

    @staticmethod
    def _interaction(question):
        return getattr(question, 'interaction', None)

    def get_decision(self, question) -> str:
        interaction = self._interaction(question)
        return interaction.decision if interaction else ''

    def get_level(self, question) -> str | None:
        interaction = self._interaction(question)
        return interaction.level if interaction else None

    def get_ai_answer(self, question) -> str:
        interaction = self._interaction(question)
        return interaction.answer_text if interaction else ''

    def get_current_answer(self, question) -> str:
        revision = question.latest_revision()
        return revision.shown_text if revision else self.get_ai_answer(question)

    @extend_schema_field(RevisionSerializer(many=True))
    def get_revisions(self, question):
        revisions = sorted(question.revisions.all(), key=lambda revision: revision.created_at, reverse=True)
        return RevisionSerializer(revisions, many=True).data


class AnswerSerializer(serializers.Serializer):
    """A specialist's answer or revision, saved through ``qa.services.revise``."""

    text = serializers.CharField(max_length=TEXT_MAX, help_text='What the asker will see.')
    reason = serializers.ChoiceField(
        choices=AnswerRevision.Reason.choices, required=False,
        help_text='Default: specialist_answer for a first answer, correction for a later revision.')
    note = serializers.CharField(required=False, allow_blank=True, help_text='Internal; never shown to the asker.')
