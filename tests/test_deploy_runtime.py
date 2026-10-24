import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('runtime_target',Path(__file__).parents[1]/'scripts/deploy_runtime.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class EnvironmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name).resolve()/'app.env'
  self.content='APP_ENV=production\nDEBUG=false\nDB_NAME=personal_web_prod\nDB_USER=personal_web_prod\nDB_HOST=127.0.0.1\nDB_PORT=5432\nDB_PASSWORD=\'literal$secret;$(never-run)\'\n'
  self.write(self.content)
 def write(self,text):self.path.write_text(text);self.path.chmod(0o600)
 def test_literal_password_no_shell_expansion_or_inherited_overrides(self):
  with patch.dict(os.environ,{'DB_NAME':'wrong','PGSERVICE':'wrong','LD_PRELOAD':'wrong'}):
   env=r.private_environment(self.path)
  self.assertEqual(env['DB_PASSWORD'],'literal$secret;$(never-run)')
  self.assertEqual(env['DB_NAME'],'personal_web_prod')
  self.assertNotIn('PGSERVICE',env);self.assertNotIn('LD_PRELOAD',env)
 def test_readable_to_world_file_and_symlink_rejected(self):
  self.path.chmod(0o644)
  with self.assertRaises(RuntimeError):r.private_environment(self.path)
  self.path.chmod(0o600);link=self.path.with_name('link');link.symlink_to(self.path)
  with self.assertRaises(RuntimeError):r.private_environment(link)
 def test_unknown_duplicate_and_nonproduction_rejected_without_echo(self):
  for content in [self.content+'PATH=/unsafe\n',self.content+'DB_NAME=wrong\n',self.content.replace('APP_ENV=production','APP_ENV=development')]:
   self.write(content)
   with self.assertRaises(RuntimeError) as failure:r.private_environment(self.path)
   self.assertNotIn('literal$secret',str(failure.exception))
 def test_operation_error_does_not_echo_driver_output_or_credentials(self):
  result=subprocess.CompletedProcess([],1,'secretdata','password=secret')
  with patch.object(r.subprocess,'run',return_value=result):
   with self.assertRaises(RuntimeError) as failure:r.command('/release',['-m','safe'],{})
  self.assertNotIn('secret',str(failure.exception))
 def test_inherited_fd_passed_without_a_shell(self):
  with self.path.open() as fd,patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{}','')) as run:
   r.command('/release',['-m','safe'],{},fd.fileno())
   self.assertEqual(run.call_args.kwargs['pass_fds'],(fd.fileno(),))
   self.assertNotIn('shell',run.call_args.kwargs)

if __name__=='__main__':unittest.main()
