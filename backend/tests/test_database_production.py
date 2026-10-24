"""Production command safety; all actual SQL uses runner-owned test cluster."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import contextlib
import io
import time
import importlib.util
import os
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import database, migrate
from app.settings import Settings, get_settings

production_migrate = None
if importlib.util.find_spec('app.production_migrate'):
    from app import production_migrate


class ProductionTargetTests(unittest.TestCase):
    def test_development_and_wrong_production_identity_refused_before_connection(self):
        self.assertIsNotNone(production_migrate, 'production migration command missing')
        for settings in (Settings(_env_file=None, app_env='development'), Settings(_env_file=None, app_env='production', db_host='invalid', db_port=5432, db_name='other', db_user='other', db_password='secret')):
            with patch.object(database, 'connection', side_effect=AssertionError('must not connect')):
                with self.assertRaises(ValueError):
                    production_migrate.run(settings, 'personal_web_prod', 'personal_web_prod')


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'isolated runner only')
class ProductionMigrationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(production_migrate, 'production migration command missing')
        self.settings = get_settings()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = str(Path(self.temp.name).resolve() / 'deploy.lock')
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')

    def run_command(self, **kwargs):
        return production_migrate.run(self.settings, self.settings.db_name, self.settings.db_user, **kwargs)

    def test_readonly_no_history_no_table_creation_and_execute_idempotent(self):
        result = self.run_command()
        self.assertEqual(result, {'database': self.settings.db_name, 'user': 'personal_web_test', 'applied': [], 'pending': ['001_admin_schema', '002_tool_defaults', '003_content_fields']})
        with database.connection() as conn:
            self.assertIsNone(conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0])
        result = self.run_command(execute=True, lock_file=self.lock)
        self.assertEqual(result['pending'], [])
        self.assertEqual(len(result['applied']), 3)
        self.assertEqual(self.run_command(execute=True, lock_file=self.lock), result)

    def test_missing_lock_and_identity_mismatch_are_refused(self):
        with self.assertRaises(ValueError):
            self.run_command(execute=True)
        with self.assertRaises(ValueError):
            production_migrate.run(self.settings, 'wrong', self.settings.db_user)

    def test_history_drift_prefix_and_failed_pending_batch_are_atomic(self):
        folder = Path(self.temp.name) / 'migrations'
        folder.mkdir()
        (folder / '001_probe.sql').write_text('CREATE TABLE probe(id integer);')
        (folder / '002_fail.sql').write_text('SELECT missing FROM probe;')
        with self.assertRaises(migrate.MigrationError):
            self.run_command(execute=True, lock_file=self.lock, directory=folder)
        with database.connection() as conn:
            self.assertEqual(conn.execute("SELECT to_regclass('public.probe'), to_regclass('public.schema_migrations')").fetchone(), (None, None))
        self.run_command(execute=True, lock_file=self.lock)
        with database.transaction() as conn:
            conn.execute("UPDATE schema_migrations SET checksum=repeat('0',64) WHERE version='002_tool_defaults'")
        with self.assertRaises(migrate.MigrationError):
            self.run_command()

    def test_inherited_lock_same_inode_held_and_preserved(self):
        with open(self.lock, 'w') as owner:
            with self.assertRaises(ValueError):
                self.run_command(execute=True, lock_file=self.lock, lock_fd=owner.fileno())
            fcntl.flock(owner, fcntl.LOCK_EX)
            self.run_command(execute=True, lock_file=self.lock, lock_fd=owner.fileno())
            with open(self.lock) as probe:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            other = Path(self.temp.name).resolve() / 'other.lock'
            other.touch()
            with self.assertRaises(ValueError):
                self.run_command(execute=True, lock_file=str(other), lock_fd=owner.fileno())
        with open(self.lock) as unlocked, open(self.lock) as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            with self.assertRaises(ValueError):
                self.run_command(execute=True, lock_file=self.lock, lock_fd=unlocked.fileno())

    def test_production_settings_real_identity_mismatch_uses_only_isolated_connection(self):
        production = Settings(_env_file=None, app_env='production', db_host='never-contact.invalid',
                              db_port=5432, db_name='personal_web_prod', db_user='personal_web_prod', db_password='private')
        isolated_transaction = database.transaction
        @contextlib.contextmanager
        def isolated_only(settings):
            # No production credential or address can reach psycopg in this test.
            with isolated_transaction(self.settings) as conn:
                yield conn
        with patch.object(database, 'transaction', isolated_only):
            with self.assertRaisesRegex(ValueError, 'Connected database/account'):
                production_migrate.run(production, 'personal_web_prod', 'personal_web_prod')
        with database.connection() as conn:
            self.assertIsNone(conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0])

    def test_readonly_preflight_rejects_attempted_writes(self):
        def malicious_snapshot(conn, *args):
            conn.execute('CREATE TABLE forbidden(id integer)')
        with patch.object(production_migrate, 'snapshot', malicious_snapshot):
            with self.assertRaises(migrate.MigrationError):
                self.run_command()
        with database.connection() as conn:
            self.assertIsNone(conn.execute("SELECT to_regclass('public.forbidden')").fetchone()[0])

    def test_release_contention_symlink_and_history_hole_refused(self):
        with open(self.lock, 'w') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            with self.assertRaises(ValueError):
                self.run_command(execute=True, lock_file=self.lock)
        link = Path(self.lock + '.link')
        link.symlink_to(self.lock)
        with self.assertRaises(ValueError):
            self.run_command(execute=True, lock_file=str(link))
        self.run_command(execute=True, lock_file=self.lock)
        with database.transaction() as conn:
            conn.execute("DELETE FROM schema_migrations WHERE version='002_tool_defaults'")
        with self.assertRaises(migrate.MigrationError):
            self.run_command(execute=True, lock_file=self.lock)

    def test_preflight_waits_for_existing_database_migration_lock(self):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with database.transaction() as holder:
                holder.execute('SELECT pg_advisory_xact_lock(%s)', (794675013001,))
                future = executor.submit(self.run_command)
                deadline = time.monotonic() + 3
                with database.connection() as observer:
                    while True:
                        waiting = observer.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted").fetchone()[0]
                        if waiting:
                            break
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(0.01)
                self.assertFalse(future.done())
            self.assertEqual(future.result(timeout=3)['applied'], [])

    def test_cli_json_and_safe_driver_failure(self):
        argv = ['--expect-database', self.settings.db_name, '--expect-user', self.settings.db_user]
        with patch.object(production_migrate, 'get_settings', return_value=self.settings), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(production_migrate.main(argv), 0)
        import json
        self.assertEqual(json.loads(output.getvalue())['applied'], [])
        with patch.object(production_migrate, 'get_settings', side_effect=ValueError('credential-sensitive-input')), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(production_migrate.main(argv), 1)
        self.assertNotIn('credential-sensitive-input', output.getvalue())

    def test_inherited_shared_lock_is_not_a_release_exclusive_lock(self):
        with open(self.lock, 'w') as owner:
            fcntl.flock(owner, fcntl.LOCK_SH)
            with self.assertRaises(ValueError):
                self.run_command(execute=True, lock_file=self.lock, lock_fd=owner.fileno())

    def test_real_subprocess_inherits_and_preserves_release_lock(self):
        with open(self.lock, 'w') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            result = subprocess.run([sys.executable, '-m', 'app.production_migrate',
                '--expect-database', self.settings.db_name, '--expect-user', self.settings.db_user,
                '--execute', '--lock-file', self.lock, '--lock-fd', str(owner.fileno())],
                pass_fds=(owner.fileno(),), capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['pending'], [])
            with open(self.lock) as probe:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_concurrent_release_and_advisory_lock(self):
        # Distinct release locks still serialize on the established database lock.
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda n: self.run_command(execute=True, lock_file=self.lock+str(n)), range(2)))
        self.assertTrue(all(len(result['applied']) == 3 and not result['pending'] for result in results))
