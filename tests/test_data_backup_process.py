"""Interrupt cleanup at process creation, without touching any database."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backup_process_probe', Path(__file__).parents[1] / 'scripts/data_backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
from app.settings import Settings


class BackupProcessTests(unittest.TestCase):
    def test_interrupt_during_spawn_reaps_child_before_removing_credentials(self):
        settings = Settings(_env_file=None, app_env='test', db_host='/tmp/not-used', db_port=25435,
                            db_name='personal_web_test_interrupt', db_user='personal_web_test', db_password='synthetic')
        children = []
        credentials = []
        original_popen = subprocess.Popen

        def spawn_and_interrupt(*args, **kwargs):
            credentials.append(Path(kwargs['env']['PGPASSFILE']))
            self.assertTrue(credentials[-1].exists())
            child = original_popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(child)
            # Deliver the signal after the OS child exists, before Popen returns.
            os.kill(os.getpid(), signal.SIGINT)
            return child

        try:
            with patch.object(backup.subprocess, 'Popen', side_effect=spawn_and_interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    backup.pg_run(Path('/not-executed'), settings, [])
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll(), 'Interrupted backup left its child running')
            self.assertFalse(credentials[0].exists())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
