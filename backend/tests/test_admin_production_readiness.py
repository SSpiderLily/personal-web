import unittest
from unittest.mock import patch
from app.settings import Settings
from app import production_readiness as ready

class ReadinessTests(unittest.TestCase):
 def test_development_refused_before_reading_database(self):
  with patch.object(ready,'transaction') as transaction:
   with self.assertRaises(ValueError):ready.check(Settings())
  transaction.assert_not_called()
 def test_unconfigured_storage_rejected(self):
  s=Settings(app_env='test',db_name='personal_web_test_readiness',db_user='personal_web_test',db_port=25432)
  with self.assertRaises(ValueError):ready.check(s)

if __name__=='__main__':unittest.main()

import io
import os
from pathlib import Path
import tempfile
from app import database, migrate
from app.admin_uploads import save_image
from app.settings import get_settings
from PIL import Image

@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS')=='1','requires disposable PostgreSQL runner')
class RealReadinessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.uploads=Path(self.tmp.name).resolve()/'uploads';self.uploads.mkdir(mode=0o700)
  self.settings=get_settings().model_copy(update={'upload_dir':str(self.uploads)})
  with database.transaction() as conn:
   conn.execute('DROP SCHEMA public CASCADE');conn.execute('CREATE SCHEMA public')
  migrate.apply_migrations()
 def test_readiness_checks_real_metadata_and_images_without_writes(self):
  buffer=io.BytesIO();Image.new('RGB',(2,2),'red').save(buffer,format='PNG')
  save_image(self.settings,buffer.getvalue(),'one.png','image/png')
  result=ready.check(self.settings)
  self.assertTrue(result['ready']);self.assertEqual(result['images'],1)
  with database.transaction() as conn:
   self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone()[0],1)
   self.assertEqual(conn.execute('SELECT count(*) FROM site_daily_visitors').fetchone()[0],0)
   self.assertEqual(conn.execute('SELECT count(*) FROM admin_accounts').fetchone()[0],0)
 def test_missing_file_refuses_ready(self):
  buffer=io.BytesIO();Image.new('RGB',(2,2),'red').save(buffer,format='PNG')
  save_image(self.settings,buffer.getvalue(),'one.png','image/png')
  for child in self.uploads.iterdir():child.unlink()
  with self.assertRaises(Exception):ready.check(self.settings)
