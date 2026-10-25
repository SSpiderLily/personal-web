"""Offline safety checks. Network boundary doubles must never reveal credentials."""
import os
import socket
import subprocess
import threading
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

    def test_libpq_hostaddr_cannot_redirect_settings_to_another_address(self):
        # A real IPv4 listener detects libpq overriding the configured IPv6 target.
        accepted = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(.3)
            def accept_probe():
                try:
                    client, _ = listener.accept()
                    accepted.set()
                    client.close()
                except TimeoutError:
                    pass
            probe = threading.Thread(target=accept_probe)
            probe.start()
            settings = Settings(app_env='test', db_host='::1', db_port=listener.getsockname()[1],
                                db_name='personal_web_test_probe', db_user='personal_web_test', db_password='dummy')
            rejected = False
            try:
                with patch.dict(os.environ, {'PGHOSTADDR': '127.0.0.1'}):
                    try:
                        with database.connection(settings):
                            self.fail('libpq environment override must be refused')
                    except database.DatabaseTargetError:
                        rejected = True
                    except database.DatabaseUnavailable:
                        pass
            finally:
                probe.join(timeout=1)
            self.assertFalse(accepted.is_set(), 'libpq reached the IPv4 address absent from Settings')
            self.assertTrue(rejected, 'hidden libpq configuration must be rejected explicitly')

    def test_libpq_environment_is_rejected_without_values_or_environment_mutation(self):
        import psycopg
        settings = Settings(app_env='development', db_password='dummy')
        for name in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGSYSCONFDIR',
                     'PGPASSWORD', 'PGPASSFILE', 'PGSSLMODE', 'PGOPTIONS', 'PGTZ'):
            with self.subTest(name=name), patch.dict(os.environ, {name: 'private-override-value'}):
                before = dict(os.environ)
                with patch.object(psycopg, 'connect', side_effect=AssertionError('driver must not receive hidden configuration')):
                    with self.assertRaises(database.DatabaseTargetError) as caught:
                        with database.connection(settings):
                            pass
                self.assertNotIn('private-override-value', str(caught.exception))
                self.assertEqual(dict(os.environ), before)

    def test_test_target_refuses_comma_separated_host_before_driver(self):
        import psycopg
        settings = Settings(app_env='test', db_host='/tmp/owned,remote.example', db_port=25432,
                            db_name='personal_web_test_probe', db_user='personal_web_test')
        with patch.object(psycopg, 'connect', side_effect=AssertionError('multihost driver call')):
            with self.assertRaises(database.DatabaseTargetError):
                with database.connection(settings):
                    pass
