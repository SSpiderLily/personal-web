"""Temporary HTTP origin and SSH administrator boundaries; no production access."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import admin_auth as auth, production_admin_init
from app.main import app
from app.settings import Settings, get_settings

PUBLIC = 'http://124.223.69.7'
PRIVATE = 'http://127.0.0.1:18880'

def settings(**overrides):
    return Settings(_env_file=None, app_env='production', db_host='127.0.0.1', db_port=5432,
                    db_name='personal_web_prod', db_user='personal_web_prod', db_password='test-only',
                    **({'production_mode': 'http_ssh', 'public_origin': PUBLIC,
                        'admin_allowed_origins': (PRIVATE,)} | overrides))

class HttpSshSettingsTests(unittest.TestCase):
    def test_explicit_mode_and_initializer_accept_public_ip_and_private_loopback(self):
        self.assertIn('production_mode', Settings.model_fields)
        configured = settings()
        self.assertEqual(configured.public_origin, PUBLIC)
        production_admin_init._origins(configured)

    def test_reject_untrusted_public_origins(self):
        for public in (None, '', 'https://124.223.69.7', 'http://example.com', 'http://127.0.0.1',
                       'http://192.168.1.1', 'http://10.1.2.3', 'http://0.0.0.0', 'http://224.0.0.1',
                       'http://user:pass@124.223.69.7', PUBLIC + '/', PUBLIC + ':80',
                       PUBLIC + '?q=1', PUBLIC + '#f'):
            with self.subTest(public=public), self.assertRaises(ValidationError):
                settings(public_origin=public)

    def test_reject_untrusted_admin_origins(self):
        for origin in ('http://localhost:18880', 'http://127.0.0.2:18880', 'http://[::1]:18880',
                       'http://127.0.0.1', 'http://127.0.0.1:80', 'http://127.0.0.1:443',
                       'http://127.0.0.1:0', 'https://127.0.0.1:18880', PUBLIC,
                       'http://192.168.1.1:18880', PRIVATE + '/', PRIVATE + '?x=1',
                       'http://u@127.0.0.1:18880', '*'):
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                settings(admin_allowed_origins=(origin,))
        for origins in ((), (PRIVATE, 'https://admin.example')):
            with self.assertRaises(ValidationError):
                settings(admin_allowed_origins=origins)

    def test_initializer_revalidates_copied_settings(self):
        configured = settings()
        for update in ({'admin_allowed_origins': ()}, {'admin_allowed_origins': (PUBLIC,)},
                       {'public_origin': 'http://127.0.0.1'}, {'production_mode': 'https'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                production_admin_init._origins(configured.model_copy(update=update))

class HttpSshRequestTests(unittest.TestCase):
    def setUp(self):
        self.configured = settings()
        app.dependency_overrides[get_settings] = lambda: self.configured
        self.addCleanup(app.dependency_overrides.clear)
        self.client = self.enterContext(TestClient(app, base_url=PRIVATE, client=('127.0.0.1', 40000)))
        self.public = self.enterContext(TestClient(app, base_url=PUBLIC, client=('203.0.113.10', 40000)))
        self.write = {'Origin': PRIVATE, 'X-Admin-Request': '1'}

    def test_private_admin_reads_require_session_and_public_reads_are_forbidden(self):
        self.assertEqual(self.client.get('/api/admin/session').status_code, 200)
        for route in ('overview', 'statistics', 'projects', 'profile', 'tools'):
            with self.subTest(route=route):
                self.assertEqual(self.client.get('/api/admin/' + route).status_code, 401)
                self.assertEqual(self.public.get('/api/admin/' + route).status_code, 403)
        self.assertEqual(self.public.get('/api/admin/session').status_code, 403)

    def test_reject_external_peer_wrong_host_scheme_and_forged_forwarding(self):
        for peer in ('203.0.113.10', '192.168.1.3', 'testclient'):
            with TestClient(app, base_url=PRIVATE, client=(peer, 40000)) as client:
                self.assertEqual(client.get('/api/admin/session', headers={
                    'X-Forwarded-For': '127.0.0.1', 'Forwarded': 'for=127.0.0.1;proto=http',
                    'X-Forwarded-Host': '127.0.0.1:18880'}).status_code, 403)
        for host in ('124.223.69.7', '127.0.0.1:18881', 'localhost:18880', 'evil.example'):
            self.assertEqual(self.client.get('/api/admin/session', headers={
                'Host': host, 'X-Forwarded-Host': '127.0.0.1:18880'}).status_code, 403)
        with TestClient(app, base_url='https://127.0.0.1:18880', client=('127.0.0.1', 40000)) as client:
            self.assertEqual(client.get('/api/admin/session', headers={'X-Forwarded-Proto': 'http'}).status_code, 403)
        for origin in (PUBLIC, PRIVATE + '/', 'http://localhost:18880'):
            self.assertEqual(self.client.get('/api/admin/session', headers={'Origin': origin}).status_code, 403)

    def test_login_logout_cookie_preserves_attributes_except_secure_and_csrf(self):
        current = auth.AdminSession(1, 'owner', datetime(2030, 1, 1, tzinfo=timezone.utc), 'A' * 43)
        with patch('app.admin_auth.authenticate', return_value=current):
            response = self.client.post('/api/admin/login', headers=self.write, json={'username': 'owner', 'password': 'test-password'})
        self.assertEqual(response.status_code, 200, response.text)
        for flag in ('HttpOnly', 'SameSite=strict', 'Path=/api/admin'):
            self.assertIn(flag, response.headers['set-cookie'])
        self.assertNotIn('Secure', response.headers['set-cookie'])
        with patch('app.admin_auth.current_session', return_value=current), patch('app.admin_auth.revoke_session'):
            self.assertEqual(self.client.post('/api/admin/logout', headers=self.write, json={}).status_code, 403)
            response = self.client.post('/api/admin/logout', headers=self.write | {'X-CSRF-Token': current.csrf_token}, json={})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Secure', response.headers['set-cookie'])
        self.assertIn('Max-Age=0', response.headers['set-cookie'])

    def test_public_collector_origin_marker_json_and_cookie(self):
        headers = {'Origin': PUBLIC, 'X-Admin-Request': '1'}
        with patch('app.visitors.record_visit', return_value=True):
            response = self.public.post('/api/admin/visits', headers=headers, json={'kind': 'website'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['recorded'])
        for flag in ('HttpOnly', 'SameSite=strict', 'Path=/api/admin/visits'):
            self.assertIn(flag, response.headers['set-cookie'])
        self.assertNotIn('Secure', response.headers['set-cookie'])
        for bad in ({}, {'Origin': PUBLIC}, headers | {'Origin': PRIVATE}, headers | {'Origin': PUBLIC + '/'},
                    headers | {'Host': 'evil.example'}, headers | {'Host': '127.0.0.1:18880'},
                    headers | {'Content-Type': 'text/plain'}):
            expected = 400 if bad.get('Content-Type') == 'text/plain' else 403
            self.assertEqual(self.public.post('/api/admin/visits', headers=bad, content='{"kind":"website"}').status_code, expected)

    def test_private_collector_excludes_admin_but_requires_loopback_peer(self):
        current = auth.AdminSession(1, 'owner', datetime(2030, 1, 1, tzinfo=timezone.utc), 'A' * 43)
        with patch('app.admin_auth.current_session', return_value=current):
            response = self.client.post('/api/admin/visits', headers=self.write, json={'kind': 'website'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'recorded': False})
            with TestClient(app, base_url=PRIVATE, client=('203.0.113.10', 40000)) as client:
                response = client.post('/api/admin/visits', headers=self.write | {'X-Forwarded-For': '127.0.0.1'}, json={'kind': 'website'})
                self.assertEqual(response.status_code, 403)
