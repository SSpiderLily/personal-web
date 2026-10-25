"""Actual session/CSRF/visitor persistence for the temporary SSH mode; owned DB only."""
import os
import unittest
from fastapi.testclient import TestClient
from app import admin_auth as auth, database, migrate
from app.main import app
from app.settings import get_settings


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1','owned isolated runner only')
class HttpSshDatabaseTests(unittest.TestCase):
    def setUp(self):
        isolated=get_settings()
        database.validate_test_target(isolated)
        with database.transaction(isolated) as conn:
            conn.execute('DROP SCHEMA public CASCADE');conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        self.settings=isolated.model_copy(update={'app_env':'production','production_mode':'http_ssh',
            'public_origin':'http://124.223.69.7','admin_allowed_origins':('http://127.0.0.1:18880',)})
        with database.transaction(isolated) as conn:
            conn.execute('INSERT INTO admin_accounts(id,username,password_hash) VALUES(1,%s,%s)',
                         ('owner',auth.PASSWORDS.hash('synthetic-test-password-123')))
        app.dependency_overrides[get_settings]=lambda:self.settings
        self.addCleanup(app.dependency_overrides.clear)
        self.private=self.enterContext(TestClient(app,base_url='http://127.0.0.1:18880',client=('127.0.0.1',40000)))
        self.public=self.enterContext(TestClient(app,base_url='http://124.223.69.7',client=('203.0.113.7',40000)))

    def test_real_private_login_session_csrf_update_and_revocation(self):
        headers={'Origin':'http://127.0.0.1:18880','X-Admin-Request':'1'}
        result=self.private.post('/api/admin/login',headers=headers,json={'username':'owner','password':'synthetic-test-password-123'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertNotIn('Secure',result.headers['set-cookie'])
        self.assertTrue(self.private.get('/api/admin/session').json()['authenticated'])
        tools=self.private.get('/api/admin/tools').json()
        self.assertEqual(self.private.put('/api/admin/tools',headers=headers,json=tools).status_code,403)
        self.assertEqual(self.private.put('/api/admin/tools',headers=headers|{'X-CSRF-Token':result.json()['csrf_token']},json=tools).status_code,200)
        for path in ['session','tools','statistics','projects','profile']:
            self.assertEqual(self.public.get('/api/admin/'+path).status_code,403)
        self.assertEqual(self.private.post('/api/admin/logout',headers=headers|{'X-CSRF-Token':result.json()['csrf_token']},json={}).status_code,200)
        self.assertFalse(self.private.get('/api/admin/session').json()['authenticated'])

    def test_public_visitor_cookie_dedup_and_private_admin_exclusion(self):
        headers={'Origin':'http://124.223.69.7','X-Admin-Request':'1'}
        for _ in range(2):
            result=self.public.post('/api/admin/visits',headers=headers,json={'kind':'website'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json(),{'recorded':True})
        private={'Origin':'http://127.0.0.1:18880','X-Admin-Request':'1'}
        self.assertEqual(self.private.post('/api/admin/login',headers=private,json={'username':'owner','password':'synthetic-test-password-123'}).status_code,200)
        self.assertEqual(self.private.post('/api/admin/visits',headers=private,json={'kind':'website'}).json(),{'recorded':False})
        with database.connection(self.settings) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM site_daily_visitors').fetchone()[0],1)
