"""Actual deployment adapter CLIs against production-named fixtures in the owned test cluster.

Never uses the configured real production host: the runner must supply its Unix
socket and dedicated port via APP_RUN_DB_TESTS/test Settings first.
"""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import database
from app.settings import get_settings

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('production_pipeline_runtime',ROOT/'scripts/deploy_runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS')=='1','requires owned temporary PostgreSQL runner')
class ProductionAdapterTests(unittest.TestCase):
 def setUp(self):
  self.settings=get_settings()
  database.validate_test_target(self.settings)
  self.assertEqual(self.settings.app_env,'test')
  self.assertTrue(Path(self.settings.db_host).is_absolute())
  self.assertNotIn(self.settings.db_port,(5432,15432))
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.directory=Path(self.tmp.name).resolve()
  self.root=self.directory/'deploy';self.root.mkdir(mode=0o700)
  old=self.root/'old';old.mkdir();(old/'REVISION').write_text('a'*40)
  (self.root/'current').symlink_to(old)
  paths={}
  for name in ('uploads','backups','replica','state'):
   folder=self.directory/name;folder.mkdir(mode=0o700);paths[name]=folder
  with database.connection(self.settings) as conn:
   conn.execute("CREATE ROLE personal_web_prod LOGIN PASSWORD 'temporary-fixture-password'")
   conn.execute('CREATE DATABASE personal_web_prod OWNER personal_web_prod')
  self.addCleanup(self.remove_fixture)
  environment=self.directory/'app.env'
  environment.write_text('\n'.join([
   'APP_ENV=production','DEBUG=false','DB_NAME=personal_web_prod','DB_USER=personal_web_prod',
   'DB_HOST='+self.settings.db_host,'DB_PORT='+str(self.settings.db_port),
   'DB_PASSWORD=temporary-fixture-password','UPLOAD_DIR='+str(paths['uploads']),
   'ADMIN_ALLOWED_ORIGINS=\'["https://local-example.com"]\''])+'\n')
  environment.chmod(0o600)
  self.config={'root':str(self.root),'data_safety':dict(enabled=True,environment_file=str(environment),
   uploads_dir=str(paths['uploads']),backup_root=str(paths['backups']),replica_root=str(paths['replica']),
   maintenance_file=str(paths['state']/'maintenance'),pg_bin=os.environ['APP_TEST_PG_BIN'],
   https_origin='https://local-example.com',prerequisites=dict(tls_verified=True,
    replica_encrypted_offsite=True,restore_drill_passed=True,previous_schema_compatible=True,exclusive_writer_service=True))}
 def remove_fixture(self):
  with database.connection(self.settings) as conn:
   conn.execute('DROP DATABASE personal_web_prod WITH (FORCE)')
   conn.execute('DROP ROLE personal_web_prod')
 def test_real_commands_backup_old_schema_then_migrate_and_verify(self):
  class PublicMarker:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def geturl(self):return 'https://local-example.com/__release.txt'
   def read(self,size):return b'a'*40
  # Only the external TLS transport is simulated; all data commands are real subprocesses.
  with patch.object(runtime.urllib.request,'urlopen',return_value=PublicMarker()):
   self.assertEqual(runtime.preflight(self.config,ROOT)['applied'],[])
  with (self.root/'deploy.lock').open('a') as lock:
   os.fchmod(lock.fileno(),0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   self.assertTrue(runtime.verify_rollback(self.config,ROOT,lock.fileno())['legacy_empty_schema'])
   receipt=runtime.backup(self.config,ROOT,lock.fileno())
   manifest=json.loads((Path(receipt['backup'])/'manifest.json').read_text())
   self.assertEqual(manifest['schema'],[])
   self.assertEqual(manifest['revision'],'a'*40)
   self.assertEqual(runtime.migrate(self.config,ROOT,lock.fileno())['pending'],[])
   self.assertTrue(runtime.verify(self.config,ROOT,lock.fileno())['ready'])
   self.assertTrue(runtime.verify_rollback(self.config,ROOT,lock.fileno())['ready'])

if __name__=='__main__':unittest.main()
