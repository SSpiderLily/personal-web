"""Only scripts/test-db.sh enables these against its own disposable cluster."""
from concurrent.futures import ThreadPoolExecutor
import os
import hashlib
import subprocess
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    import psycopg
    from app import database, migrate
except ImportError:
    database = migrate = None


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'run bash scripts/test-db.sh for isolated PostgreSQL tests')
class DatabaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(database, 'shared database module is missing')
        self.assertIsNotNone(migrate, 'versioned migration module is missing')
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')

    def test_commit_rollback_and_connection_closure(self):
        with database.transaction() as conn:
            conn.execute('CREATE TABLE probe (value integer)')
            conn.execute('INSERT INTO probe VALUES (7)')
        self.assertTrue(conn.closed)
        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with database.transaction() as conn:
                conn.execute('INSERT INTO probe VALUES (9)')
                raise RuntimeError('abort')
        self.assertTrue(conn.closed)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT value FROM probe').fetchall(), [(7,)])
        self.assertTrue(conn.closed)

    def test_repeated_migration_keeps_existing_data_and_constraints(self):
        self.assertEqual(migrate.apply_migrations(), ['001_admin_schema', '002_tool_defaults'])
        with database.transaction() as conn:
            project_id = conn.execute("INSERT INTO projects(name) VALUES ('retain me') RETURNING id").fetchone()[0]
        self.assertEqual(migrate.apply_migrations(), [])
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT name FROM projects').fetchall(), [('retain me',)])
            self.assertEqual(conn.execute('SELECT count(*) FROM schema_migrations').fetchone(), (2,))
            self.assertEqual(conn.execute('SELECT count(*) FROM tool_settings').fetchone(), (10,))
            for table in ('admin_accounts', 'admin_sessions', 'uploaded_files', 'site_profile', 'site_daily_visitors', 'project_daily_visitors', 'project_blocks', 'project_screenshots'):
                self.assertEqual(conn.execute(f'SELECT count(*) FROM {table}').fetchone(), (0,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with database.transaction() as conn:
                conn.execute("INSERT INTO project_blocks(project_id, position, kind, body) VALUES (%s, 0, 'text', 'x')", (project_id + 1,))
        with self.assertRaises(psycopg.errors.CheckViolation):
            with database.transaction() as conn:
                conn.execute("INSERT INTO projects(status) VALUES ('invalid')")
        class RollbackFixtures(Exception):
            pass
        with self.assertRaises(RollbackFixtures):
            with database.transaction() as conn:
                conn.execute("SET LOCAL personal_web.schema_test = 'rollback-only'")
                conn.execute((migrate.MIGRATIONS / 'tests/assert_initial_schema.sql').read_text())
                raise RollbackFixtures()

    def test_mismatch_and_unknown_history_are_rejected(self):
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute("UPDATE schema_migrations SET checksum = repeat('0', 64)")
        with self.assertRaises(migrate.MigrationError):
            migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute('DELETE FROM schema_migrations')
            conn.execute("INSERT INTO schema_migrations VALUES ('999_missing', repeat('0',64), now())")
        with self.assertRaises(migrate.MigrationError):
            migrate.apply_migrations()

    def test_all_pending_migrations_roll_back_together(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / '001_first.sql').write_text('CREATE TABLE first_probe (id integer);')
            (folder / '002_broken.sql').write_text('SELECT missing_column FROM first_probe;')
            with self.assertRaises(migrate.MigrationError):
                migrate.apply_migrations(folder)
        with database.connection() as conn:
            self.assertEqual(conn.execute("SELECT to_regclass('public.first_probe'), to_regclass('public.schema_migrations')").fetchone(), (None, None))

    def test_concurrent_migration_waits_for_same_advisory_lock(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            with database.transaction() as blocker:
                blocker.execute('SELECT pg_advisory_xact_lock(794675013001)')
                futures = [executor.submit(migrate.apply_migrations) for _ in range(2)]
                # Observe PostgreSQL lock wait, not just thread scheduling.
                deadline = time.monotonic() + 4
                while True:
                    with database.connection() as observer:
                        waiting = observer.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted").fetchone()[0]
                    if waiting == 2:
                        break
                    self.assertLess(time.monotonic(), deadline, 'both migration callers must wait on the advisory lock')
                    time.sleep(.02)
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual(sorted(results, key=len), [[], ['001_admin_schema', '002_tool_defaults']])

    def test_existing_psql_entry_and_python_share_history(self):
        from app.settings import Settings, get_settings
        settings = get_settings()
        with database.connection() as conn:
            conn.execute('CREATE ROLE personal_web_dev LOGIN')
            conn.execute('CREATE DATABASE personal_web_dev OWNER personal_web_dev')
        checksum = 'b47c9141e0b42926660dc7002230910a1b7254e76a516f824f9650c4672b6d1c'
        psql = [str(Path(os.environ['APP_TEST_PG_BIN']) / 'psql'), '-X', '-h', settings.db_host,
                '-p', str(settings.db_port), '-U', 'personal_web_dev', '-d', 'personal_web_dev',
                '-v', 'ON_ERROR_STOP=1']
        for _ in range(2):
            result = subprocess.run(psql + ['-v', f'migration_checksum={checksum}',
                                            '-f', str(migrate.MIGRATIONS / 'apply_dev.sql')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        local_dev = Settings(app_env='development', db_host=settings.db_host, db_port=settings.db_port,
                             db_name='personal_web_dev', db_user='personal_web_dev', db_password='')
        with database.connection(local_dev) as conn:
            self.assertEqual(conn.execute('SELECT version, checksum FROM schema_migrations').fetchall(), [('001_admin_schema', checksum)])
        with patch.object(migrate, 'get_settings', return_value=local_dev):
            self.assertEqual(migrate.apply_migrations(), ['002_tool_defaults'])
            self.assertEqual(migrate.apply_migrations(), [])
        # A psql mismatch fails without replacing the existing history.
        result = subprocess.run(psql + ['-v', 'migration_checksum=' + '0' * 64,
                                        '-f', str(migrate.MIGRATIONS / 'apply_dev.sql')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        with database.connection(local_dev) as conn:
            self.assertEqual(conn.execute('SELECT version, checksum FROM schema_migrations ORDER BY version').fetchall(),
                             [('001_admin_schema', checksum), ('002_tool_defaults', hashlib.sha256((migrate.MIGRATIONS / '002_tool_defaults.sql').read_bytes()).hexdigest())])

    def test_later_version_extends_schema_without_replaying_old_version(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / '001_first.sql').write_text('CREATE TABLE version_probe (id integer PRIMARY KEY);')
            self.assertEqual(migrate.apply_migrations(folder), ['001_first'])
            with database.transaction() as conn:
                conn.execute('INSERT INTO version_probe VALUES (7)')
            (folder / '002_extend.sql').write_text('ALTER TABLE version_probe ADD COLUMN title text;')
            self.assertEqual(migrate.apply_migrations(folder), ['002_extend'])
            self.assertEqual(migrate.apply_migrations(folder), [])
            with database.connection() as conn:
                self.assertEqual(conn.execute('SELECT id, title FROM version_probe').fetchall(), [(7, None)])
            (folder / '002_duplicate.sql').write_text('DROP TABLE version_probe;')
            with self.assertRaises(migrate.MigrationError):
                migrate.apply_migrations(folder)
            with database.connection() as conn:
                self.assertEqual(conn.execute('SELECT id FROM version_probe').fetchall(), [(7,)])
