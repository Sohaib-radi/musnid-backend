"""
Questions of a center (center dashboard): any active member of an operational
center sees the questions sent to it, answers the waiting ones and revises
answers. Views stay thin: answers go through ``qa.services.revise``, the same
rules as Telegram and the admin (the asker sees the latest revision at once, and
the first answer closes the question in Telegram).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import exceptions, generics, permissions, status
from rest_framework.response import Response

from api.permissions import IsCenterMember, IsOperationalCenter
from api.v1.serializers.center_questions import (
    AnswerSerializer, CenterQuestionDetailSerializer, CenterQuestionSerializer,
)
from api.v1.views.mixins import CenterScopedMixin
from qa.models import AnswerRevision, Question, Referral
from qa.services import revise

#: ``?status=`` values: the referral statuses each one lists
STATUS_FILTERS = {
    'waiting': Referral.PENDING,
    'answered': (Referral.Status.ANSWERED,),
    'closed': (Referral.Status.CLOSED,),
    'all': tuple(Referral.Status.values),
}


class CenterQuestionsMixin(CenterScopedMixin):
    """Members of an operational center; only that center's questions."""

    permission_classes = [permissions.IsAuthenticated, IsCenterMember, IsOperationalCenter]

    def center_questions(self):
        return (Question.objects.for_center(self.get_center())
                .select_related('interaction', 'referral').prefetch_related('revisions__author'))


@extend_schema(tags=['center questions'], parameters=[OpenApiParameter(
    'status', str, enum=list(STATUS_FILTERS), description='waiting (default), answered, closed or all.')])
class CenterQuestionListView(CenterQuestionsMixin, generics.ListAPIView):
    """The questions sent to the center (oldest waiting first; others newest first)."""

    serializer_class = CenterQuestionSerializer

    def get_queryset(self):
        wanted = self.request.query_params.get('status', 'waiting')
        if wanted not in STATUS_FILTERS:
            raise exceptions.ValidationError({'status': [exceptions.ErrorDetail(
                f'Choose one of: {", ".join(STATUS_FILTERS)}.', code='invalid_choice')]})
        questions = self.center_questions().filter(referral__status__in=STATUS_FILTERS[wanted])
        # The queue is served oldest first, so the longest-waiting asker is answered first
        return questions.order_by('referral__created_at' if wanted == 'waiting' else '-referral__created_at')


@extend_schema(tags=['center questions'])
class CenterQuestionDetailView(CenterQuestionsMixin, generics.RetrieveAPIView):
    """One question of the center, with its AI answer, ticket and revisions."""

    serializer_class = CenterQuestionDetailSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        return self.center_questions()


@extend_schema(tags=['center questions'], request=AnswerSerializer, responses={201: CenterQuestionDetailSerializer})
class CenterQuestionAnswerView(CenterQuestionsMixin, generics.GenericAPIView):
    """Answer a waiting question, or revise an answer; the asker sees it at once."""

    serializer_class = AnswerSerializer

    def post(self, request, slug, uuid):
        question = get_object_or_404(self.center_questions(), uuid=uuid)
        body = AnswerSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        default = (AnswerRevision.Reason.CORRECTION if question.revisions.exists()
                   else AnswerRevision.Reason.SPECIALIST_ANSWER)
        revise(question, request.user, body.validated_data['text'], body.validated_data.get('reason', default),
               body.validated_data.get('note', ''))
        question = get_object_or_404(self.center_questions(), uuid=uuid)
        return Response(CenterQuestionDetailSerializer(question).data, status=status.HTTP_201_CREATED)
