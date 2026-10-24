"""D composition contract on owned temporary SQL/files, never shared databases."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import database, migrate, admin_auth as auth
from app.settings import get_settings
from test_admin_uploads import HEADERS, ORIGIN, picture

@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'requires owned temporary PostgreSQL')
class StageDJointTests(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.app=app
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()/'uploads'
        self.settings=get_settings().model_copy(update={'upload_dir':str(self.root)})
        self.app.dependency_overrides[get_settings]=lambda:self.settings
        self.addCleanup(self.app.dependency_overrides.clear)
        database.validate_test_target(self.settings)
        with database.transaction(self.settings) as conn:
            conn.execute('DROP SCHEMA public CASCADE');conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        with database.transaction(self.settings) as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)',('owner',auth.PASSWORDS.hash('temporary-joint-password')))
        self.client=self.enterContext(TestClient(app,base_url=ORIGIN))
        response=self.client.post('/api/admin/login',headers=HEADERS,json={'username':'owner','password':'temporary-joint-password'})
        self.assertEqual(response.status_code,200,response.text)
        self.headers=HEADERS|{'X-CSRF-Token':response.json()['csrf_token']}

    def test_real_project_profile_and_file_publication_compose(self):
        upload=self.client.post('/api/admin/files',headers=self.headers,files={'file':('cover.png',picture(),'image/png')})
        self.assertEqual(upload.status_code,201,upload.text)
        fid=upload.json()['id'];url='/api/files/'+fid
        payload={'name':'真实项目','summary':'简介','category':'应用','tech_stack':['Vue'],'features':[],
          'cover_file_id':fid,'cover_alt':'封面','demo_url':'/trip/','source_url':None,
          'blocks':[{'kind':'text','body':'详情'}],'screenshots':[]}
        result=self.client.post('/api/admin/projects',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,200,result.text)
        pid=result.json()['project']['id'];base='/api/admin/projects/'+str(pid)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get('/api/projects').json(),{'projects':[]})
        self.assertEqual(self.client.post(base+'/publish',headers=self.headers,json={}).status_code,200)
        self.assertEqual(self.client.get(url).status_code,200)
        profile=self.client.get('/api/profile').json()
        self.assertEqual(profile['projects'],[{'name':'真实项目','description':'简介'}])
        self.assertEqual(self.client.put(base,headers=self.headers,json={**payload,'summary':''}).status_code,400)
        self.assertEqual(self.client.get('/api/projects/'+str(pid)).json()['project']['summary'],'简介')
        self.assertEqual(self.client.get(url).status_code,200)
        value={key:profile[key] for key in ('name','title','introduction','skills','avatar_file_id','contacts','social_links')}
        value['avatar_file_id']=fid
        self.assertEqual(self.client.put('/api/admin/profile',headers=self.headers,json=value).status_code,200)
        self.assertEqual(self.client.post(base+'/archive',headers=self.headers,json={}).status_code,200)
        self.assertEqual(self.client.get('/api/projects').json(),{'projects':[]})
        self.assertEqual(self.client.get('/api/projects/'+str(pid)).status_code,404)
        self.assertEqual(self.client.get(url).status_code,200) # shared current avatar remains public
        value['avatar_file_id']=None
        self.assertEqual(self.client.put('/api/admin/profile',headers=self.headers,json=value).status_code,200)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get('/api/admin/files/'+fid).status_code,200)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/admin/files/'+fid).status_code,401)
