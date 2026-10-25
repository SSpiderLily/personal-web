"""Integration entrypoints must retain the stage B authorization boundary."""
import unittest
from fastapi.testclient import TestClient
from app.main import app

class StageCRouteTests(unittest.TestCase):
    def test_new_admin_reads_are_protected_at_the_real_main_app(self):
        with TestClient(app) as client:
            for path in ('/api/admin/projects', '/api/admin/profile', '/api/admin/tools', '/api/admin/statistics', '/api/admin/files/e829699d-abf4-4aa4-b02e-b067b36123e4'):
                with self.subTest(path=path):
                    response=client.get(path)
                    self.assertEqual(response.status_code,401)
                    self.assertEqual(response.json()['error']['code'],'unauthenticated')
                    self.assertEqual(response.headers['cache-control'],'no-store')
    def test_new_writes_require_a_trusted_origin_before_reading_content(self):
        with TestClient(app) as client:
            for path in ('/api/admin/tools','/api/admin/files','/api/admin/visits'):
                with self.subTest(path=path):
                    response=client.request('PUT' if path.endswith('tools') else 'POST',path,content=b'not a request')
                    self.assertEqual(response.status_code,403)
                    self.assertEqual(response.json()['error']['code'],'origin_forbidden')

    def test_overview_reports_completed_business_modules_as_ready(self):
        from datetime import datetime,timezone,timedelta
        from app import admin_auth as auth
        app.dependency_overrides[auth.require_admin]=lambda:auth.AdminSession(1,'test-owner',datetime.now(timezone.utc)+timedelta(hours=1),'x'*43)
        try:
            with TestClient(app) as client:
                self.assertEqual({item['id']:item['status'] for item in client.get('/api/admin/overview').json()['modules']},
                                 {'projects':'ready','statistics':'ready','content':'ready','tools':'ready'})
        finally:app.dependency_overrides.clear()
