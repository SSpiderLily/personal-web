import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import database, migrate
from app.settings import get_settings
from app.content_bootstrap import bootstrap, BootstrapError

@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'requires owned PostgreSQL')
class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()/'uploads'
        self.settings=get_settings().model_copy(update={'upload_dir':str(self.root)})
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE'); conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()

    def test_preserves_real_content_and_repeat_does_not_overwrite(self):
        result=bootstrap(self.settings)
        with database.transaction() as conn:
            self.assertEqual(conn.execute('SELECT name,status,category FROM projects').fetchone(),('漫游 · 智能旅行助手','published','AI 应用'))
            self.assertEqual(conn.execute('SELECT count(*) FROM project_blocks').fetchone(),(3,))
            conn.execute("UPDATE projects SET name='user edit'")
        self.assertEqual(bootstrap(self.settings),result)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT name FROM projects').fetchone(),('user edit',))
            self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(),(1,))
        self.assertEqual(len(list(self.root.iterdir())),1)

    def test_refuses_existing_user_content_and_production(self):
        with database.transaction() as conn: conn.execute("INSERT INTO projects(name) VALUES ('user')")
        with self.assertRaises(BootstrapError): bootstrap(self.settings)
        self.assertFalse(self.root.exists())
        with patch('app.content_bootstrap.transaction') as connect:
            with self.assertRaises(BootstrapError): bootstrap(self.settings.model_copy(update={'app_env':'production'}))
            connect.assert_not_called()

    def test_rollback_removes_new_file_and_metadata(self):
        with patch('app.content_bootstrap.write_content', side_effect=RuntimeError('temporary failure')):
            with self.assertRaises(RuntimeError): bootstrap(self.settings)
        with database.connection() as conn:
            for table in ('projects','uploaded_files','site_profile','content_bootstraps'):
                self.assertEqual(conn.execute('SELECT count(*) FROM '+table).fetchone(),(0,))
        self.assertEqual(list(self.root.iterdir()),[])

    def test_concurrent_initialization_is_one_transactional_bootstrap(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids=list(pool.map(lambda _:bootstrap(self.settings),range(2)))
        self.assertEqual(ids[0],ids[1])
        with database.connection() as conn:
            for table in ('projects','uploaded_files','site_profile','content_bootstraps'):
                self.assertEqual(conn.execute('SELECT count(*) FROM '+table).fetchone(),(1,))
        self.assertEqual(len(list(self.root.iterdir())),1)
