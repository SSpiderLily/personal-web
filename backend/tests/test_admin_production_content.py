"""Production content initialization against an owned isolated PostgreSQL target."""
import fcntl
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import database, migrate
from app.settings import get_settings, Settings

available = importlib.util.find_spec('app.production_content_init') is not None
if available:
    from app import production_content_init as content


class ProductionContentGuardTests(unittest.TestCase):
    def test_production_content_entry_exists_and_rejects_development_before_connect(self):
        self.assertTrue(available, 'explicit production content entry missing')
        settings = Settings(_env_file=None)
        with patch.object(database, 'transaction') as connect:
            with self.assertRaises(ValueError):
                content.run(settings, 'personal_web_dev', 'personal_web_dev', execute=True)
            connect.assert_not_called()


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'owned isolated runner only')
class ProductionContentDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(available)
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.uploads = self.directory/'uploads'
        self.lock = str(self.directory/'deploy.lock')
        self.settings = get_settings().model_copy(update={'upload_dir':str(self.uploads)})
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE');conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()

    def run_content(self, **kwargs):
        return content.run(self.settings,self.settings.db_name,self.settings.db_user,**kwargs)

    def test_readonly_then_explicit_locked_initialization_and_repeat_preserve_edits(self):
        self.assertEqual(self.run_content()['initialized'],False)
        self.assertFalse(self.uploads.exists())
        self.assertFalse(Path(self.lock).exists())
        with self.assertRaises(ValueError):self.run_content(execute=True)
        with open(self.lock,'w') as lock:
            Path(self.lock).chmod(0o600);fcntl.flock(lock,fcntl.LOCK_EX)
            first=self.run_content(execute=True,lock_file=self.lock,lock_fd=lock.fileno())
            self.assertTrue(first['initialized'])
            with open(self.lock) as probe:
                with self.assertRaises(BlockingIOError):fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with database.transaction() as conn:
            self.assertEqual(conn.execute('SELECT name,status,demo_url FROM projects').fetchone(),('漫游 · 智能旅行助手','published','/trip/'))
            self.assertEqual(conn.execute('SELECT count(*) FROM project_blocks').fetchone()[0],3)
            self.assertEqual(conn.execute('SELECT count(*) FROM admin_accounts').fetchone()[0],0)
            conn.execute("UPDATE projects SET name='owner edit'")
        self.assertEqual(self.run_content(execute=True,lock_file=self.lock),first)
        self.assertEqual(len(list(self.uploads.iterdir())),1)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT name FROM projects').fetchone()[0],'owner edit')
            self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone()[0],1)

    def test_existing_unmarked_content_and_history_drift_refuse_without_creating_files(self):
        with database.transaction() as conn:conn.execute("INSERT INTO site_profile(name,title,introduction) VALUES ('owner','','')")
        with self.assertRaises(ValueError):self.run_content(execute=True,lock_file=self.lock)
        self.assertFalse(self.uploads.exists())
        with database.transaction() as conn:
            conn.execute('DELETE FROM site_profile')
            conn.execute("UPDATE schema_migrations SET checksum=repeat('0',64) WHERE version='003_content_fields'")
        with self.assertRaises(ValueError):self.run_content(execute=True,lock_file=self.lock)
        self.assertFalse(self.uploads.exists())

    def test_failure_rolls_back_database_and_removes_only_new_picture(self):
        with patch('app.content_bootstrap.write_content',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):self.run_content(execute=True,lock_file=self.lock)
        self.assertEqual(list(self.uploads.iterdir()),[])
        with database.connection() as conn:
            for table in ('projects','uploaded_files','site_profile','content_bootstraps'):
                self.assertEqual(conn.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_wrong_expected_identity_and_readonly_lock_arguments_refused(self):
        with self.assertRaises(ValueError):content.run(self.settings,'personal_web_prod','personal_web_prod',execute=True,lock_file=self.lock)
        with self.assertRaises(ValueError):self.run_content(lock_file=self.lock)
        self.assertFalse(self.uploads.exists())
