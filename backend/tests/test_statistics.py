"""Statistics contract on a dedicated app; never installs public event hooks."""
from datetime import date, datetime, timezone
import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.settings import Settings, get_settings


class StatisticsModuleTests(unittest.TestCase):
    def test_server_day_uses_shanghai_across_utc_midnight(self):
        from app import visitors
        with patch('app.visitors.datetime') as clock:
            clock.now.side_effect = lambda zone: datetime(2026, 10, 23, 16, 1, tzinfo=timezone.utc).astimezone(zone)
            self.assertEqual(visitors.today(), date(2026, 10, 24))

    def test_uuid_cookie_reused_and_invalid_value_replaced(self):
        from app.visitors import resolve_visitor
        value = '17a20cdd-29f9-4468-9902-50e7da292a92'
        self.assertEqual(resolve_visitor(value), (UUID(value), False))
        for invalid in (None, '', 'forged', '17a20cdd29f94468990250e7da292a92'):
            visitor, fresh = resolve_visitor(invalid)
            self.assertTrue(fresh)
            self.assertEqual(visitor.version, 4)

    def test_inclusive_server_window_rejects_non_contract_days(self):
        from app import statistics
        with patch('app.visitors.today', return_value=date(2026, 1, 2)):
            self.assertEqual(statistics.date_window(7), (date(2025, 12, 27), date(2026, 1, 2)))
            self.assertEqual(statistics.date_window(30), (date(2025, 12, 4), date(2026, 1, 2)))
        for days in (True, 7.0, '7', 0, 6, 31):
            with self.assertRaises(ValueError):
                statistics.date_window(days)


class StatisticsGuardTests(unittest.TestCase):
    def setUp(self):
        from app.statistics_routes import router
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_settings] = lambda: Settings(app_env='test')
        self.client = self.enterContext(TestClient(self.app, base_url='http://127.0.0.1:5180'))
        self.write = {'Origin': 'http://127.0.0.1:5180', 'X-Admin-Request': '1'}

    def test_anonymous_statistics_read_requires_authentication(self):
        response = self.client.get('/api/admin/statistics?days=7')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'unauthenticated')
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_collector_requires_exact_origin_marker_and_json(self):
        for headers, status in (({}, 403), (self.write | {'Origin': 'http://127.0.0.1:5180.evil'}, 403),
                                ({'Origin': self.write['Origin']}, 403),
                                (self.write | {'Content-Type': 'text/plain'}, 400)):
            response = self.client.post('/api/admin/visits', headers=headers, content='{"kind":"website"}')
            self.assertEqual(response.status_code, status, response.text)
            self.assertNotIn('set-cookie', response.headers)

    def test_collector_rejects_extra_fields_and_invalid_ids_without_database(self):
        bodies = ({}, {'kind': 'unknown'}, {'kind': 'website', 'project_id': 1},
                  {'kind': 'website', 'admin': False}, {'kind': 'website', 'preview': False},
                  {'kind': 'website', 'time': '2025-01-01'}, {'kind': 'website', 'visitor_id': 'fake'},
                  {'kind': 'project'}, *({'kind': 'project', 'project_id': value} for value in
                    (True, 0, -1, '1', 1.0, 2**63)))
        for body in bodies:
            with self.subTest(body=body):
                response = self.client.post('/api/admin/visits', headers=self.write, json=body)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertNotIn('set-cookie', response.headers)
        for content in ('null', '[]', '{', '{"kind":"website","padding":"' + 'x' * 5000 + '"}'):
            response = self.client.post('/api/admin/visits', headers=self.write | {'Content-Type': 'application/json'}, content=content)
            self.assertEqual(response.status_code, 400)

    def test_database_failure_returns_safe_error_without_cookie(self):
        from app.database import DatabaseUnavailable
        with patch('app.visitors.record_visit', side_effect=DatabaseUnavailable('secret driver diagnostic')):
            response = self.client.post('/api/admin/visits', headers=self.write, json={'kind': 'website'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.text)
        self.assertNotIn('set-cookie', response.headers)
