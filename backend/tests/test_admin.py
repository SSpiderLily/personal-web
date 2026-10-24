"""Admin HTTP boundaries without a database; no network or credentials."""
import unittest
from unittest.mock import patch
import json
from fastapi.testclient import TestClient
from app.main import app
from app.settings import Settings, get_settings

ORIGIN = 'http://127.0.0.1:5180'
WRITE = {'Origin': ORIGIN, 'X-Admin-Request': '1'}
ANONYMOUS = {'authenticated': False, 'admin': None, 'csrf_token': None, 'expires_at': None}

class AdminBoundaryTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='test')
        self.addCleanup(app.dependency_overrides.clear)
        self.client = self.enterContext(TestClient(app))

    def error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['error']['code'], code)
        self.assertEqual(response.headers.get('cache-control'), 'no-store')
        self.assertNotIn('Traceback', response.text)

    def test_anonymous_session_works_without_database(self):
        response = self.client.get('/api/admin/session')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ANONYMOUS)
        self.assertEqual(response.headers.get('cache-control'), 'no-store')

    def test_overview_requires_real_authentication(self):
        self.error(self.client.get('/api/admin/overview'), 401, 'unauthenticated')

    def test_write_requires_exact_origin_and_request_header(self):
        for headers in ({}, {'Origin': ORIGIN}, WRITE | {'Origin': 'https://evil.example'}, WRITE | {'Origin': 'null'}, WRITE | {'Origin': ORIGIN + '/'}):
            with self.subTest(headers=headers):
                self.error(self.client.post('/api/admin/login', headers=headers, json={'username': 'owner', 'password': 'secret'}), 403, 'origin_forbidden')

    def test_bad_bodies_never_echo_secret(self):
        secret = 'private-password-must-not-echo'
        bodies = [({'username': 'owner', 'password': [secret]}, None), ({'username': 'owner', 'password': secret * 500}, None),
                  ({'username': '', 'password': secret}, None), ({'username': 'owner', 'password': secret, 'extra': secret}, None),
                  (None, '{"password":"' + secret), (None, secret)]
        for body, raw in bodies:
            with self.subTest(raw=bool(raw)):
                response = self.client.post('/api/admin/login', headers=WRITE | {'Content-Type': 'application/json'}, json=body, content=raw)
                self.error(response, 400, 'invalid_request')
                self.assertNotIn(secret, response.text)
        self.error(self.client.post('/api/admin/login', headers=WRITE, content=secret), 400, 'invalid_request')

    def test_database_unavailable_is_safe_even_debug(self):
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='test', debug=True, db_port=25431, db_name='personal_web_test_unavailable', db_user='personal_web_test')
        response = self.client.post('/api/admin/login', headers=WRITE, json={'username': 'owner', 'password': 'test-only-password'})
        self.error(response, 503, 'admin_unavailable')
        self.assertNotIn('test-only-password', response.text)

    def production(self, origins=()):
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='production', db_host='127.0.0.1', db_port=5432, db_name='personal_web_prod', db_user='personal_web_prod', db_password='test-only', admin_allowed_origins=origins)

    def test_production_admin_fails_closed_without_origin_config(self):
        self.production()
        self.error(self.client.get('/api/admin/session'), 503, 'admin_unavailable')
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok'})

    def test_production_rejects_http_and_forged_forwarded_headers(self):
        self.production(('https://admin.example',))
        self.error(self.client.get('/api/admin/session', headers={'Host': 'admin.example', 'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'admin.example'}), 403, 'origin_forbidden')
        with TestClient(app, base_url='https://admin.example') as client:
            self.assertEqual(client.get('/api/admin/session').json(), ANONYMOUS)
        with TestClient(app, base_url='https://evil.example') as client:
            self.error(client.get('/api/admin/session'), 403, 'origin_forbidden')

    def test_origin_configuration_rejects_wildcards_paths_and_production_http(self):
        from pydantic import ValidationError
        for origin in ('*', 'https://admin.example/path', 'https://admin.example/', 'null', 'https://user:pass@admin.example', 'http://admin.example'):
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                Settings(app_env='production', db_host='localhost', db_port=5432, db_name='prod', db_user='prod', db_password='test-only', admin_allowed_origins=(origin,))

    def test_invalid_unicode_and_nul_inputs_are_safe(self):
        for body in ({'username': 'owner\x00', 'password': 'test-only-password'},
                     {'username': '\ud800', 'password': 'test-only-password'},
                     {'username': 'owner', 'password': '\ud800'}):
            with self.subTest(field=next(k for k,v in body.items() if '\x00' in v or '\ud800' in v)):
                self.error(self.client.post('/api/admin/login', headers=WRITE | {'Content-Type': 'application/json'}, content=json.dumps(body)), 400, 'invalid_request')

    def test_bootstrap_rejects_unloginable_characters_before_hash_or_write(self):
        from app import admin_init
        settings = Settings(app_env='test')
        for case, username, password in (('NUL username', 'owner\x00', 'disposable-test-password'),
                                         ('NUL password', 'owner', 'disposable\x00-test-password'),
                                         ('surrogate username', 'owner\ud800', 'disposable-test-password'),
                                         ('surrogate password', 'owner', 'disposable\ud800-test-password')):
            with self.subTest(case=case), \
                    patch.object(admin_init.PASSWORDS, 'hash') as hash_password, \
                    patch('app.admin_init.transaction') as transaction:
                with self.assertRaises(admin_init.AdminInitializationError) as error:
                    admin_init.initialize_admin(settings, username, password)
                self.assertNotIn(username, str(error.exception))
                self.assertNotIn(password, str(error.exception))
                hash_password.assert_not_called()
                transaction.assert_not_called()

    def test_database_outage_session_and_logout_do_not_appear_anonymous(self):
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='test', debug=True, db_port=25431, db_name='personal_web_test_unavailable', db_user='personal_web_test')
        self.client.cookies.set('personal_web_session', 'A' * 43)
        self.error(self.client.get('/api/admin/session'), 503, 'admin_unavailable')
        self.error(self.client.get('/api/admin/overview'), 503, 'admin_unavailable')
        self.error(self.client.post('/api/admin/logout', headers=WRITE | {'X-CSRF-Token': 'x'}, json={}), 503, 'admin_unavailable')
        self.assertIsNone(self.client.post('/api/admin/logout', headers=WRITE, json={}).headers.get('set-cookie'))
