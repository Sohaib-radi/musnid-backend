"""Tests for agents/tracing.py: CrewAI's first-run trace prompt is declined before import."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from agents.tracing import crewai_user_file, decline_crewai_traces

# Runs in a fresh interpreter, where CrewAI has never been imported: Django setup, then
# the flow import, then the checks CrewAI makes before prompting.
CHILD = '''
import json
import django
django.setup()
import agents.flow
from crewai.events.listeners.tracing.trace_listener import TraceCollectionListener
from crewai.events.listeners.tracing.utils import (
    has_user_declined_tracing, should_auto_collect_first_time_traces)
from agents.tracing import crewai_user_file
print(json.dumps({
    'declined': has_user_declined_tracing(),
    'auto_collect': should_auto_collect_first_time_traces(),
    'first_time': TraceCollectionListener().first_time_handler.is_first_time,
    'file': str(crewai_user_file()),
}))
'''


class DeclineTests(SimpleTestCase):
    """``decline_crewai_traces`` on a temporary user file."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'CrewAI' / '.crewai_user.json'
        patcher = mock.patch('agents.tracing.crewai_user_file', return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self):
        return json.loads(self.path.read_text())

    def test_writes_the_decline_when_no_file_exists(self):
        self.assertTrue(decline_crewai_traces())
        data = self.read()
        self.assertIs(data['first_execution_done'], True)
        self.assertIs(data['trace_consent'], False)

    def test_keeps_an_existing_choice(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({'first_execution_done': True, 'trace_consent': True}))
        self.assertFalse(decline_crewai_traces())
        self.assertIs(self.read()['trace_consent'], True)

    def test_keeps_other_keys(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({'user_id': 'abc'}))
        decline_crewai_traces()
        self.assertEqual(self.read()['user_id'], 'abc')
        self.assertIs(self.read()['trace_consent'], False)

    def test_replaces_an_unreadable_file(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('not json')
        self.assertTrue(decline_crewai_traces())
        self.assertIs(self.read()['first_execution_done'], True)

    def test_logs_a_write_failure_without_raising(self):
        with mock.patch.object(Path, 'write_text', side_effect=PermissionError('read-only')), \
                self.assertLogs('agents.tracing', 'WARNING'):
            self.assertFalse(decline_crewai_traces())


class CrewAIContractTests(SimpleTestCase):
    """The file we write is the one CrewAI reads, with the meaning CrewAI gives it."""

    def test_path_matches_crewai(self):
        from crewai.utilities.paths import db_storage_path

        self.assertEqual(crewai_user_file().parent, Path(db_storage_path()))

    def test_importing_the_flow_never_prompts(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home, 'CREWAI_STORAGE_DIR': 'musnid-test',
                   'DJANGO_SETTINGS_MODULE': 'config.settings'}
            env.pop('XDG_DATA_HOME', None)
            env.pop('CREWAI_TESTING', None)  # would hide the prompt by itself
            child = subprocess.run(
                [sys.executable, '-c', CHILD], cwd=settings.BASE_DIR, env=env,
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual(child.returncode, 0, child.stderr[-2000:])
        result = json.loads(child.stdout.strip().splitlines()[-1])
        self.assertTrue(result['file'].startswith(home), 'user file outside the test home')
        self.assertIs(result['declined'], True)
        self.assertIs(result['auto_collect'], False)
        self.assertIs(result['first_time'], False)
        self.assertNotIn('execution traces', child.stdout + child.stderr)
