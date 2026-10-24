"""Real publication authorization on the runner-owned disposable database only."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import admin_uploads, database, migrate
from app.settings import get_settings
from test_admin_uploads import picture


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1', 'requires owned temporary PostgreSQL')
class PublicFileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.public_file_routes'), 'public file routes are not implemented')
        from app import public_file_routes, file_publication
        self.routes, self.publication = public_file_routes, file_publication
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / 'uploads'
        self.settings = get_settings().model_copy(update={'upload_dir': str(self.root)})
        self.assertEqual(self.settings.app_env, 'test')
        database.validate_test_target(self.settings)
        # scripts/test_database.py owns this new random personal_web_test_* DB,
        # creates its local cluster, clears DB_/PG overrides and cleans it up.
        with database.transaction(self.settings) as conn:
            conn.execute('DROP SCHEMA public CASCADE')
            conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        app = FastAPI()
        app.include_router(public_file_routes.router)
        app.include_router(admin_uploads.router)
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = self.enterContext(TestClient(app))

    def image(self):
        return UUID(admin_uploads.save_image(self.settings, picture(), 'a.png', 'image/png')['id'])

    def project(self, identifier, status='published', kind='cover'):
        with database.transaction(self.settings) as conn:
            project_id = conn.execute('INSERT INTO projects(status,cover_file_id) VALUES (%s,%s) RETURNING id',
                                      (status, identifier if kind == 'cover' else None)).fetchone()[0]
            if kind == 'block':
                conn.execute("INSERT INTO project_blocks(project_id,position,kind,file_id) VALUES (%s,0,'image',%s)", (project_id, identifier))
            elif kind == 'screenshot':
                conn.execute('INSERT INTO project_screenshots(project_id,position,file_id) VALUES (%s,0,%s)', (project_id, identifier))
        return project_id

    def avatar(self, identifier):
        with database.transaction(self.settings) as conn:
            conn.execute("INSERT INTO site_profile(name,title,introduction,avatar_file_id) VALUES ('','','',%s) "
                         'ON CONFLICT (id) DO UPDATE SET avatar_file_id=excluded.avatar_file_id', (identifier,))

    def read(self, identifier):
        return self.client.get('/api/files/' + str(identifier))

    def error(self, response, status=404, code='file_not_found'):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['error']['code'], code)
        self.assertEqual(set(response.json()), {'error'})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn(str(self.root), response.text)

    def allowed(self, identifier):
        response = self.read(identifier)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, picture())
        self.assertEqual(response.headers['content-type'], 'image/png')
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_only_published_cover_block_or_screenshot_allows_anonymous_read(self):
        for kind in ('cover', 'block', 'screenshot'):
            for status, expected in (('draft', False), ('published', True), ('archived', False)):
                with self.subTest(kind=kind, status=status):
                    identifier = self.image()
                    self.project(identifier, status, kind)
                    with database.connection(self.settings) as conn:
                        self.assertIs(self.publication.is_public_reference(conn, identifier), expected)
                    if expected:
                        self.allowed(identifier)
                    else:
                        self.error(self.read(identifier))

    def test_unreferenced_unknown_and_invalid_are_same_error(self):
        responses = [self.read(value) for value in (self.image(), uuid4(), 'invalid')]
        for response in responses:
            self.error(response)
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[1].json(), responses[2].json())

    def test_private_endpoint_still_requires_login_for_published_image(self):
        identifier = self.image()
        self.project(identifier)
        self.allowed(identifier)
        self.error(self.client.get('/api/admin/files/' + str(identifier)), 401, 'unauthenticated')

    def test_shared_reference_survives_until_last_published_project_archived(self):
        identifier = self.image()
        first = self.project(identifier)
        second = self.project(identifier, kind='block')
        with database.transaction(self.settings) as conn:
            conn.execute("UPDATE projects SET status='archived' WHERE id=%s", (first,))
        self.allowed(identifier)
        with database.transaction(self.settings) as conn:
            conn.execute("UPDATE projects SET status='archived' WHERE id=%s", (second,))
        self.error(self.read(identifier))

    def test_avatar_replacement_revokes_old_unless_project_still_references_it(self):
        old, new = self.image(), self.image()
        self.avatar(old)
        self.allowed(old)
        self.avatar(new)
        self.error(self.read(old))
        self.allowed(new)
        self.project(old)
        self.allowed(old)
        self.avatar(None)
        self.error(self.read(new))
        self.allowed(old)

    def test_replacing_each_project_reference_revokes_old_image(self):
        for kind in ('cover', 'block', 'screenshot'):
            with self.subTest(kind=kind):
                old, new = self.image(), self.image()
                project_id = self.project(old, kind=kind)
                self.allowed(old)
                with database.transaction(self.settings) as conn:
                    if kind == 'cover':
                        conn.execute('UPDATE projects SET cover_file_id=%s WHERE id=%s', (new, project_id))
                    elif kind == 'block':
                        conn.execute('UPDATE project_blocks SET file_id=%s WHERE project_id=%s', (new, project_id))
                    else:
                        conn.execute('UPDATE project_screenshots SET file_id=%s WHERE project_id=%s', (new, project_id))
                self.error(self.read(old))
                self.allowed(new)

    def test_uncommitted_replacement_and_rollback_never_change_public_access(self):
        old, new = self.image(), self.image()
        project_id = self.project(old)
        with self.assertRaises(RuntimeError):
            with database.transaction(self.settings) as conn:
                conn.execute('UPDATE projects SET cover_file_id=%s WHERE id=%s', (new, project_id))
                self.assertFalse(self.publication.is_public_reference(conn, old))
                self.assertTrue(self.publication.is_public_reference(conn, new))
                self.allowed(old)
                self.error(self.read(new))
                raise RuntimeError('rollback')
        self.allowed(old)
        self.error(self.read(new))

    def test_unreferenced_ids_never_reach_private_loader_even_without_storage_config(self):
        identifier = self.image()
        self.settings = self.settings.model_copy(update={'upload_dir': None})
        with patch.object(admin_uploads, 'load_image', side_effect=AssertionError('read before authorization')):
            self.error(self.read(identifier))
            self.error(self.read(uuid4()))

    def test_authorized_missing_or_unconfigured_storage_returns_503(self):
        identifier = self.image()
        self.project(identifier)
        (self.root / str(identifier)).unlink()
        self.error(self.read(identifier), 503, 'upload_unavailable')
        self.settings = self.settings.model_copy(update={'upload_dir': None})
        self.error(self.read(identifier), 503, 'upload_unavailable')

    def test_corrupt_metadata_cannot_escape_storage_root(self):
        identifier = self.image()
        self.project(identifier)
        for key, mime, size in (('../secret', 'image/png', 10), (str(identifier), 'text/html', 10),
                                (str(identifier), 'image/png', 10485761)):
            with database.transaction(self.settings) as conn:
                conn.execute('UPDATE uploaded_files SET storage_key=%s,media_type=%s,byte_size=%s WHERE id=%s',
                             (key, mime, size, identifier))
            self.error(self.read(identifier), 503, 'upload_unavailable')

    def test_symlink_hardlink_fifo_and_file_or_directory_permissions_rejected(self):
        identifier = self.image()
        self.project(identifier)
        path, backup = self.root / str(identifier), self.root / 'backup'
        path.rename(backup)
        path.symlink_to(backup)
        self.error(self.read(identifier), 503, 'upload_unavailable')
        path.unlink()
        os.link(backup, path)
        self.error(self.read(identifier), 503, 'upload_unavailable')
        path.unlink()
        os.mkfifo(path, mode=0o600)
        self.error(self.read(identifier), 503, 'upload_unavailable')
        path.unlink()
        backup.rename(path)
        path.chmod(0o644)
        self.error(self.read(identifier), 503, 'upload_unavailable')
        path.chmod(0o600)
        self.root.chmod(0o755)
        self.error(self.read(identifier), 503, 'upload_unavailable')

    def test_symlink_directory_or_parent_rejected(self):
        identifier = self.image()
        self.project(identifier)
        moved = self.root.parent / 'moved'
        self.root.rename(moved)
        self.root.symlink_to(moved, target_is_directory=True)
        self.error(self.read(identifier), 503, 'upload_unavailable')
        link = self.root.parent / 'linked'
        link.symlink_to(self.root.parent, target_is_directory=True)
        self.settings = self.settings.model_copy(update={'upload_dir': str(link / 'moved')})
        self.error(self.read(identifier), 503, 'upload_unavailable')

    def test_size_mismatch_rejected(self):
        identifier = self.image()
        self.project(identifier)
        (self.root / str(identifier)).write_bytes(b'changed')
        self.error(self.read(identifier), 503, 'upload_unavailable')

    def test_authorization_and_metadata_share_snapshot_during_committed_replacement(self):
        old, new = self.image(), self.image()
        project_id = self.project(old)
        authorize = self.publication.is_public_reference
        snapshots = []
        def concurrent_replace(conn, identifier):
            allowed = authorize(conn, identifier)
            snapshots.append(conn.execute('SHOW transaction_isolation').fetchone()[0])
            snapshots.append(conn.execute('SHOW transaction_read_only').fetchone()[0])
            with database.transaction(self.settings) as writer:
                writer.execute('UPDATE projects SET cover_file_id=%s WHERE id=%s', (new, project_id))
                writer.execute('DELETE FROM uploaded_files WHERE id=%s', (old,))
            return allowed
        with patch.object(self.routes, 'is_public_reference', side_effect=concurrent_replace):
            self.allowed(old)
        self.assertEqual(snapshots, ['repeatable read', 'on'])
        self.error(self.read(old))
        self.allowed(new)

    def test_database_outage_returns_safe_error(self):
        with patch.object(self.routes, 'transaction', side_effect=database.DatabaseUnavailable('private connection details')):
            response = self.read(uuid4())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private connection details', response.text)
