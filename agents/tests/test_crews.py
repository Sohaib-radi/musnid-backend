"""Tests for agents/crews: YAML configuration, output shapes, LLM settings, CrewAI env."""

import os
from unittest import mock

from django.test import TestCase

from agents.crews import Classification, VerifiedAnswer, build_llm, prompt_version
from core.models import AISettings

KEY = 'sk-test-0000000000000000000000'


@mock.patch('agents.crews.credentials.get_openai_key', return_value=KEY)
class CrewDefinitionTests(TestCase):
    """Crews load their YAML and return structured output, without calling an LLM."""

    def test_classify_crew(self, _key):
        from agents.crews.classify_crew.classify_crew import ClassifyCrew
        crew = ClassifyCrew().crew()
        self.assertEqual([t.output_pydantic for t in crew.tasks], [Classification])
        self.assertIn('{question}', crew.tasks[0].description)
        self.assertFalse(crew.verbose)

    def test_answer_crew_is_writer_then_verifier(self, _key):
        from agents.crews.answer_crew.answer_crew import AnswerCrew
        crew = AnswerCrew().crew()
        self.assertEqual([a.role.strip() for a in crew.agents], ['Evidence-bound writer', 'Strict verifier'])
        self.assertEqual(crew.tasks[-1].output_pydantic, VerifiedAnswer)
        write = crew.tasks[0].description
        for rule in ('ONLY from the evidence', '[آية]', 'NEVER quote the Quran or hadith', 'scholars differ'):
            self.assertIn(rule, write)

    def test_verifier_uses_its_own_model_when_set(self, _key):
        from agents.crews.answer_crew.answer_crew import AnswerCrew
        settings = AISettings.load()
        settings.verifier_model = 'gpt-4o'
        settings.save()
        writer, verifier = AnswerCrew().crew().agents
        self.assertEqual((writer.llm.model, verifier.llm.model), ('gpt-4o-mini', 'gpt-4o'))

    def test_llm_follows_ai_settings(self, _key):
        settings = AISettings.load()
        settings.chat_model, settings.temperature = 'gpt-4o', 0.5
        settings.save()
        llm = build_llm()
        self.assertEqual((llm.model, llm.temperature), ('gpt-4o', 0.5))


class MiscTests(TestCase):
    """Prompt version and CrewAI's environment switches."""

    def test_prompt_version_is_a_short_hash(self):
        version = prompt_version()
        self.assertEqual(len(version), 12)
        int(version, 16)

    def test_crewai_telemetry_and_tracing_are_off(self):
        self.assertEqual(os.environ['CREWAI_DISABLE_TELEMETRY'], 'true')
        self.assertEqual(os.environ['OTEL_SDK_DISABLED'], 'true')
        self.assertEqual(os.environ['CREWAI_TRACING_ENABLED'], 'false')

    def test_ai_settings_is_a_singleton(self):
        first, second = AISettings.load(), AISettings(chat_model='x')
        second.save()
        self.assertEqual(AISettings.objects.count(), 1)
        self.assertEqual(first.pk, second.pk)
