"""Upload boundaries; no shared database or directories."""
import asyncio
from datetime import datetime, timezone
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import Request
from app import admin_auth as auth
from app.settings import Settings, get_settings

ORIGIN = 'http://127.0.0.1:5180'
SESSION = auth.AdminSession(1, 'owner', datetime(2030, 1, 1, tzinfo=timezone.utc), 'a' * 43)
HEADERS = {'Origin': ORIGIN, 'X-Admin-Request': '1', 'X-CSRF-Token': SESSION.csrf_token}


def picture(fmt='PNG', size=(3, 2), **kwargs):
    output = io.BytesIO()
    Image.new('RGB', size, 'red').save(output, format=fmt, **kwargs)
    return output.getvalue()


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.admin_uploads'), 'upload route has not been implemented')
        from app import admin_uploads
        self.uploads = admin_uploads
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / 'uploads'
        self.settings = Settings(app_env='test', upload_dir=str(self.root))
        self.app = FastAPI()
        self.app.include_router(admin_uploads.router)
        self.app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = self.enterContext(TestClient(self.app, base_url=ORIGIN))
        self.enterContext(patch.object(auth, 'current_session', return_value=SESSION))

    def post(self, data=None, name='photo.png', mime='image/png'):
        return self.client.post('/api/admin/files', headers=HEADERS,
                                files={'file': (name, picture() if data is None else data, mime)})

    def error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['error']['code'], code)
        self.assertEqual(set(response.json()), {'error'})
        self.assertNotIn(str(self.root), response.text)

    def test_missing_config_does_not_create_directory(self):
        self.settings = Settings(app_env='test')
        self.error(self.post(), 503, 'upload_unavailable')
        self.assertFalse(self.root.exists())

    def test_unauthenticated_upload_never_reads_body(self):
        reads = []
        async def receive():
            reads.append(True)
            raise AssertionError('unauthorized request read body')
        scope = {'type': 'http', 'method': 'POST', 'path': '/api/admin/files', 'raw_path': b'/api/admin/files',
                 'root_path': '', 'query_string': b'', 'scheme': 'http', 'server': ('127.0.0.1', 5180),
                 'client': ('127.0.0.1', 1234), 'headers': [(k.lower().encode(), v.encode()) for k,v in
                 (HEADERS | {'Content-Type': 'multipart/form-data; boundary=x'}).items()]}
        sent = []
        async def send(message): sent.append(message)
        with patch.object(auth, 'current_session', return_value=None):
            asyncio.run(self.app(scope, receive, send))
        self.assertEqual(sent[0]['status'], 401)
        self.assertEqual(reads, [])

    def test_upload_guard_does_not_relax_json_guard(self):
        for headers, code in [(HEADERS | {'Origin': 'https://evil.example'}, 'origin_forbidden'),
                              (HEADERS | {'X-Admin-Request': '0'}, 'origin_forbidden'),
                              (HEADERS | {'X-CSRF-Token': 'wrong'}, 'csrf_failed')]:
            response = self.client.post('/api/admin/files', headers=headers, files={'file': ('a.png', picture(), 'image/png')})
            self.error(response, 403, code)
        self.error(self.client.post('/api/admin/files', headers=HEADERS, json={}), 400, 'invalid_request')
        request = Request({'type': 'http', 'headers': [(b'origin', ORIGIN.encode()), (b'x-admin-request', b'1'),
                                                      (b'content-type', b'multipart/form-data; boundary=x')],
                           'scheme': 'http', 'server': ('127.0.0.1', 5180), 'path': '/'})
        with self.assertRaises(auth.AdminError): auth.require_write_origin(request, self.settings)

    def test_multipart_requires_exactly_one_file(self):
        cases = [([], {'extra': 'value'}), ([('wrong', ('a.png', picture(), 'image/png'))], None),
                 ([('file', ('a.png', picture(), 'image/png')), ('file', ('b.png', picture(), 'image/png'))], None),
                 ([('file', ('a.png', picture(), 'image/png'))], {'extra': 'value'})]
        for files, data in cases:
            self.error(self.client.post('/api/admin/files', headers=HEADERS, files=files, data=data), 400, 'invalid_request')
        self.assertFalse(self.root.exists())

    def test_body_limit_is_checked_before_multipart_parser(self):
        self.error(self.client.post('/api/admin/files', headers=HEADERS | {'Content-Type': 'multipart/form-data; boundary=x'},
                                   content=b'x' * (10 * 1024 * 1024 + 65537)), 413, 'file_too_large')
        self.assertFalse(self.root.exists())

    def test_chunked_body_is_bounded_without_content_length(self):
        response = self.client.post('/api/admin/files', headers=HEADERS | {'Content-Type': 'multipart/form-data; boundary=x'},
                                    content=(b'x' * 1048576 for _ in range(11)))
        self.error(response, 413, 'file_too_large')

    def test_empty_truncated_or_broken_images_are_rejected(self):
        for value in (b'', b'not an image', picture()[:40], picture('JPEG')[:-20]):
            self.error(self.post(value), 400, 'invalid_image')
        self.assertFalse(self.root.exists())

    def test_disguised_and_unsupported_images_are_rejected(self):
        for data, name, mime in [(picture(), 'a.jpg', 'image/jpeg'), (picture(), 'a.png', 'image/jpeg'),
                                 (b'<svg/>', 'a.svg', 'image/svg+xml'), (picture('GIF'), 'a.gif', 'image/gif')]:
            self.error(self.post(data, name, mime), 415, 'unsupported_image')

    def test_multiframe_and_pixel_limit_are_rejected(self):
        output = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(output, format='PNG', save_all=True,
                                           append_images=[Image.new('RGB', (2,2), 'blue')])
        self.error(self.post(output.getvalue()), 415, 'unsupported_image')
        self.error(self.post(picture(size=(6667, 6000))), 400, 'invalid_image')

    def test_symlink_and_unsafe_directory_permissions_are_rejected(self):
        target = self.root.parent / 'target'
        target.mkdir(mode=0o700)
        self.root.symlink_to(target, target_is_directory=True)
        self.error(self.post(), 503, 'upload_unavailable')
        self.root.unlink()
        self.root.mkdir(mode=0o777)
        self.root.chmod(0o777)
        self.error(self.post(), 503, 'upload_unavailable')
        self.assertEqual(list(target.iterdir()), [])

    def test_anonymous_read_is_rejected_even_for_unknown_id(self):
        with patch.object(auth, 'current_session', return_value=None):
            self.error(self.client.get('/api/admin/files/' + str(uuid4())), 401, 'unauthenticated')

    def test_invalid_id_uses_safe_error_envelope(self):
        self.error(self.client.get('/api/admin/files/not-a-uuid'), 400, 'invalid_request')

    def test_unfinished_multipart_never_stores_a_completed_first_part(self):
        body = (b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\n'
                b'Content-Type: image/png\r\n\r\n' + picture() + b'\r\n--boundary\r\n')
        response = self.client.post('/api/admin/files', headers=HEADERS | {
            'Content-Type': 'multipart/form-data; boundary=boundary'}, content=body)
        self.error(response, 400, 'invalid_request')
        self.assertFalse(self.root.exists())

    def test_file_limit_is_independent_of_multipart_overhead(self):
        self.error(self.post(picture() + b'x' * 10485760), 413, 'file_too_large')
        self.assertFalse(self.root.exists())

    def test_read_missing_storage_config_is_503_for_live_admin(self):
        self.settings = Settings(app_env='test')
        self.error(self.client.get('/api/admin/files/' + str(uuid4())), 503, 'upload_unavailable')

    def test_raw_asgi_chunk_stream_stops_at_bound(self):
        reads = []
        async def receive():
            reads.append(True)
            if len(reads) > 11:
                raise AssertionError('continued receiving after body limit')
            return {'type': 'http.request', 'body': b'x' * 1048576, 'more_body': True}
        scope = {'type': 'http', 'method': 'POST', 'path': '/api/admin/files', 'raw_path': b'/api/admin/files',
                 'root_path': '', 'query_string': b'', 'scheme': 'http', 'server': ('127.0.0.1', 5180),
                 'client': ('127.0.0.1', 1234), 'headers': [(k.lower().encode(), v.encode()) for k,v in
                 (HEADERS | {'Content-Type': 'multipart/form-data; boundary=x'}).items()]}
        sent = []
        async def send(message): sent.append(message)
        asyncio.run(self.app(scope, receive, send))
        self.assertEqual(sent[0]['status'], 413)
        self.assertEqual(len(reads), 11)
        self.assertFalse(self.root.exists())

    def test_symlink_parent_is_rejected(self):
        target = self.root.parent / 'target'
        target.mkdir(mode=0o700)
        link = self.root.parent / 'linked'
        link.symlink_to(target, target_is_directory=True)
        self.settings = self.settings.model_copy(update={'upload_dir': str(link / 'uploads')})
        self.error(self.post(), 503, 'upload_unavailable')
        self.assertFalse((target / 'uploads').exists())

    def test_production_storage_inside_release_is_disabled_at_request_time(self):
        self.settings = self.settings.model_copy(update={'app_env': 'production',
            'admin_allowed_origins': ('https://admin.example',),
            'upload_dir': str(Path(self.uploads.__file__).resolve().parents[2] / 'uploads')})
        with TestClient(self.app, base_url='https://admin.example') as client:
            response = client.post('/api/admin/files', headers=HEADERS | {'Origin': 'https://admin.example'},
                                   files={'file': ('a.png', picture(), 'image/png')})
        self.error(response, 503, 'upload_unavailable')

    def test_upload_dir_configuration_rejects_relative_traversal_and_null(self):
        from pydantic import ValidationError
        for value in ('uploads', '/private/../tmp/uploads', '/private/tmp/invalid\x00path'):
            with self.assertRaises(ValidationError):
                Settings(app_env='test', upload_dir=value)

    def test_png_truncated_iend_and_corrupt_terminal_crc_are_rejected(self):
        value = picture()
        for data in (value[:-1], value[:-2], value[:-4], value[:-1] + bytes([value[-1] ^ 1])):
            self.error(self.post(data), 400, 'invalid_image')
        self.assertFalse(self.root.exists())

    def test_double_leading_slash_cannot_bypass_production_release_guard(self):
        release = Path(self.uploads.__file__).resolve().parents[2]
        settings = self.settings.model_copy(update={
            'app_env': 'production', 'upload_dir': '//' + str(release).lstrip('/') + '/uploads'})
        with self.assertRaises(auth.AdminError) as caught:
            self.uploads.configured_path(settings)
        self.assertEqual((caught.exception.status, caught.exception.code), (503, 'upload_unavailable'))
        self.assertFalse((release / 'uploads').exists())

    def test_multipart_rollover_disk_full_is_safe_and_closes_spooled_file(self):
        import errno
        import tempfile
        from starlette import formparsers
        real_spool = tempfile.SpooledTemporaryFile
        spools = []
        def track_spool(*args, **kwargs):
            file = real_spool(*args, **kwargs)
            spools.append(file)
            return file
        with patch.object(formparsers, 'SpooledTemporaryFile', side_effect=track_spool), \
             patch.object(tempfile, 'TemporaryFile', side_effect=OSError(errno.ENOSPC, '/private/secret-path disk full')), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture() + b'x' * 1048576, 'image/png')})
        self.error(response, 503, 'upload_unavailable')
        self.assertNotIn('secret-path', response.text)
        self.assertTrue(spools)
        self.assertTrue(all(file.closed for file in spools))
        self.assertFalse(self.root.exists())

    def test_multipart_tempfile_creation_failure_is_safe(self):
        from starlette import formparsers
        with patch.object(formparsers, 'SpooledTemporaryFile', side_effect=OSError('private temp directory unavailable')), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture(), 'image/png')})
        self.error(response, 503, 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertFalse(self.root.exists())

    def test_tempfile_read_failure_is_safe_and_closes_spooled_file(self):
        import tempfile
        from starlette import formparsers
        from starlette.datastructures import UploadFile
        real_spool = tempfile.SpooledTemporaryFile
        spools = []
        def track_spool(*args, **kwargs):
            file = real_spool(*args, **kwargs)
            spools.append(file)
            return file
        with patch.object(formparsers, 'SpooledTemporaryFile', side_effect=track_spool), \
             patch.object(UploadFile, 'read', side_effect=OSError('private read fault')), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture(), 'image/png')})
        self.error(response, 503, 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertTrue(spools)
        self.assertTrue(all(file.closed for file in spools))
        self.assertFalse(self.root.exists())

    def test_tempfile_close_failure_is_safe(self):
        from starlette.datastructures import FormData
        close = FormData.close
        async def faulty_close(form):
            await close(form)
            raise OSError('private close fault')
        with patch.object(FormData, 'close', faulty_close), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture(), 'image/png')})
        self.error(response, 503, 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertFalse(self.root.exists())

    def test_tempfile_cleanup_failure_preserves_file_size_error(self):
        from starlette.datastructures import FormData
        close = FormData.close
        async def faulty_close(form):
            await close(form)
            raise OSError('private cleanup fault')
        with patch.object(FormData, 'close', faulty_close), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture() + b'x' * 10485760, 'image/png')})
        self.error(response, 413, 'file_too_large')
        self.assertFalse(self.root.exists())

    def test_tempfile_outage_does_not_mask_auth_or_body_size_errors(self):
        from starlette import formparsers
        with patch.object(formparsers, 'SpooledTemporaryFile', side_effect=OSError('private temp fault')):
            with patch.object(auth, 'current_session', return_value=None):
                self.error(self.post(), 401, 'unauthenticated')
            response = self.client.post('/api/admin/files', headers=HEADERS | {
                'Content-Type': 'multipart/form-data; boundary=x'}, content=b'x' * (10485760 + 65537))
            self.error(response, 413, 'file_too_large')
        self.assertFalse(self.root.exists())

    def test_initial_storage_directory_open_failure_is_safe(self):
        import errno
        from app import admin_uploads
        real_open = admin_uploads.os.open
        def faulty_open(path, *args, **kwargs):
            if path == '/':
                raise OSError(errno.EMFILE, 'private descriptor exhaustion')
            return real_open(path, *args, **kwargs)
        with patch.object(admin_uploads.os, 'open', side_effect=faulty_open), \
             TestClient(self.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            response = client.post('/api/admin/files', headers=HEADERS,
                                   files={'file': ('a.png', picture(), 'image/png')})
        self.error(response, 503, 'upload_unavailable')
        self.assertNotIn('private', response.text)
        self.assertFalse(self.root.exists())

    def test_double_leading_slash_outside_release_keeps_nofollow_storage_available(self):
        settings = self.settings.model_copy(update={
            'app_env': 'production', 'upload_dir': '/' + str(self.root)})
        with self.uploads.storage_directory(settings, create=True) as descriptor:
            import os
            self.assertEqual(os.fstat(descriptor).st_ino, self.root.stat().st_ino)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_failed_component_open_closes_owned_root_descriptor(self):
        import errno
        import os
        real_open = os.open
        root_fds = []
        def faulty_open(path, *args, **kwargs):
            if path == '/':
                descriptor = real_open(path, *args, **kwargs)
                root_fds.append(descriptor)
                return descriptor
            if kwargs.get('dir_fd') in root_fds:
                raise OSError(errno.EACCES, 'private component permission fault')
            return real_open(path, *args, **kwargs)
        with patch.object(os, 'open', side_effect=faulty_open):
            self.error(self.post(), 503, 'upload_unavailable')
        self.assertTrue(root_fds)
        for descriptor in root_fds:
            with self.assertRaises(OSError) as caught:
                os.fstat(descriptor)
            self.assertEqual(caught.exception.errno, errno.EBADF)
        self.assertFalse(self.root.exists())
