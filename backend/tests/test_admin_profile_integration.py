"""Atomic profile persistence and real session protection on disposable PG."""
from contextlib import contextmanager
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import database, migrate, admin_auth as auth
from app.settings import get_settings
from app.admin_routes import router as auth_router
from test_admin_profile import payload
from test_admin import WRITE


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'requires owned temporary PostgreSQL')
class ProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app import profile, profile_routes
        self.profile = profile
        self.settings = get_settings()
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)', ('owner',auth.PASSWORDS.hash('temporary-profile-password')))
        app=FastAPI()
        app.include_router(auth_router)
        app.include_router(profile_routes.router)
        app.dependency_overrides[get_settings]=lambda:self.settings
        self.client=self.enterContext(TestClient(app,base_url='http://127.0.0.1:5180'))

    def login(self):
        response=self.client.post('/api/admin/login',headers=WRITE,json={'username':'owner','password':'temporary-profile-password'})
        self.assertEqual(response.status_code,200,response.text)
        return WRITE | {'X-CSRF-Token':response.json()['csrf_token']}

    def test_empty_public_profile_has_no_invented_identity_and_legacy_projects(self):
        self.assertEqual(self.client.get('/api/profile').json(),payload() | {'projects':[]})
        self.assertEqual(self.client.get('/api/admin/profile').status_code,401)
        headers=self.login()
        value=payload() | {'name':'真实姓名','title':'开发者','introduction':'介绍\n第二行','skills':['Python'],'contacts':[{'label':'邮件','url':'mailto:owner@example.com'}]}
        response=self.client.put('/api/admin/profile',headers=headers,json=value)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json(),value | {'projects':[]})
        self.assertEqual(self.client.get('/api/profile').json(),response.json())
        self.assertEqual(self.client.get('/api/admin/profile').headers['cache-control'],'no-store')

    def test_real_csrf_origin_and_expiry_protect_write(self):
        headers=self.login()
        for invalid in [WRITE,headers | {'Origin':'https://evil.example'},headers | {'X-CSRF-Token':'bad'}]:
            self.assertEqual(self.client.put('/api/admin/profile',headers=invalid,json=payload()).status_code,403)
        with database.transaction() as conn: conn.execute('UPDATE admin_sessions SET revoked_at=now()')
        self.assertEqual(self.client.put('/api/admin/profile',headers=headers,json=payload()).status_code,401)
        self.assertEqual(self.profile.load_profile(self.settings),payload() | {'projects':[]})

    def test_avatar_reference_and_failed_commit_leave_previous_profile(self):
        original=payload() | {'name':'旧资料'}
        self.profile.save_profile(original,self.settings)
        bad=payload() | {'name':'新资料','avatar_file_id':str(uuid4())}
        with self.assertRaises(auth.AdminError): self.profile.save_profile(bad,self.settings)
        self.assertEqual(self.profile.load_profile(self.settings),original | {'projects':[]})
        identifier=str(uuid4())
        with database.transaction() as conn:
            conn.execute("INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height) VALUES (%s,%s,'avatar.png','image/png',1,1,1)",(identifier,identifier))
        updated=bad | {'avatar_file_id':identifier}
        self.assertEqual(self.profile.save_profile(updated,self.settings),updated | {'projects':[]})
        @contextmanager
        def fail(settings):
            with database.transaction(settings) as conn:
                yield conn
                raise RuntimeError('simulated commit failure')
        with patch.object(self.profile,'transaction',fail),self.assertRaises(RuntimeError):
            self.profile.save_profile(payload(),self.settings)
        self.assertEqual(self.profile.load_profile(self.settings),updated | {'projects':[]})

    def test_invalid_and_large_content_are_safe(self):
        headers=self.login()
        for value in [payload() | {'secret':'do-not-echo'},payload() | {'skills':['']},payload() | {'title':'x'*201}]:
            response=self.client.put('/api/admin/profile',headers=headers,json=value)
            self.assertEqual(response.status_code,400,response.text)
            self.assertNotIn('do-not-echo',response.text)
        value=payload() | {'introduction':'文'*10000}
        self.assertEqual(self.client.put('/api/admin/profile',headers=headers,json=value).status_code,200)


    def test_about_copy_round_trip_and_legacy_updates_preserve_saved_about(self):
        headers=self.login()
        about={'page_title':'关于我','about_body':'新的文案\n\n第二段','current_project_url':'/#/works'}
        response=self.client.put('/api/admin/profile',headers=headers,json=payload() | {'name':'rewind','about_content':about})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/profile').json()['about_content'],about)
        response=self.client.put('/api/admin/profile',headers=headers,json=payload() | {'name':'修改基本资料'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['about_content'],about)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT about_content FROM site_profile WHERE id=1').fetchone()[0],about)
