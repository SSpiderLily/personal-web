"""Public image HTTP boundaries independent of database availability."""
import importlib.util
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.settings import Settings, get_settings


class PublicFileBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.public_file_routes'), 'public file routes are not implemented')
        from app import public_file_routes
        self.routes = public_file_routes
        app = FastAPI()
        app.include_router(public_file_routes.router)
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='test')
        self.client = self.enterContext(TestClient(app))

    def test_invalid_uuid_is_hidden_even_when_database_and_storage_unavailable(self):
        with patch.object(self.routes, 'transaction', side_effect=AssertionError('invalid UUID opened database')):
            for identifier in ('not-a-uuid', 'null', '0'):
                response = self.client.get('/api/files/' + identifier)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json()['error']['code'], 'file_not_found')
                self.assertEqual(response.headers['cache-control'], 'no-store')
