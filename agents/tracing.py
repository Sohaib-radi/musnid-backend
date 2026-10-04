"""
Declines CrewAI's first-run trace prompt without importing CrewAI.

On a machine's first run, CrewAI asks "view your execution traces? [y/N] (20s timeout)"
after each crew run. The decision is taken when CrewAI is imported: ``crewai.events``
creates its event listener at import, and the listener reads CrewAI's user file then.
``CREWAI_TRACING_ENABLED=false`` does not stop the prompt; only a recorded decline does.
Importing any ``crewai`` module to record it would already be too late, so this module
writes the file itself, at the path and with the keys CrewAI 1.9.3 uses
(``crewai.utilities.paths.db_storage_path`` and
``crewai.events.listeners.tracing.utils.mark_first_execution_done``).
Re-check both after upgrading CrewAI.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import appdirs

logger = logging.getLogger(__name__)

USER_FILE = '.crewai_user.json'


def crewai_user_file():
    """
    Return the path of CrewAI's user file, as CrewAI computes it.

    The directory is ``appdirs.user_data_dir(<name>, 'CrewAI')``, where ``<name>`` is
    ``CREWAI_STORAGE_DIR`` or the name of the current working directory.
    """
    name = os.environ.get('CREWAI_STORAGE_DIR', Path.cwd().name)
    return Path(appdirs.user_data_dir(name, 'CrewAI')) / USER_FILE


def decline_crewai_traces():
    """
    Record "no traces" in CrewAI's user file unless a first run is already recorded.

    Returns True when the file was written. An existing choice (decline or consent) is
    kept. An unreadable file is treated as empty, as CrewAI does. A write failure (for
    example a read-only home directory) is logged, not raised: the service still works,
    and CrewAI's prompt times out after 20 seconds.
    """
    path = crewai_user_file()
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    if data.get('first_execution_done'):
        return False
    data.update(first_execution_done=True, first_execution_at=datetime.now().timestamp(),
                trace_consent=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except OSError as error:
        logger.warning('Could not record the CrewAI trace decline in %s: %s', path, error)
        return False
    return True
