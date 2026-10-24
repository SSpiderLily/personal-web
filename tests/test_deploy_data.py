"""Release data boundary tests; no real services or databases."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy_data_target',Path(__file__).parents[1]/'scripts/deploy.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)

class DataReleaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name).resolve();self.old=self.root/'old';self.new=self.root/'new'
  for p,sha in [(self.old,'a'*40),(self.new,'b'*40)]:p.mkdir();(p/'REVISION').write_text(sha)
  (self.root/'current').symlink_to(self.old)
  self.events=[]
  self.config={'root':str(self.root),'data_safety':{}}
 def phase(self,name,fail=None):
  def f(*a,**kw):
   self.events.append(name)
   if fail:raise RuntimeError(fail)
   return {}
  return f
 def run_release(self,fail=None,rollback_failure=False):
  with patch.object(d,'preflight_data',side_effect=self.phase('preflight')),patch.object(d,'maintenance',side_effect=lambda c,v:self.events.append('maintenance' if v else 'open')),patch.object(d,'stop',side_effect=self.phase('stop')),patch.object(d,'backup_data',side_effect=self.phase('backup','backup failed' if fail=='backup' else None)),patch.object(d,'migrate_data',side_effect=self.phase('migrate','migration failed' if fail=='migrate' else None)),patch.object(d,'verify_data',side_effect=self.phase('verify','readiness failed' if fail=='verify' else None)),patch.object(d,'verify_rollback_data',side_effect=self.phase('rollback-verify')),patch.object(d,'restart',side_effect=self.phase('restart','rollback failed' if rollback_failure else None)),patch.object(d,'wait_healthy',side_effect=self.phase('health')):
   d.activate_data(self.root,self.new,self.config,17)
 def test_order_keeps_writers_stopped_until_verified(self):
  self.run_release()
  self.assertEqual(self.events,['preflight','maintenance','stop','backup','migrate','restart','health','verify','open'])
  self.assertEqual((self.root/'current').resolve(),self.new)
 def test_backup_failure_restarts_old_before_opening(self):
  with self.assertRaisesRegex(RuntimeError,'backup failed'):self.run_release('backup')
  self.assertEqual(self.events,['preflight','maintenance','stop','backup','restart','health','rollback-verify','open'])
  self.assertEqual((self.root/'current').resolve(),self.old)
 def test_migration_failure_keeps_old_link(self):
  with self.assertRaisesRegex(RuntimeError,'migration failed'):self.run_release('migrate')
  self.assertEqual((self.root/'current').resolve(),self.old)
  self.assertEqual(self.events[-4:],['restart','health','rollback-verify','open'])
 def test_new_data_readiness_failure_rolls_back(self):
  with self.assertRaisesRegex(RuntimeError,'readiness failed'):self.run_release('verify')
  self.assertEqual((self.root/'current').resolve(),self.old)
  self.assertEqual(self.events[-4:],['restart','health','rollback-verify','open'])
 def test_rollback_failure_leaves_maintenance(self):
  with self.assertRaisesRegex(RuntimeError,'rollback failed'):self.run_release('backup',True)
  self.assertNotIn('open',self.events)
 def test_failed_rollback_data_probe_keeps_maintenance(self):
  with patch.object(d,'verify_rollback_data',side_effect=RuntimeError('old data unhealthy')):
   # Dedicated phases avoid overriding the rollback probe in run_release().
   with patch.object(d,'preflight_data'),patch.object(d,'maintenance') as marker,patch.object(d,'stop'),patch.object(d,'backup_data',side_effect=RuntimeError('backup failed')),patch.object(d,'restart'),patch.object(d,'wait_healthy'):
    with self.assertRaisesRegex(RuntimeError,'old data unhealthy'):d.activate_data(self.root,self.new,self.config,17)
   self.assertEqual(marker.call_count,1)
   self.assertTrue(marker.call_args.args[1])
 def test_missing_data_contract_rejected_before_fetch(self):
  with patch.object(d,'fetch') as fetch:
   with self.assertRaisesRegex(RuntimeError,'data_safety'):d.deploy({'root':str(self.root)},'b'*40)
  fetch.assert_not_called()

if __name__=='__main__':unittest.main()
