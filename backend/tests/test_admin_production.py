import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from app import database, migrate
from app.admin_auth import PASSWORDS
from app.settings import Settings, get_settings

production_admin_init = None
if importlib.util.find_spec('app.production_admin_init'):
    from app import production_admin_init


class ProductionAdminCliTests(unittest.TestCase):
    def test_no_password_flags_or_non_tty_execution(self):
        self.assertIsNotNone(production_admin_init, 'production admin entry missing')
        settings = Settings(_env_file=None, app_env='production', db_host='invalid', db_port=5432, db_name='personal_web_prod', db_user='personal_web_prod', db_password='hidden', admin_allowed_origins=['https://example.com'])
        args = ['--expect-database','personal_web_prod','--expect-user','personal_web_prod','--execute','--lock-file','/not-used']
        with patch.object(production_admin_init, 'get_settings', return_value=settings), patch('sys.stdin.isatty', return_value=False), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(production_admin_init.main(args), 1)
        self.assertNotIn('hidden', output.getvalue())
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(production_admin_init.main(args+['--password','must-never-echo']), 2)
        self.assertNotIn('must-never-echo', output.getvalue())


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'isolated runner only')
class ProductionAdminDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(production_admin_init, 'production admin entry missing')
        self.settings = get_settings().model_copy(update={'admin_allowed_origins': ('https://example.com',)})
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = str(Path(self.temp.name).resolve() / 'deploy.lock')
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')

    def initialize(self, **kwargs):
        return production_admin_init.run(self.settings, self.settings.db_name, self.settings.db_user, **kwargs)

    def test_schema_origin_and_existing_account_protection(self):
        with self.assertRaises(ValueError):
            self.initialize()
        migrate.apply_migrations()
        self.assertEqual(self.initialize()['initialized'], False)
        self.assertTrue(self.initialize(execute=True, lock_file=self.lock, username='owner', password='strong-password-123')['initialized'])
        with self.assertRaises(ValueError):
            self.initialize(execute=True, lock_file=self.lock, username='replacement', password='another-password-123')
        with database.connection() as conn:
            username, hashed = conn.execute('SELECT username,password_hash FROM admin_accounts').fetchone()
        self.assertEqual(username, 'owner')
        self.assertTrue(PASSWORDS.verify('strong-password-123', hashed))
        for origins in ((), ('http://example.com',), ('https://example.com/path',)):
            invalid = self.settings.model_copy(update={'admin_allowed_origins': origins})
            with self.assertRaises(ValueError):
                production_admin_init.run(invalid, invalid.db_name, invalid.db_user)

    def terminal_probe(self, mismatch=False):
        # Reuse the existing real controlling-TTY probe; password enters its stdin,
        # then getpass receives it via the child PTY, never child arguments/env.
        probe = Path(__file__).with_name('admin_tty_probe.py').read_text()
        probe = probe.replace("[sys.executable, '-m', 'app.admin_init']", "[sys.executable, '-m', 'app.production_admin_init', *sys.argv[1:]]")
        if mismatch:
            probe = probe.replace("password + b'\\n')", "b'different-password\\n')")
        env = dict(os.environ, ADMIN_ALLOWED_ORIGINS='["https://example.com"]')
        return subprocess.run([sys.executable, '-c', probe, '--expect-database', self.settings.db_name,
                               '--expect-user', self.settings.db_user, '--execute', '--lock-file', self.lock],
                              input=b'terminal-private-password', capture_output=True, timeout=20, env=env)

    def test_real_terminal_double_password_no_echo_and_no_overwrite(self):
        migrate.apply_migrations()
        mismatch = self.terminal_probe(mismatch=True)
        self.assertNotEqual(mismatch.returncode, 0)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM admin_accounts').fetchone(), (0,))
        result = self.terminal_probe()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(b'terminal-private-password', result.stdout + result.stderr)
        self.assertNotEqual(self.terminal_probe().returncode, 0)
        with database.connection() as conn:
            username, hashed = conn.execute('SELECT username,password_hash FROM admin_accounts').fetchone()
        self.assertEqual(username, 'tty-owner')
        self.assertTrue(PASSWORDS.verify('terminal-private-password', hashed))

    def test_history_claim_without_essential_admin_schema_refused(self):
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute('ALTER TABLE admin_accounts DROP COLUMN password_hash')
        with self.assertRaises(ValueError):
            self.initialize(execute=True, lock_file=self.lock, username='owner', password='strong-password-123')
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM admin_accounts').fetchone(), (0,))

    def test_pending_migration_and_invalid_password_refused(self):
        migrate.apply_migrations()
        with self.assertRaises(ValueError):
            self.initialize(execute=True, lock_file=self.lock, username='owner', password='short')
        with database.transaction() as conn:
            conn.execute("DELETE FROM schema_migrations WHERE version='003_content_fields'")
        with self.assertRaises(ValueError):
            self.initialize(execute=True, lock_file=self.lock, username='owner', password='strong-password-123')
