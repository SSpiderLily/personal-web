"""Real SQL only: the runner owns and destroys an isolated Unix-socket PG."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import database, migrate
from app.admin_routes import router as admin_router
from app.settings import get_settings
from app.statistics_routes import router as statistics_router

WRITE = {'Origin': 'http://127.0.0.1:5180', 'X-Admin-Request': '1'}


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'run isolated PostgreSQL statistics tests')
class StatisticsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute("INSERT INTO projects(id,name,status,sort_order) VALUES (1,'Published','published',2),(2,'Draft','draft',0),(3,'Archived','archived',1)")
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.include_router(statistics_router)
        self.app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = self.enterContext(TestClient(self.app, base_url='http://127.0.0.1:5180'))

    def post(self, payload=None, client=None):
        return (client or self.client).post('/api/admin/visits', headers=WRITE, json=payload or {'kind': 'website'})

    def login(self):
        from app.admin_auth import PASSWORDS
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)', ('owner', PASSWORDS.hash('test-password')))
        response = self.client.post('/api/admin/login', headers=WRITE, json={'username': 'owner', 'password': 'test-password'})
        self.assertEqual(response.status_code, 200, response.text)

    def counts(self):
        with database.connection() as conn:
            return (conn.execute('SELECT count(*) FROM site_daily_visitors').fetchone()[0],
                    conn.execute('SELECT count(*) FROM project_daily_visitors').fetchone()[0])

    def test_anonymous_collector_persists_first_visit(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'recorded': True})
        self.assertEqual(self.counts(), (1, 0))
        cookie = response.headers['set-cookie']
        for text in ('personal_web_visitor=', 'HttpOnly', 'SameSite=strict', 'Path=/api/admin/visits', 'Max-Age=31536000'):
            self.assertIn(text, cookie)
        self.assertNotIn('Domain=', cookie)
        self.assertNotIn('; Secure', cookie)

    def test_duplicate_and_cross_day_cookie_does_not_renew(self):
        with patch('app.visitors.today', return_value=date(2026, 10, 23)):
            self.assertEqual(self.post().json(), {'recorded': True})
            visitor = self.client.cookies.get('personal_web_visitor')
            duplicate = self.post()
            self.assertEqual(duplicate.json(), {'recorded': True})
            self.assertNotIn('set-cookie', duplicate.headers)
            self.assertEqual(self.counts(), (1, 0))
        with patch('app.visitors.today', return_value=date(2026, 10, 24)):
            response = self.post()
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.client.cookies.get('personal_web_visitor'), visitor)
        self.assertEqual(self.counts(), (2, 0))

    def test_project_only_published_and_independent_of_website(self):
        for project_id in (2, 3, 999):
            response = self.post({'kind': 'project', 'project_id': project_id})
            self.assertEqual(response.json(), {'recorded': False})
            self.assertNotIn('set-cookie', response.headers)
        response = self.post({'kind': 'project', 'project_id': 1})
        self.assertEqual(response.json(), {'recorded': True})
        self.assertEqual(self.counts(), (0, 1))
        self.assertEqual(self.post().json(), {'recorded': True})
        self.assertEqual(self.counts(), (1, 1))

    def test_invalid_cookie_replaced_only_when_recorded(self):
        self.client.cookies.set('personal_web_visitor', 'forged', path='/api/admin/visits')
        response = self.post()
        self.assertEqual(response.json(), {'recorded': True})
        self.assertIn('set-cookie', response.headers)
        self.assertNotIn('forged', response.headers['set-cookie'])

    def test_real_admin_session_skips_without_new_or_renewed_visitor_cookie(self):
        self.login()
        for existing in (False, True):
            if existing:
                self.client.cookies.set('personal_web_visitor', str(uuid4()), path='/api/admin/visits')
            for payload in ({'kind': 'website'}, {'kind': 'project', 'project_id': 1}):
                response = self.post(payload)
                self.assertEqual(response.json(), {'recorded': False})
                self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.counts(), (0, 0))
        with database.transaction() as conn:
            conn.execute('UPDATE admin_sessions SET revoked_at=now()')
        self.client.cookies.delete('personal_web_visitor', path='/api/admin/visits')
        response = self.post()
        self.assertEqual(response.json(), {'recorded': True})
        self.assertIn('set-cookie', response.headers)

    def test_expired_session_is_anonymous_and_statistic_read_rejected(self):
        self.login()
        with database.transaction() as conn:
            conn.execute("UPDATE admin_sessions SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour'")
        self.assertEqual(self.client.get('/api/admin/statistics?days=7').status_code, 401)
        self.assertEqual(self.post().json(), {'recorded': True})

    def test_simultaneous_repeated_visits_use_database_deduplication(self):
        visitor = str(uuid4())
        def collect(payload):
            with TestClient(self.app, base_url='http://127.0.0.1:5180') as client:
                client.cookies.set('personal_web_visitor', visitor, path='/api/admin/visits')
                return self.post(payload, client).json()
        for payload in ({'kind': 'website'}, {'kind': 'project', 'project_id': 1}):
            with ThreadPoolExecutor(max_workers=6) as executor:
                results = list(executor.map(collect, [payload] * 12))
            self.assertEqual(results, [{'recorded': True}] * 12)
        self.assertEqual(self.counts(), (1, 1))

    def test_interval_distinct_counts_includes_existing_unpublished_projects(self):
        first, second, outside = uuid4(), uuid4(), uuid4()
        with database.transaction() as conn:
            for day, visitor in [('2026-10-24', first), ('2026-10-23', first), ('2026-10-18', second), ('2026-10-17', outside), ('2026-10-25', outside)]:
                conn.execute('INSERT INTO site_daily_visitors VALUES (%s,%s)', (day, visitor))
                conn.execute('INSERT INTO project_daily_visitors VALUES (3,%s,%s)', (day, visitor))
        self.login()
        with patch('app.visitors.today', return_value=date(2026, 10, 24)):
            response = self.client.get('/api/admin/statistics?days=7')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {'days': 7, 'timezone': 'Asia/Shanghai', 'start_date': '2026-10-18', 'end_date': '2026-10-24',
                'website_visitors': 2, 'projects': [{'project_id': 2, 'name': 'Draft', 'visitors': 0}, {'project_id': 3, 'name': 'Archived', 'visitors': 2}, {'project_id': 1, 'name': 'Published', 'visitors': 0}]})
            self.assertEqual(self.client.get('/api/admin/statistics').json(), response.json())
            self.assertNotIn('set-cookie', response.headers)
            result = self.client.get('/api/admin/statistics?days=30').json()
            self.assertEqual(result['start_date'], '2026-09-25')
            self.assertEqual(result['website_visitors'], 3)
            for query in ('days=1', 'days=7.0', 'days=true', 'days=07', 'days=7&days=30', 'days=7&start_date=2025-01-01'):
                self.assertEqual(self.client.get('/api/admin/statistics?' + query).status_code, 400)

    def test_insert_failure_rolls_back_without_cookie_or_driver_details(self):
        with database.transaction() as conn:
            conn.execute("""CREATE FUNCTION fail_visits() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private-storage-failure'; END $$""")
            conn.execute('CREATE TRIGGER fail_visits BEFORE INSERT ON site_daily_visitors FOR EACH ROW EXECUTE FUNCTION fail_visits()')
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-storage', response.text)
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.counts(), (0, 0))

    def test_production_collector_cookie_secure_and_transport_guard(self):
        self.settings = self.settings.model_copy(update={'app_env': 'production', 'admin_allowed_origins': ('https://admin.example',)})
        with TestClient(self.app, base_url='https://admin.example') as client:
            response = client.post('/api/admin/visits', headers={'Origin': 'https://admin.example', 'X-Admin-Request': '1'}, json={'kind': 'website'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('; Secure', response.headers['set-cookie'])
        with TestClient(self.app, base_url='http://admin.example') as client:
            response = client.post('/api/admin/visits', headers={'Origin': 'https://admin.example', 'X-Admin-Request': '1'}, json={'kind': 'website'})
            self.assertEqual(response.status_code, 403)
