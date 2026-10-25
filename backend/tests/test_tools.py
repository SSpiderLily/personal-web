"""Tool validation and HTTP boundaries; no database access."""
import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import admin_auth as auth
from app.settings import Settings, get_settings


def payload():
    return {'tools': [dict(tool_key=f'grid_{i+1:02}', placement='grid', is_visible=True, sort_order=i) for i in range(9)] +
            [dict(tool_key='dice', placement='floating', is_visible=True, sort_order=0)]}


class ToolContractTests(unittest.TestCase):
    def test_canonical_sort_and_strict_complete_validation(self):
        from app.tool_settings import validate_tools
        expected = payload()['tools']
        self.assertEqual(validate_tools({'tools': list(reversed(expected))}), expected)
        invalid = []
        value = payload(); value['tools'].pop(); invalid.append(value)
        value = payload(); value['tools'][0]['tool_key'] = 'secret-unknown'; invalid.append(value)
        value = payload(); value['tools'][0] = copy.deepcopy(value['tools'][1]); invalid.append(value)
        for field, bad in [('placement', 'floating'), ('is_visible', 1), ('is_visible', 'false'),
                           ('sort_order', True), ('sort_order', 1.0), ('sort_order', -1), ('sort_order', 9), ('sort_order', 1)]:
            value = payload(); value['tools'][0][field] = bad; invalid.append(value)
        value = payload(); value['tools'][-1]['sort_order'] = 1; invalid.append(value)
        value = payload(); value['tools'][0]['extra'] = 'secret'; invalid.append(value)
        invalid.extend([{}, {'tools': {}}, {'tools': [], 'extra': 1}, None])
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(auth.AdminError) as raised:
                validate_tools(value)
            self.assertEqual((raised.exception.status, raised.exception.code), (400, 'invalid_request'))

    def test_public_read_and_protected_admin_routes_use_safe_errors(self):
        from app.tool_routes import router
        from app import tool_settings
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_settings] = lambda: Settings(app_env='test')
        with TestClient(app) as client:
            with patch.object(tool_settings, 'load_tools', return_value=payload()['tools']):
                response = client.get('/api/tools')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), payload())
                self.assertEqual(client.get('/api/admin/tools').status_code, 401)
            current = auth.AdminSession(1, 'owner', datetime.now(timezone.utc), 'a' * 43)
            app.dependency_overrides[auth.require_admin_write] = lambda: current
            with patch.object(tool_settings, 'save_tools', side_effect=auth.invalid_request()):
                response = client.put('/api/admin/tools', json={'secret': 'must-not-echo'})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertNotIn('must-not-echo', response.text)
            with patch.object(tool_settings, 'load_tools', side_effect=auth.unavailable()):
                response = client.get('/api/tools')
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['error']['code'], 'admin_unavailable')
