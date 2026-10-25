"""Tools against a disposable PostgreSQL cluster only."""
from concurrent.futures import ThreadPoolExecutor
import copy
import os
import unittest
import time
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import database, migrate
from app.admin_routes import router as auth_router
from app.admin_auth import AdminError
from test_tools import payload


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'run isolated PostgreSQL tools tests')
class ToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app import tool_settings
        from app.tool_routes import router
        self.tools = tool_settings
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE'); conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        self.app = FastAPI(); self.app.include_router(auth_router); self.app.include_router(router)
        self.client = self.enterContext(TestClient(self.app, base_url='http://127.0.0.1:5180'))

    def test_migration_defaults_are_idempotent_and_preserve_existing_settings(self):
        self.assertEqual(self.tools.load_tools(), payload()['tools'])
        sql = (migrate.MIGRATIONS / '002_tool_defaults.sql').read_text()
        with database.transaction() as conn:
            conn.execute("UPDATE tool_settings SET is_visible=false, sort_order=8 WHERE tool_key='grid_01'")
            conn.execute("DELETE FROM tool_settings WHERE tool_key='grid_02'")
            conn.execute(sql); conn.execute(sql)
            self.assertEqual(conn.execute("SELECT is_visible,sort_order FROM tool_settings WHERE tool_key='grid_01'").fetchone(), (False, 8))
            self.assertEqual(conn.execute('SELECT count(*) FROM tool_settings').fetchone(), (10,))

    def test_save_round_trip_invalid_input_and_trigger_failure_rollback(self):
        changed = payload(); changed['tools'][0]['is_visible'] = False
        changed['tools'][0]['sort_order'], changed['tools'][8]['sort_order'] = 8, 0
        expected = [changed['tools'][8], *changed['tools'][1:8], changed['tools'][0], changed['tools'][9]]
        self.assertEqual(self.tools.save_tools(changed), expected)
        bad = copy.deepcopy(changed); bad['tools'].pop()
        with self.assertRaises(AdminError): self.tools.save_tools(bad)
        self.assertEqual(self.tools.load_tools(), expected)
        with database.transaction() as conn:
            conn.execute("""CREATE FUNCTION reject_dice() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
              IF NEW.tool_key='dice' THEN RAISE EXCEPTION 'private-driver-detail'; END IF; RETURN NEW; END $$""")
            conn.execute('CREATE TRIGGER fail_save BEFORE UPDATE ON tool_settings FOR EACH ROW EXECUTE FUNCTION reject_dice()')
        with self.assertRaises(psycopg.errors.RaiseException): self.tools.save_tools(payload())
        self.assertEqual(self.tools.load_tools(), expected)

    def test_missing_unknown_or_invalid_stored_rows_fail_closed(self):
        for sql in ["DELETE FROM tool_settings WHERE tool_key='dice'", "UPDATE tool_settings SET placement='floating' WHERE tool_key='grid_01'", "UPDATE tool_settings SET sort_order=1 WHERE tool_key='grid_01'", "INSERT INTO tool_settings(tool_key,placement) VALUES ('unknown','grid')"]:
            with self.subTest(sql=sql):
                with database.transaction() as conn:
                    conn.execute('TRUNCATE tool_settings'); conn.execute((migrate.MIGRATIONS / '002_tool_defaults.sql').read_text()); conn.execute(sql)
                for operation in [self.tools.load_tools, lambda: self.tools.save_tools(payload())]:
                    with self.assertRaises(AdminError) as raised: operation()
                    self.assertEqual(raised.exception.status, 503)

    def test_concurrent_complete_saves_never_mix_configurations(self):
        first = payload(); first['tools'][0]['is_visible'] = False
        second = payload(); second['tools'][1]['is_visible'] = False
        second['tools'][0]['sort_order'], second['tools'][8]['sort_order'] = 8, 0
        with ThreadPoolExecutor(max_workers=2) as executor:
            with database.transaction() as blocker:
                blocker.execute('SELECT tool_key FROM tool_settings ORDER BY tool_key FOR UPDATE')
                futures = [executor.submit(self.tools.save_tools, value) for value in (first, second)]
                deadline = time.monotonic() + 4
                while True:
                    with database.connection() as observer:
                        waiting = observer.execute("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE 'SELECT tool_key, placement,%'").fetchone()[0]
                    if waiting == 2:
                        break
                    self.assertLess(time.monotonic(), deadline, 'both complete saves must reach the row lock')
                    time.sleep(.02)
            results = [future.result(timeout=5) for future in futures]
        self.assertIn(self.tools.load_tools(), results)
        self.assertEqual(sum(not item['is_visible'] for item in self.tools.load_tools()), 1)

    def test_http_auth_csrf_json_atomic_update_and_safe_failure(self):
        from app import admin_auth as auth
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)', ('owner', auth.PASSWORDS.hash('test-only-password')))
        write = {'Origin': 'http://127.0.0.1:5180', 'X-Admin-Request': '1'}
        self.assertEqual(self.client.get('/api/admin/tools').status_code, 401)
        login = self.client.post('/api/admin/login', headers=write, json={'username':'owner','password':'test-only-password'})
        self.assertEqual(login.status_code, 200, login.text)
        headers = write | {'X-CSRF-Token': login.json()['csrf_token']}
        for bad_headers, body, status in [(write, payload(),403), (headers | {'Origin':'https://evil.example'},payload(),403), (headers | {'Content-Type':'text/plain'},payload(),400), (headers,{'tools':[]},400)]:
            response = self.client.put('/api/admin/tools', headers=bad_headers, json=body)
            self.assertEqual(response.status_code,status,response.text)
            self.assertEqual(self.client.get('/api/tools').json(),payload())
        changed = payload(); changed['tools'][-1]['is_visible'] = False
        self.assertEqual(self.client.put('/api/admin/tools', headers=headers, json=changed).json(),changed)
        self.assertEqual(self.client.get('/api/admin/tools').json(),changed)
        with database.transaction() as conn:
            conn.execute('DROP TABLE tool_settings')
        for path in ('/api/tools','/api/admin/tools'):
            response = self.client.get(path)
            self.assertEqual(response.status_code,503,response.text)
            self.assertNotIn('tool_settings',response.text)
