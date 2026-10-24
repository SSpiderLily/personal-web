"""Runs only on the owned disposable PostgreSQL cluster."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from app import database, migrate
from app.main import app
from app.settings import Settings, get_settings
from test_admin import ANONYMOUS, WRITE

PASSWORD = 'disposable-test-password'

@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'run bash scripts/test-db.sh for isolated PostgreSQL tests')
class AdminIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.addCleanup(app.dependency_overrides.clear)
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)', ('owner', PasswordHash.recommended().hash(PASSWORD)))
        self.client = self.enterContext(TestClient(app, base_url='http://127.0.0.1:5180'))

    def login(self, client=None, username='owner', password=PASSWORD, csrf=None):
        headers = WRITE | ({'X-CSRF-Token': csrf} if csrf else {})
        return (client or self.client).post('/api/admin/login', headers=headers, json={'username': username, 'password': password})

    def authenticated(self, csrf=None):
        response = self.login(csrf=csrf)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body['authenticated'])
        self.assertEqual(body['admin'], {'id': 1, 'username': 'owner'})
        self.assertTrue(body['csrf_token'])
        self.assertGreater(datetime.fromisoformat(body['expires_at']), datetime.now(timezone.utc) + timedelta(hours=7, minutes=59))
        return response

    def test_login_cookie_hash_persistence_and_overview(self):
        response = self.authenticated()
        token = self.client.cookies.get('personal_web_session')
        cookie = response.headers['set-cookie']
        for part in ('HttpOnly', 'Path=/api/admin', 'SameSite=strict'):
            self.assertIn(part, cookie)
        self.assertNotIn('Domain=', cookie)
        with database.connection() as conn:
            row = conn.execute('SELECT token_hash, expires_at FROM admin_sessions').fetchone()
        self.assertEqual(bytes(row[0]), hashlib.sha256(token.encode()).digest())
        self.assertNotIn(token, str(row))
        # A separate app instance has no process/session memory to inherit.
        from fastapi import FastAPI
        from app.admin_routes import router
        other_app = FastAPI()
        other_app.include_router(router)
        other_app.dependency_overrides[get_settings] = lambda: self.settings
        with TestClient(other_app, base_url='http://127.0.0.1:5180') as other:
            other.cookies.set('personal_web_session', token)
            self.assertEqual(other.get('/api/admin/session').json(), response.json())
            overview = other.get('/api/admin/overview').json()
            self.assertEqual(overview['admin'], {'id': 1, 'username': 'owner'})
            self.assertEqual([m['id'] for m in overview['modules']], ['projects', 'statistics', 'content', 'tools'])
            self.assertEqual({m['id']:m['status'] for m in overview['modules']},
                             {'projects':'ready','statistics':'pending','content':'ready','tools':'ready'})

    def test_wrong_username_and_password_have_same_generic_error(self):
        errors = [self.login(username='missing').json(), self.login(password='wrong').json()]
        self.assertEqual(errors[0], errors[1])
        self.assertEqual(errors[0]['error']['code'], 'invalid_credentials')
        self.assertEqual(self.login(password='wrong').status_code, 401)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM admin_sessions').fetchone(), (0,))

    def test_rotation_logout_and_csrf_reject_old_tokens(self):
        initial = self.authenticated()
        old = self.client.cookies.get('personal_web_session')
        for csrf in (None, 'wrong'):
            rejected = self.login(csrf=csrf)
            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(rejected.json()['error']['code'], 'csrf_failed')
        rotated = self.authenticated(initial.json()['csrf_token'])
        self.assertNotEqual(old, self.client.cookies.get('personal_web_session'))
        with TestClient(app) as other:
            other.cookies.set('personal_web_session', old)
            self.assertEqual(other.get('/api/admin/session').json(), ANONYMOUS)
        for headers in (WRITE, WRITE | {'X-CSRF-Token': initial.json()['csrf_token']}, WRITE | {'X-CSRF-Token': 'wrong'}):
            response = self.client.post('/api/admin/logout', headers=headers, json={})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['error']['code'], 'csrf_failed')
        current = self.client.cookies.get('personal_web_session')
        response = self.client.post('/api/admin/logout', headers=WRITE | {'X-CSRF-Token': rotated.json()['csrf_token']}, json={})
        self.assertEqual(response.json(), ANONYMOUS)
        self.assertIn('Max-Age=0', response.headers['set-cookie'])
        with TestClient(app) as other:
            other.cookies.set('personal_web_session', current)
            self.assertEqual(other.get('/api/admin/overview').status_code, 401)

    def test_expired_revoked_missing_and_malformed_cookies(self):
        for state in ('expired', 'revoked'):
            self.authenticated()
            with database.transaction() as conn:
                if state == 'expired':
                    conn.execute("UPDATE admin_sessions SET created_at=now()-interval '2 hours', expires_at=now()-interval '1 hour'")
                else:
                    conn.execute('UPDATE admin_sessions SET revoked_at=now()')
            self.assertEqual(self.client.get('/api/admin/session').json(), ANONYMOUS)
            self.assertEqual(self.client.get('/api/admin/overview').status_code, 401)
        self.client.cookies.clear()
        for token in ('', 'forged', 'x' * 10000):
            self.client.cookies.set('personal_web_session', token)
            self.assertEqual(self.client.get('/api/admin/session').json(), ANONYMOUS)
            self.assertEqual(self.client.get('/api/admin/overview').status_code, 401)

    def test_cross_origin_and_non_json_logout_cannot_revoke(self):
        response = self.authenticated()
        headers = WRITE | {'X-CSRF-Token': response.json()['csrf_token']}
        for invalid in (headers | {'Origin': 'https://evil.example'}, headers | {'X-Admin-Request': '0'}):
            self.assertEqual(self.client.post('/api/admin/logout', headers=invalid, json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/admin/logout', headers=headers, content='').status_code, 400)
        self.assertTrue(self.client.get('/api/admin/session').json()['authenticated'])

    def test_production_secure_cookie_and_https_origin(self):
        self.settings = self.settings.model_copy(update={'app_env': 'production', 'admin_allowed_origins': ('https://admin.example',)})
        with TestClient(app, base_url='https://admin.example') as client:
            response = client.post('/api/admin/login', headers={'Origin': 'https://admin.example', 'X-Admin-Request': '1'}, json={'username': 'owner', 'password': PASSWORD})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('; Secure', response.headers['set-cookie'])
            self.assertTrue(client.get('/api/admin/session').json()['authenticated'])

    def test_bootstrap_duplicate_and_concurrent_never_overwrites(self):
        from app import admin_init
        with database.transaction() as conn:
            conn.execute('DELETE FROM admin_accounts')
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(admin_init.initialize_admin, self.settings, 'owner' + str(i), PASSWORD) for i in range(2)]
            results = []
            for future in futures:
                try:
                    future.result(timeout=10)
                    results.append('created')
                except admin_init.AdminAlreadyExists:
                    results.append('exists')
        self.assertCountEqual(results, ['created', 'exists'])
        with database.connection() as conn:
            original = conn.execute('SELECT username,password_hash FROM admin_accounts').fetchall()
        with self.assertRaises(admin_init.AdminAlreadyExists):
            admin_init.initialize_admin(self.settings, 'replacement', PASSWORD)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT username,password_hash FROM admin_accounts').fetchall(), original)
        self.assertTrue(PasswordHash.recommended().verify(PASSWORD, original[0][1]))

    def test_bootstrap_cli_initializes_from_real_tty_without_echo(self):
        with database.transaction() as conn:
            conn.execute('DELETE FROM admin_accounts')
        result = subprocess.run([sys.executable, 'tests/admin_tty_probe.py'], input=PASSWORD,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        with database.connection() as conn:
            row = conn.execute('SELECT username,password_hash FROM admin_accounts').fetchone()
        self.assertEqual(row[0], 'tty-owner')
        self.assertTrue(PasswordHash.recommended().verify(PASSWORD, row[1]))
        self.assertEqual(self.login(username='tty-owner').status_code, 200)

    def test_bootstrap_cli_rejects_piped_password_without_write(self):
        result = subprocess.run([sys.executable, '-m', 'app.admin_init'], input='owner\n' + PASSWORD + '\n' + PASSWORD + '\n', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(PASSWORD, result.stdout + result.stderr)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT username FROM admin_accounts').fetchall(), [('owner',)])
