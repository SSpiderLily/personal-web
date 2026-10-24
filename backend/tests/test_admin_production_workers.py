"""Real two-worker persistence on the runner-owned PostgreSQL, never real services.

This covers local HTTP process/restart behavior; real TLS and proxy trust remain
separate deployment acceptance checks. The worker PID header exists only in a
temporary wrapper, never in the production application.
"""
from concurrent.futures import ThreadPoolExecutor
import http.client
from http.cookies import SimpleCookie
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image
from app import database, migrate
from app.admin_init import initialize_admin
from app.settings import get_settings


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'owned disposable PostgreSQL only')
class ProductionWorkerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        self.assertEqual(self.settings.app_env, 'test')
        database.validate_test_target(self.settings)
        self.process = None
        self.addCleanup(self.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix='pw-workers-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uploads = self.root / 'uploads'
        self.uploads.mkdir(mode=0o700)
        self.log = self.root / 'gunicorn.log'
        self.backend = Path(__file__).resolve().parents[1]
        (self.root / 'worker_probe.py').write_text(
            "import os\nfrom app.main import app\n"
            "@app.middleware('http')\n"
            "async def worker_header(request, call_next):\n"
            "    response = await call_next(request)\n"
            "    response.headers['X-Test-Worker-Pid'] = str(os.getpid())\n"
            "    return response\n")
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.port = reservation.getsockname()[1]
        self.origin = f'http://127.0.0.1:{self.port}'
        self.write = {'Origin': self.origin, 'X-Admin-Request': '1'}
        self.environment = dict(os.environ, APP_ENV='test', DEBUG='false',
            DB_HOST=self.settings.db_host, DB_PORT=str(self.settings.db_port),
            DB_NAME=self.settings.db_name, DB_USER=self.settings.db_user,
            DB_PASSWORD=self.settings.db_password.get_secret_value(),
            UPLOAD_DIR=str(self.uploads), ADMIN_ALLOWED_ORIGINS=json.dumps([self.origin]),
            PYTHONPATH=os.pathsep.join((str(self.root), str(self.backend))))
        with database.transaction(self.settings) as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        initialize_admin(self.settings, 'worker-owner', 'temporary-worker-password')
        image = io.BytesIO()
        Image.new('RGB', (3, 2), (15, 120, 220)).save(image, format='PNG')
        self.png = image.getvalue()

    def request(self, method, path, *, headers=None, value=None, body=None):
        outgoing = dict(headers or {})
        if value is not None:
            outgoing['Content-Type'] = 'application/json'
            body = json.dumps(value).encode()
        # New TCP connections let the shared Gunicorn listener select either worker.
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=outgoing)
            response = conn.getresponse()
            return response.status, dict((key.lower(), item) for key, item in response.getheaders()), response.read()
        finally:
            conn.close()

    def start(self):
        self.process = subprocess.Popen([
            sys.executable, '-m', 'gunicorn', 'worker_probe:app', '-w', '2',
            '-k', 'uvicorn.workers.UvicornWorker', '--bind', f'127.0.0.1:{self.port}',
            '--graceful-timeout', '3', '--timeout', '15', '--error-logfile', str(self.log)],
            cwd=self.backend, env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.assertIsNone(self.process.poll(), self.log.read_text() if self.log.exists() else 'Gunicorn exited')
            try:
                self.both_workers(lambda: self.request('GET', '/api/health'), timeout=0.5)
                return
            except (OSError, AssertionError):
                time.sleep(0.05)
        self.fail('Two Gunicorn workers failed to become ready: ' + self.log.read_text())

    def stop(self):
        if self.process is None:
            return
        process, self.process = self.process, None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)

    def both_workers(self, operation, *, status=200, timeout=8):
        seen, responses = set(), []
        deadline = time.monotonic() + timeout
        with ThreadPoolExecutor(max_workers=4) as executor:
            while time.monotonic() < deadline:
                batch = list(executor.map(lambda _: operation(), range(4)))
                for result in batch:
                    self.assertEqual(result[0], status, result[2].decode(errors='replace'))
                    seen.add(int(result[1]['x-test-worker-pid']))
                    responses.append(result)
                if len(seen) == 2:
                    return seen, responses
        self.fail(f'Expected responses from both workers, observed {seen}')

    def upload(self, headers):
        boundary = 'personal-web-worker-test-boundary'
        content = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.png"\r\n'
                   'Content-Type: image/png\r\n\r\n').encode() + self.png + f'\r\n--{boundary}--\r\n'.encode()
        result = self.request('POST', '/api/admin/files', headers=headers | {
            'Content-Type': 'multipart/form-data; boundary=' + boundary}, body=content)
        self.assertEqual(result[0], 201, result[2].decode())
        return json.loads(result[2])

    def test_both_workers_share_auth_csrf_and_survive_restart_with_db_and_images(self):
        try:
            self.start()
            original_workers, logins = self.both_workers(lambda: self.request('POST', '/api/admin/login',
                headers=self.write, value={'username': 'worker-owner', 'password': 'temporary-worker-password'}))
            selected = logins[0]
            cookie = SimpleCookie()
            cookie.load(selected[1]['set-cookie'])
            token = cookie['personal_web_session'].value
            authenticated = {'Cookie': 'personal_web_session=' + token}
            csrf = json.loads(selected[2])['csrf_token']
            writes = self.write | authenticated | {'X-CSRF-Token': csrf}
            pids, sessions = self.both_workers(lambda: self.request('GET', '/api/admin/session', headers=authenticated))
            self.assertEqual(pids, original_workers)
            for _, _, raw in sessions:
                self.assertEqual(json.loads(raw), json.loads(selected[2]))
            tools = {'tools': [dict(tool_key=f'grid_{i:02}', placement='grid', is_visible=True, sort_order=i-1)
                               for i in range(1, 10)] + [dict(tool_key='dice', placement='floating', is_visible=False, sort_order=0)]}
            pids, denied = self.both_workers(lambda: self.request('PUT', '/api/admin/tools',
                headers=writes | {'X-CSRF-Token': 'invalid'}, value=tools), status=403)
            self.assertEqual(pids, original_workers)
            self.assertTrue(all(json.loads(raw)['error']['code'] == 'csrf_failed' for _, _, raw in denied))
            unchanged = json.loads(self.request('GET', '/api/admin/tools', headers=authenticated)[2])
            self.assertTrue(next(item for item in unchanged['tools'] if item['tool_key'] == 'dice')['is_visible'])
            pids, saved = self.both_workers(lambda: self.request('PUT', '/api/admin/tools', headers=writes, value=tools))
            self.assertEqual(pids, original_workers)
            self.assertTrue(all(json.loads(raw) == tools for _, _, raw in saved))
            private, cover = self.upload(writes), self.upload(writes)
            self.assertEqual(self.request('GET', '/api/files/' + private['id'])[0], 404)
            value = dict(name='Persisted worker project', summary='Restart persistence', category='',
                tech_stack=['Vue'], features=[], cover_file_id=cover['id'], cover_alt='Probe',
                demo_url=None, source_url=None, blocks=[dict(kind='text', body='Saved by two-worker service')], screenshots=[])
            created = self.request('POST', '/api/admin/projects', headers=writes, value=value)
            self.assertEqual(created[0], 200, created[2].decode())
            identifier = json.loads(created[2])['project']['id']
            published = self.request('POST', f'/api/admin/projects/{identifier}/publish', headers=writes, value={})
            self.assertEqual(published[0], 200, published[2].decode())
            for kind in ({'kind': 'website'}, {'kind': 'project', 'project_id': identifier}):
                _, records = self.both_workers(lambda: self.request('POST', '/api/admin/visits', headers=writes, value=kind))
                self.assertTrue(all(json.loads(raw) == {'recorded': False} for _, _, raw in records))
            self.stop()
            self.start()
            restarted_workers, restored = self.both_workers(lambda: self.request('GET', '/api/admin/session', headers=authenticated))
            self.assertTrue(original_workers.isdisjoint(restarted_workers))
            self.assertTrue(all(json.loads(raw) == json.loads(selected[2]) for _, _, raw in restored))
            for path, headers in ((private['url'], authenticated), ('/api/files/' + cover['id'], {})):
                _, images = self.both_workers(lambda: self.request('GET', path, headers=headers))
                for status, metadata, raw in images:
                    self.assertEqual(raw, self.png)
                    self.assertEqual(metadata['cache-control'], 'no-store')
                    self.assertEqual(metadata['x-content-type-options'], 'nosniff')
            self.assertEqual(self.request('GET', private['url'])[0], 401)
            self.assertEqual(self.request('GET', '/api/files/' + private['id'])[0], 404)
            _, settings = self.both_workers(lambda: self.request('GET', '/api/admin/tools', headers=authenticated))
            self.assertTrue(all(json.loads(raw) == tools for _, _, raw in settings))
            _, projects = self.both_workers(lambda: self.request('GET', f'/api/projects/{identifier}'))
            self.assertTrue(all(json.loads(raw)['project']['name'] == 'Persisted worker project' for _, _, raw in projects))
            _, statistics = self.both_workers(lambda: self.request('GET', '/api/admin/statistics?days=7', headers=authenticated))
            for _, _, raw in statistics:
                report = json.loads(raw)
                self.assertEqual(report['website_visitors'], 0)
                self.assertEqual(report['projects'][0]['project_id'], identifier)
                self.assertEqual(report['projects'][0]['visitors'], 0)
            with database.transaction(self.settings) as conn:
                conn.execute('SET TRANSACTION READ ONLY')
                self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(), (2,))
                self.assertEqual(conn.execute("SELECT name,status FROM projects").fetchone(), ('Persisted worker project', 'published'))
                self.assertFalse(conn.execute("SELECT is_visible FROM tool_settings WHERE tool_key='dice'").fetchone()[0])
                self.assertEqual(conn.execute('SELECT count(*) FROM site_daily_visitors').fetchone(), (0,))
                self.assertEqual(conn.execute('SELECT count(*) FROM project_daily_visitors').fetchone(), (0,))
            self.assertEqual(self.uploads.stat().st_mode & 0o777, 0o700)
            for image in (private, cover):
                self.assertEqual((self.uploads / image['id']).stat().st_mode & 0o777, 0o600)
        finally:
            self.stop()
