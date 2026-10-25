import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import urllib.error
from io import BytesIO
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

class HttpSshTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name).resolve()/'app.env'
  self.content='APP_ENV=production\nDEBUG=false\nDB_NAME=personal_web_prod\nDB_USER=personal_web_prod\nDB_PASSWORD=private\n'
  base=self.path.parent
  root=base/'release-root';(root/'current').mkdir(parents=True)
  (root/'current/REVISION').write_text('old-revision')
  self.config={'root':str(root),'data_safety':{
   'enabled':True,'mode':'http_ssh','environment_file':str(self.path),
   'uploads_dir':str(base/'uploads'),'backup_root':str(base/'backup'),
   'replica_root':str(base/'mirror'),'pg_bin':'/usr/bin',
   'maintenance_file':str(base/'maintenance'),
   'public_origin':'http://124.223.69.7','admin_origin':'http://127.0.0.1:18880',
   'prerequisites':{key:True for key in ('restore_drill_passed','previous_schema_compatible',
    'exclusive_writer_service','ssh_tunnel_verified','public_admin_blocked','local_backup_accepted')}}}
  self.content+='PRODUCTION_MODE=http_ssh\nPUBLIC_ORIGIN=http://124.223.69.7\nADMIN_ALLOWED_ORIGINS=\'["http://127.0.0.1:18880"]\'\nUPLOAD_DIR='+str(base/'uploads')+'\n'
  self.write(self.content)
 def write(self,text):self.path.write_text(text);self.path.chmod(0o600)
 def fetch(self,request,timeout):
  url=request if isinstance(request,str) else request.full_url
  method='GET' if isinstance(request,str) else request.get_method()
  if url.startswith('http://124.223.69.7/') and ('/admin' in url or '/api/admin' in url):
   raise urllib.error.HTTPError(url,404,'blocked',{},None)
  if url.endswith('/__release.txt'):
   response=BytesIO(b'old-revision');response.geturl=lambda:url
   return response
  if url=='http://127.0.0.1:18880/api/admin/session' and method=='GET':
   raise urllib.error.HTTPError(url,401,'anonymous',{},None)
  raise AssertionError((url,method))
 def test_accepts_explicit_http_ssh_without_tls_or_offsite_evidence(self):
  self.assertEqual(r.data_config(self.config)['mode'],'http_ssh')
  self.assertEqual(r.private_environment(self.path)['PRODUCTION_MODE'],'http_ssh')
 def test_http_ssh_requires_each_own_prerequisite(self):
  for key in self.config['data_safety']['prerequisites']:
   with self.subTest(key=key):
    self.config['data_safety']['prerequisites'][key]=False
    with self.assertRaises(RuntimeError):r.data_config(self.config)
    self.config['data_safety']['prerequisites'][key]=True
 def test_rejects_unsafe_public_and_admin_origins_or_unknown_mode(self):
  data=self.config['data_safety']
  for key,value in [('mode','skip'),('public_origin','http://127.0.0.1'),
    ('public_origin','http://124.223.69.7/'),('public_origin','http://124.223.69.7:80'),
    ('public_origin','https://124.223.69.7'),('public_origin','http://224.0.0.1'),
    ('public_origin','http://[2606:4700:4700::1111]'),('admin_origin','http://localhost:18880'),
    ('admin_origin','http://127.0.0.1:8000')]:
   with self.subTest(key=key,value=value):
    old=data[key];data[key]=value
    with self.assertRaises(RuntimeError):r.data_config(self.config)
    data[key]=old
 def test_http_ssh_preflight_checks_both_release_endpoints_and_blocked_admin(self):
  with patch.object(r.urllib.request,'urlopen',side_effect=self.fetch) as fetch,patch.object(r,'command',return_value={'pending':[]}):
   self.assertEqual(r.preflight(self.config,'/candidate'),{'pending':[]})
  requests=[call.args[0] for call in fetch.call_args_list]
  self.assertEqual([(request if isinstance(request,str) else request.full_url,
    'GET' if isinstance(request,str) else request.get_method()) for request in requests],[
    ('http://124.223.69.7/__release.txt','GET'),
    ('http://127.0.0.1:18880/__release.txt','GET'),
    ('http://124.223.69.7/admin','GET'),
    ('http://124.223.69.7/api/admin/session','GET'),
    ('http://124.223.69.7/api/admin/login','POST'),
    ('http://127.0.0.1:18880/api/admin/session','GET')])
  self.assertIsNone(requests[4].data)
 def test_preflight_rejects_mode_origin_mismatch_before_network(self):
  for old,new in [('PRODUCTION_MODE=http_ssh','PRODUCTION_MODE=https'),
    ('PUBLIC_ORIGIN=http://124.223.69.7','PUBLIC_ORIGIN=http://8.8.8.8'),
    ('["http://127.0.0.1:18880"]','["http://127.0.0.1:18880","http://localhost:18880"]')]:
   self.write(self.content.replace(old,new))
   with self.assertRaises(RuntimeError):r.preflight(self.config,'/candidate')
 def test_preflight_rejects_each_public_admin_exposure(self):
  for path in ('/admin','/api/admin/session','/api/admin/login'):
   def unsafe(request,timeout):
    url=request if isinstance(request,str) else request.full_url
    if url=='http://124.223.69.7'+path:return BytesIO(b'login')
    return self.fetch(request,timeout)
   with self.subTest(path=path),patch.object(r.urllib.request,'urlopen',side_effect=unsafe):
    with self.assertRaises(RuntimeError):r.preflight(self.config,'/candidate')
 def test_preflight_rejects_either_release_stale_or_redirected(self):
  for origin in ('http://124.223.69.7','http://127.0.0.1:18880'):
   for redirected in (False,True):
    def invalid(request,timeout):
     url=request if isinstance(request,str) else request.full_url
     if url==origin+'/__release.txt':
      response=BytesIO(b'wrong-revision' if not redirected else b'old-revision')
      response.geturl=lambda:'http://elsewhere/__release.txt' if redirected else url
      return response
     return self.fetch(request,timeout)
    with self.subTest(origin=origin,redirected=redirected),patch.object(r.urllib.request,'urlopen',side_effect=invalid):
     with self.assertRaises(RuntimeError):r.preflight(self.config,'/candidate')
 def test_private_session_legacy404_allowed_but_configuration503_rejected(self):
  for status in (404,503):
   def session(request,timeout):
    url=request if isinstance(request,str) else request.full_url
    if url=='http://127.0.0.1:18880/api/admin/session':
     raise urllib.error.HTTPError(url,status,'session',{},None)
    return self.fetch(request,timeout)
   with patch.object(r.urllib.request,'urlopen',side_effect=session),patch.object(r,'command',return_value={'pending':[]}):
    if status==404:self.assertEqual(r.preflight(self.config,'/candidate'),{'pending':[]})
    else:
     with self.assertRaises(RuntimeError):r.preflight(self.config,'/candidate')
 def test_default_https_still_requires_tls_and_offsite_prerequisites(self):
  data=self.config['data_safety'];data.pop('mode');data['https_origin']='https://124.223.69.7'
  with self.assertRaises(RuntimeError):r.data_config(self.config)
 def test_https_default_can_preflight_with_its_original_explicit_evidence(self):
  data=self.config['data_safety'];data.pop('mode');data['https_origin']='https://124.223.69.7'
  data['prerequisites'].update(tls_verified=True,replica_encrypted_offsite=True)
  self.write(self.content.replace('PRODUCTION_MODE=http_ssh\n','').replace('["http://127.0.0.1:18880"]','["https://124.223.69.7"]'))
  with patch.object(r.urllib.request,'urlopen',side_effect=self.fetch),patch.object(r,'command',return_value={'pending':[]}):
   self.assertEqual(r.preflight(self.config,'/candidate'),{'pending':[]})

if __name__=='__main__':unittest.main()
