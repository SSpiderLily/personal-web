"""Real upload transactions on the owned disposable PostgreSQL cluster."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import database, migrate, admin_auth as auth
from app.admin_routes import router as auth_router
from app.settings import get_settings
from test_admin_uploads import HEADERS, ORIGIN, picture


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'requires owned temporary PostgreSQL')
class UploadIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.admin_uploads'), 'upload route has not been implemented')
        from app import admin_uploads
        self.uploads = admin_uploads
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / 'uploads'
        self.settings = get_settings().model_copy(update={'upload_dir': str(self.root)})
        self.app = FastAPI()
        self.app.include_router(auth_router)
        self.app.include_router(admin_uploads.router)
        self.app.dependency_overrides[get_settings] = lambda: self.settings
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)', ('owner', auth.PASSWORDS.hash('temporary-upload-password')))
        self.client = self.enterContext(TestClient(self.app, base_url=ORIGIN))
        response = self.client.post('/api/admin/login', headers=HEADERS, json={'username': 'owner', 'password': 'temporary-upload-password'})
        self.assertEqual(response.status_code, 200, response.text)
        self.headers = HEADERS | {'X-CSRF-Token': response.json()['csrf_token']}

    def post(self, fmt='PNG', suffix='png', mime='image/png', client=None):
        return (client or self.client).post('/api/admin/files', headers=self.headers,
                                            files={'file': ('../original.' + suffix, picture(fmt), mime)})

    def test_roundtrip_all_formats_and_metadata(self):
        for fmt, suffix, mime in [('PNG', 'png', 'image/png'), ('JPEG', 'jpg', 'image/jpeg'), ('WEBP', 'webp', 'image/webp')]:
            response = self.post(fmt, suffix, mime)
            self.assertEqual(response.status_code, 201, response.text)
            value = response.json()
            self.assertEqual(set(value), {'id', 'media_type', 'byte_size', 'width', 'height', 'url'})
            self.assertEqual((value['media_type'], value['width'], value['height']), (mime, 3, 2))
            self.assertEqual(value['url'], '/api/admin/files/' + value['id'])
            read = self.client.get(value['url'])
            self.assertEqual(read.content, picture(fmt))
            self.assertEqual(read.headers['content-type'], mime)
            self.assertEqual(read.headers['x-content-type-options'], 'nosniff')
            self.assertEqual(read.headers['cache-control'], 'no-store')
            with database.connection() as conn:
                row = conn.execute('SELECT storage_key, original_name, byte_size FROM uploaded_files WHERE id=%s', (value['id'],)).fetchone()
            self.assertEqual(row, (value['id'], '../original.' + suffix, len(picture(fmt))))
            self.assertEqual((self.root / value['id']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_unknown_ids_and_orphan_files_are_not_public(self):
        self.root.mkdir(mode=0o700)
        orphan = str(uuid4())
        (self.root / orphan).write_bytes(picture())
        for identifier in (str(uuid4()), orphan):
            response = self.client.get('/api/admin/files/' + identifier)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()['error']['code'], 'file_not_found')
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/admin/files/' + orphan).status_code, 401)

    def test_metadata_commit_failure_rolls_back_and_removes_file(self):
        @contextmanager
        def failed_transaction(settings):
            with database.transaction(settings) as conn:
                yield conn
                raise RuntimeError('private commit detail')
        with patch.object(self.uploads, 'transaction', failed_transaction):
            response = self.post()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()['error']['code'], 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertEqual(list(self.root.iterdir()), [])
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(), (0,))

    def test_symlink_file_and_tampered_storage_keys_fail_closed(self):
        value = self.post().json()
        path = self.root / value['id']
        path.unlink()
        path.symlink_to(self.root.parent / 'outside')
        (self.root.parent / 'outside').write_bytes(b'secret')
        response = self.client.get(value['url'])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.text)
        with database.transaction() as conn:
            conn.execute('UPDATE uploaded_files SET storage_key=%s WHERE id=%s', ('../outside', value['id']))
        self.assertEqual(self.client.get(value['url']).status_code, 503)

    def test_expired_session_and_forged_csrf_cannot_upload(self):
        self.assertEqual(self.client.post('/api/admin/files', headers=HEADERS, files={'file': ('a.png', picture(), 'image/png')}).status_code, 403)
        with database.transaction() as conn:
            conn.execute('UPDATE admin_sessions SET revoked_at=now()')
        self.assertEqual(self.post().status_code, 401)
        self.assertFalse(self.root.exists())

    def test_concurrent_uploads_have_distinct_storage_and_metadata(self):
        token = self.client.cookies.get(auth.COOKIE)
        def upload(_):
            with TestClient(self.app, base_url=ORIGIN) as client:
                client.cookies.set(auth.COOKIE, token)
                return self.post(client=client)
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(upload, range(8)))
        self.assertTrue(all(response.status_code == 201 for response in responses), [r.text for r in responses])
        ids = {response.json()['id'] for response in responses}
        self.assertEqual(len(ids), 8)
        self.assertEqual({path.name for path in self.root.iterdir()}, ids)
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(), (8,))

    def test_exact_file_limit_is_allowed(self):
        value = picture()
        value += b'\0' * (10485760 - len(value))
        response = self.client.post('/api/admin/files', headers=self.headers, files={'file': ('a.png', value, 'image/png')})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['byte_size'], 10485760)
        self.assertEqual(len(self.client.get(response.json()['url']).content), 10485760)

    def test_uuid_collision_does_not_overwrite_or_remove_existing_file(self):
        original = self.post().json()
        from uuid import UUID
        with patch.object(self.uploads, 'uuid4', return_value=UUID(original['id'])):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get(original['url']).content, picture())
        with database.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(), (1,))

    def test_unsafe_file_modes_and_hardlinks_are_rejected(self):
        original = self.post().json()
        path = self.root / original['id']
        path.chmod(0o644)
        self.assertEqual(self.client.get(original['url']).status_code, 503)
        path.chmod(0o600)
        os.link(path, self.root.parent / 'hardlink')
        self.assertEqual(self.client.get(original['url']).status_code, 503)

    def test_storage_faults_leave_no_final_files_or_metadata(self):
        import errno
        import tempfile
        from starlette import formparsers
        from starlette.datastructures import UploadFile
        real_open = self.uploads.os.open
        def faulty_open(path, *args, **kwargs):
            if path == '/':
                raise OSError(errno.EMFILE, 'private root descriptor fault')
            return real_open(path, *args, **kwargs)
        faults = [patch.object(tempfile, 'TemporaryFile', side_effect=OSError(errno.ENOSPC, 'private temp fault')),
                  patch.object(formparsers, 'SpooledTemporaryFile', side_effect=OSError(errno.EACCES, 'private temp creation fault')),
                  patch.object(UploadFile, 'read', side_effect=OSError('private temp read fault')),
                  patch.object(self.uploads.os, 'open', side_effect=faulty_open)]
        with TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            client.cookies.set(auth.COOKIE, self.client.cookies.get(auth.COOKIE))
            for fault in faults:
                with fault:
                    response = client.post('/api/admin/files', headers=self.headers,
                        files={'file': ('a.png', picture() + b'x' * 1048576, 'image/png')})
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json()['error']['code'], 'upload_unavailable')
                self.assertNotIn('private', response.text)
                self.assertFalse(self.root.exists())
                with database.connection() as conn:
                    self.assertEqual(conn.execute('SELECT count(*) FROM uploaded_files').fetchone(), (0,))

    def test_initial_directory_open_fault_on_read_is_safe(self):
        import errno
        original = self.post().json()
        real_open = self.uploads.os.open
        def faulty_open(path, *args, **kwargs):
            if path == '/':
                raise OSError(errno.EMFILE, 'private read descriptor fault')
            return real_open(path, *args, **kwargs)
        with patch.object(self.uploads.os, 'open', side_effect=faulty_open), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            client.cookies.set(auth.COOKIE, self.client.cookies.get(auth.COOKIE))
            response = client.get(original['url'])
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()['error']['code'], 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertEqual(self.client.get(original['url']).content, picture())
