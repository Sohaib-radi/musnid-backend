"""
Public identifier for questions, kept and dropped sentences on interactions, and an
index for session history (ADR 0017).

``Question.uuid`` is added in three steps because existing rows need distinct values:
a field with a callable default would give every existing row the same one.
"""

import uuid

from django.db import migrations, models


def fill_question_uuids(apps, schema_editor):
    """Give each existing question its own uuid."""
    Question = apps.get_model('qa', 'Question')
    for question in Question.objects.filter(uuid__isnull=True).only('pk'):
        question.uuid = uuid.uuid4()
        # updated_at deliberately untouched: a backfill does not change the question.
        question.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('qa', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='uuid',
            field=models.UUIDField(editable=False, null=True, verbose_name='public identifier'),
        ),
        migrations.RunPython(fill_question_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='question',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True,
                                   verbose_name='public identifier'),
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['session_id', '-created_at'], name='question_session_recent'),
        ),
        migrations.AddField(
            model_name='interaction',
            name='sentences',
            field=models.JSONField(
                blank=True, default=list, verbose_name='sentences',
                help_text='Kept sentences: text without citation markers, supporting quote, '
                          'source question number.'),
        ),
        migrations.AddField(
            model_name='interaction',
            name='dropped',
            field=models.JSONField(
                blank=True, default=list, verbose_name='dropped sentences',
                help_text='Sentences removed by the quote or entailment check: text, quote, reason.'),
        ),
    ]
