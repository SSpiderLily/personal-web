"""Offline safety checks. Network boundary doubles must never reveal credentials."""
import subprocess
import sys
import unittest
from unittest.mock import patch

from app.settings import Settings

try:
    from app import database
    from app import migrate
except ImportError:
    database = migrate = None


class DatabaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(database, 'shared database module is missing')
        self.assertIsNotNone(migrate, 'versioned migration module is missing')

    def test_import_never_connects(self):
        result = subprocess.run([sys.executable, '-c',
            'import psycopg; psycopg.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("import connected")); import app.database; import app.migrate'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_connection_failure_redacts_driver_message_and_traceback(self):
        import psycopg
        settings = Settings(app_env='development', db_password='never-show-this-password')
        with patch.object(database, 'get_settings', return_value=settings), patch.object(
                psycopg, 'connect', side_effect=psycopg.OperationalError('never-show-this-password')):
            try:
                with database.connection():
                    self.fail('connection unexpectedly opened')
            except database.DatabaseUnavailable as error:
                import traceback
                rendered = ''.join(traceback.format_exception(error))
                self.assertNotIn('never-show-this-password', rendered)
                self.assertIsNone(error.__cause__)
            else:
                self.fail('connection failure must be explicit')

    def test_test_connections_refuse_shared_or_nonlocal_targets_before_driver(self):
        import psycopg
        safe = dict(app_env='test', db_host='127.0.0.1', db_port=25432,
                    db_name='personal_web_test_disposable', db_user='personal_web_test')
        for changed in ({'db_name': 'personal_web_dev'}, {'db_name': 'personal_web_prod'},
                        {'db_host': 'example.com'}, {'db_port': 15432}, {'db_port': 5432},
                        {'db_user': 'personal_web_dev'}):
            with self.subTest(changed=changed), patch.object(database, 'get_settings', return_value=Settings(**(safe | changed))):
                with patch.object(psycopg, 'connect', side_effect=AssertionError('unsafe driver call')):
                    with self.assertRaises(database.DatabaseTargetError):
                        with database.connection():
                            pass

    def test_production_migrations_are_rejected_before_connection(self):
        settings = Settings(app_env='production', db_host='127.0.0.1', db_port=5432,
                            db_name='personal_web_prod', db_user='personal_web_prod', db_password='dummy')
        with patch.object(migrate, 'get_settings', return_value=settings), patch.object(
                database, 'connection', side_effect=AssertionError('production connected')):
            with self.assertRaises(migrate.MigrationError):
                migrate.apply_migrations()
