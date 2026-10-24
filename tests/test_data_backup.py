"""Real backup/restore tests; owns a private Unix-only PostgreSQL cluster."""
from contextlib import ExitStack
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/data_backup.py'
PYTHON = ROOT / 'backend/.venv/bin/python'
# Both Linux CI and the local macOS installation are supported.
_candidates = ([Path(os.environ['APP_TEST_PG_BIN'])] if os.environ.get('APP_TEST_PG_BIN') else
               [Path(shutil.which('initdb')).parent] if shutil.which('initdb') else
               [Path('/Library/PostgreSQL/17/bin'), *sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True)])
PG = next((p for p in _candidates if all((p / n).is_file() for n in ('initdb','pg_ctl','psql','pg_dump','pg_restore'))), _candidates[0])
RED_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAEUlEQVR4nGP8zwACTGASRgEAFEABBVDVLjgAAAAASUVORK5CYII=')
BLUE_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGNkYPjPwMDAxAAGUAoAEkIBBYa3P50AAAAASUVORK5CYII=')


class DataBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PG / 'initdb').is_file():
            if os.environ.get('PW_REQUIRE_RECOVERY_TESTS') == '1':
                raise RuntimeError('Recovery tests require owned PostgreSQL binaries')
            raise unittest.SkipTest('owned PostgreSQL binaries unavailable')
        if not PYTHON.is_file():
            raise RuntimeError('Install independent backend dependencies before recovery tests')
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.cluster = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix='pwbackup-', dir='/private/tmp')))
        cls.socket = cls.cluster / 'socket'
        cls.socket.mkdir(mode=0o700)
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith(('PG', 'DB_', 'APP_'))}
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            cls.port = probe.getsockname()[1]
        cls.pg('initdb', '-D', str(cls.cluster / 'data'), '-U', 'personal_web_test', '--auth=trust', '--encoding=UTF8', '--no-locale')
        cls.stack.callback(cls.pg, 'pg_ctl', '-D', str(cls.cluster / 'data'), '-m', 'immediate', '-w', 'stop')
        cls.pg('pg_ctl', '-D', str(cls.cluster / 'data'), '-l', str(cls.cluster / 'pg.log'), '-w', 'start', '-o',
               f"-k {cls.socket} -p {cls.port} -c listen_addresses='' -c fsync=off")
        cls.env.update(APP_ENV='test', DB_HOST=str(cls.socket), DB_PORT=str(cls.port), DB_USER='personal_web_test', DB_PASSWORD='')

    @classmethod
    def pg(cls, name, *args):
        result = subprocess.run([str(PG / name), *args], env=cls.env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Owned test cluster command failed: ' + name)
        return result.stdout

    def sql(self, sql, db=None):
        return self.pg('psql', '-X', '-h', str(self.socket), '-p', str(self.port), '-U', 'personal_web_test', '-d', db or self.db,
                       '-v', 'ON_ERROR_STOP=1', '-Atc', sql)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pwbackup-case-', dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = 'personal_web_test_' + uuid.uuid4().hex
        self.sql('CREATE DATABASE ' + self.db, 'postgres')
        self.env = dict(type(self).env, DB_NAME=self.db)
        self.uploads = self.root / 'uploads'
        self.uploads.mkdir(mode=0o700)
        self.key = str(uuid.uuid4())
        # A real readable PNG; metadata references this exact byte stream.
        self.image = RED_PNG
        (self.uploads / self.key).write_bytes(self.image)
        (self.uploads / self.key).chmod(0o600)
        migration = subprocess.run([str(PYTHON), '-m', 'app.migrate'], cwd=ROOT / 'backend', env=self.env, capture_output=True)
        self.assertEqual(migration.returncode, 0, migration.stderr)
        self.sql(f"INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height) VALUES ('{self.key}','{self.key}','image.png','image/png',{len(self.image)},2,3); INSERT INTO projects(name,cover_file_id) VALUES ('preserve content','{self.key}')")
        self.args = ['create', '--uploads-dir', str(self.uploads), '--backup-root', str(self.root / 'backups'),
                     '--replica-root', str(self.root / 'replica'), '--revision', 'a' * 40, '--pg-bin', str(PG),
                     '--lock-file', str(self.root / 'deploy.lock'), '--execute', '--writers-stopped']

    def cli(self, args, *, env=None, pass_fds=()):
        return subprocess.run([str(PYTHON), str(SCRIPT), *args], env=env or self.env, capture_output=True, text=True, pass_fds=pass_fds)

    def create(self):
        result = self.cli(self.args)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {'backup'})
        return Path(payload['backup'])

    def restore_args(self, group):
        target = 'personal_web_test_' + uuid.uuid4().hex
        self.sql('CREATE DATABASE ' + target, 'postgres')
        return ['restore-test', '--backup', str(group), '--uploads-dir', str(self.root / 'restored'), '--pg-bin', str(PG), '--execute'], dict(self.env, DB_NAME=target)

    def test_real_dump_replica_restore_content_permissions_and_metadata(self):
        group = self.create()
        self.assertEqual({p.name for p in group.iterdir()}, {'manifest.json', 'database.dump', 'uploads.tar'})
        manifest = json.loads((group / 'manifest.json').read_text())
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(manifest['revision'], 'a' * 40)
        self.assertEqual(manifest['images']['count'], 1)
        self.assertEqual(manifest['images']['files'][self.key]['sha256'], hashlib.sha256(self.image).hexdigest())
        replica = self.root / 'replica' / group.name
        for file in group.iterdir():
            self.assertEqual(file.read_bytes(), (replica / file.name).read_bytes())
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(group.stat().st_mode & 0o777, 0o700)
        checked = self.cli(['verify', '--backup', str(group)])
        self.assertEqual(checked.returncode, 0, checked.stderr)
        args, env = self.restore_args(group)
        restored = self.cli(args, env=env)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)['restored'], True)
        self.assertEqual(self.sql('SELECT name FROM projects', env['DB_NAME']).strip(), 'preserve content')
        self.assertEqual((self.root / 'restored' / self.key).read_bytes(), self.image)
        self.assertEqual((self.root / 'restored' / self.key).stat().st_mode & 0o777, 0o600)

    def test_missing_execute_or_stop_confirmation_never_creates_backup(self):
        for flag in ('--execute', '--writers-stopped'):
            with self.subTest(flag=flag):
                result = self.cli([arg for arg in self.args if arg != flag])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'backups').exists())

    def test_development_remote_test_and_shared_ports_rejected_without_output_leaks(self):
        for override in ({'APP_ENV': 'development'}, {'DB_PORT': '5432'}, {'DB_PORT': '15432'}, {'DB_HOST': 'remote.invalid'}, {'DB_NAME': 'personal_web_dev'}):
            with self.subTest(override=override):
                result = self.cli(self.args, env=dict(self.env, **override, DB_PASSWORD='do-not-print-me'))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('do-not-print-me', result.stdout + result.stderr)
                self.assertFalse((self.root / 'backups').exists())

    def test_hidden_pg_environment_cannot_redirect_dump(self):
        result = self.cli(self.args, env=dict(self.env, PGSERVICE='invalid', PGHOST='invalid', PGPASSWORD='do-not-print-me'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('do-not-print-me', result.stdout + result.stderr)

    def test_busy_unheld_and_wrong_inherited_lock_rejected(self):
        path = self.root / 'deploy.lock'
        with path.open('w') as lock:
            path.chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self.cli(self.args).returncode, 0)
            other = self.root / 'other.lock'
            with other.open('w') as different:
                other.chmod(0o600)
                result = self.cli(self.args + ['--lock-fd', str(different.fileno())], pass_fds=(different.fileno(),))
                self.assertNotEqual(result.returncode, 0)
            fcntl.flock(lock, fcntl.LOCK_UN)
            result = self.cli(self.args + ['--lock-fd', str(lock.fileno())], pass_fds=(lock.fileno(),))
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'backups').exists())

    def test_valid_inherited_lock_remains_held_by_caller(self):
        path = self.root / 'deploy.lock'
        with path.open('w') as lock:
            path.chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli(self.args + ['--lock-fd', str(lock.fileno())], pass_fds=(lock.fileno(),))
            self.assertEqual(result.returncode, 0, result.stderr)
            with path.open('r') as contender:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_overlapping_paths_symlinks_and_unsafe_upload_permissions_rejected(self):
        for option, value in (('--replica-root', str(self.uploads / 'inside')), ('--backup-root', str(self.uploads))):
            args = self.args.copy()
            args[args.index(option) + 1] = value
            self.assertNotEqual(self.cli(args).returncode, 0)
        (self.uploads / 'link').symlink_to(self.uploads / self.key)
        self.assertNotEqual(self.cli(self.args).returncode, 0)
        (self.uploads / 'link').unlink()
        (self.uploads / self.key).chmod(0o644)
        self.assertNotEqual(self.cli(self.args).returncode, 0)

    def test_corruption_incomplete_group_cross_group_archive_and_bad_manifest_rejected(self):
        group = self.create()
        for filename in ('database.dump', 'uploads.tar', 'manifest.json'):
            original = (group / filename).read_bytes()
            (group / filename).write_bytes(original + b'corruption')
            self.assertNotEqual(self.cli(['verify', '--backup', str(group)]).returncode, 0)
            (group / filename).write_bytes(original)
        (group / 'database.dump').unlink()
        self.assertNotEqual(self.cli(['verify', '--backup', str(group)]).returncode, 0)

    def test_malicious_tar_even_with_updated_checksum_is_rejected(self):
        group = self.create()
        for name, kind in (('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), (self.key, tarfile.SYMTYPE)):
            with self.subTest(name=name, kind=kind):
                with tarfile.open(group / 'uploads.tar', 'w') as archive:
                    item = tarfile.TarInfo(name)
                    item.type = kind
                    item.mode = 0o600
                    item.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
                    archive.addfile(item)
                manifest = json.loads((group / 'manifest.json').read_text())
                manifest['files']['uploads.tar'] = hashlib.sha256((group / 'uploads.tar').read_bytes()).hexdigest()
                (group / 'manifest.json').write_text(json.dumps(manifest))
                self.assertNotEqual(self.cli(['verify', '--backup', str(group)]).returncode, 0)

    def test_restore_rejects_nonempty_database_existing_uploads_and_production(self):
        group = self.create()
        args, env = self.restore_args(group)
        self.sql('CREATE TABLE sentinel(id int)', env['DB_NAME'])
        self.assertNotEqual(self.cli(args, env=env).returncode, 0)
        self.assertFalse((self.root / 'restored').exists())
        args, env = self.restore_args(group)
        (self.root / 'restored').mkdir(mode=0o700)
        self.assertNotEqual(self.cli(args, env=env).returncode, 0)
        self.assertNotEqual(self.cli(args, env=dict(env, APP_ENV='production')).returncode, 0)

    def test_missing_image_metadata_and_failed_second_copy_preserve_old_group(self):
        group = self.create()
        (self.uploads / self.key).unlink()
        self.assertNotEqual(self.cli(self.args).returncode, 0)
        self.assertEqual(self.cli(['verify', '--backup', str(group)]).returncode, 0)
        (self.uploads / self.key).write_bytes(self.image)
        (self.uploads / self.key).chmod(0o600)
        broken = self.root / 'broken-replica'
        broken.write_text('not a directory')
        args = self.args.copy()
        args[args.index('--replica-root') + 1] = str(broken)
        self.assertNotEqual(self.cli(args).returncode, 0)
        self.assertEqual(self.cli(['verify', '--backup', str(group)]).returncode, 0)

    def test_revision_and_pg_binary_validation_precedes_any_backup(self):
        for option, value in (('--revision', 'bad'), ('--pg-bin', str(self.uploads))):
            args = self.args.copy()
            args[args.index(option) + 1] = value
            self.assertNotEqual(self.cli(args).returncode, 0)
            self.assertFalse((self.root / 'backups').exists())

    def test_empty_initial_database_backup_and_restore(self):
        empty = 'personal_web_test_' + uuid.uuid4().hex
        self.sql('CREATE DATABASE ' + empty, 'postgres')
        for item in self.uploads.iterdir():
            item.unlink()
        result = self.cli(self.args, env=dict(self.env, DB_NAME=empty))
        self.assertEqual(result.returncode, 0, result.stderr)
        group = Path(json.loads(result.stdout)['backup'])
        self.assertEqual(json.loads((group / 'manifest.json').read_text())['schema'], [])
        args, env = self.restore_args(group)
        result = self.cli(args, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pre_migration_applied_prefix_is_backed_up_without_applying_pending(self):
        # Use a faithful prefix, rather than mutating immutable checked-in SQL.
        self.sql("DELETE FROM schema_migrations WHERE version != '001_admin_schema'")
        result = self.cli(self.args)
        self.assertEqual(result.returncode, 0, result.stderr)
        group = Path(json.loads(result.stdout)['backup'])
        manifest = json.loads((group / 'manifest.json').read_text())
        self.assertEqual([row['version'] for row in manifest['schema']], ['001_admin_schema'])
        self.assertEqual(self.sql('SELECT count(*) FROM schema_migrations').strip(), '1')
        args, env = self.restore_args(group)
        result = self.cli(args, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_schema_history_drift_is_rejected(self):
        self.sql("UPDATE schema_migrations SET checksum=repeat('f',64) WHERE version='001_admin_schema'")
        self.assertNotEqual(self.cli(self.args).returncode, 0)
        self.assertFalse((self.root / 'backups').exists())

    def test_cross_group_upload_mix_and_duplicate_members_rejected(self):
        first = self.create()
        changed = BLUE_PNG
        (self.uploads / self.key).write_bytes(changed)
        self.sql(f"UPDATE uploaded_files SET byte_size={len(changed)}")
        second = self.create()
        (first / 'uploads.tar').write_bytes((second / 'uploads.tar').read_bytes())
        manifest = json.loads((first / 'manifest.json').read_text())
        manifest['files']['uploads.tar'] = hashlib.sha256((first / 'uploads.tar').read_bytes()).hexdigest()
        (first / 'manifest.json').write_text(json.dumps(manifest))
        self.assertNotEqual(self.cli(['verify','--backup',str(first)]).returncode, 0)
        with tarfile.open(second / 'uploads.tar', 'a') as archive:
            item = tarfile.TarInfo(self.key)
            item.mode, item.size = 0o600, len(changed)
            archive.addfile(item, io.BytesIO(changed))
        manifest = json.loads((second / 'manifest.json').read_text())
        manifest['files']['uploads.tar'] = hashlib.sha256((second / 'uploads.tar').read_bytes()).hexdigest()
        (second / 'manifest.json').write_text(json.dumps(manifest))
        self.assertNotEqual(self.cli(['verify','--backup',str(second)]).returncode, 0)

    def test_restore_content_digest_and_image_metadata_checked(self):
        group = self.create()
        manifest = json.loads((group / 'manifest.json').read_text())
        manifest['content_sha256'] = '0' * 64
        (group / 'manifest.json').write_text(json.dumps(manifest))
        args, env = self.restore_args(group)
        result = self.cli(args, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('content mismatch', result.stderr)
        # Rehearsal failure never drops roles/databases; retain evidence for diagnosis.
        self.assertEqual(self.sql('SELECT count(*) FROM projects', env['DB_NAME']).strip(), '1')

    def test_verify_is_readonly_and_does_not_need_database_configuration(self):
        group = self.create()
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in group.iterdir()}
        result = self.cli(['verify','--backup',str(group)], env=dict(self.env, APP_ENV='production', DB_PASSWORD=''))
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in group.iterdir()}
        self.assertEqual(before, after)

    def test_other_account_owned_restore_database_rejected(self):
        group = self.create()
        args, env = self.restore_args(group)
        owner = 'backup_owner_' + uuid.uuid4().hex
        self.sql('CREATE ROLE ' + owner, 'postgres')
        self.sql('ALTER DATABASE ' + env['DB_NAME'] + ' OWNER TO ' + owner, 'postgres')
        self.assertNotEqual(self.cli(args, env=env).returncode, 0)
        self.assertFalse((self.root / 'restored').exists())

    def test_unlocked_fd_cannot_borrow_someone_elses_lock(self):
        path = self.root / 'deploy.lock'
        with path.open('w') as actual, path.open('r') as unrelated:
            path.chmod(0o600)
            fcntl.flock(actual, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli(self.args + ['--lock-fd',str(unrelated.fileno())], pass_fds=(unrelated.fileno(),))
            self.assertNotEqual(result.returncode, 0)


    def wrappers(self, dump_code):
        binaries = self.root / 'bin'
        binaries.mkdir(mode=0o700)
        for name in ('pg_dump','pg_restore'):
            file = binaries / name
            code = dump_code if name == 'pg_dump' else f"import os,sys; os.execv({str(PG / name)!r}, [{str(PG / name)!r}, *sys.argv[1:]])"
            file.write_text('#!' + str(PYTHON) + '\n' + code + '\n')
            file.chmod(0o700)
        args = self.args.copy()
        args[args.index('--pg-bin') + 1] = str(binaries)
        return args

    def test_pgpass_private_cleanup_and_credentials_not_in_argv_or_hidden_pg_config(self):
        audit = self.root / 'audit.json'
        code = f"""import json,os,sys,stat
from pathlib import Path
p=Path(os.environ['PGPASSFILE'])
audit={{'private':stat.S_IMODE(p.stat().st_mode)==0o600,'contains_password':'credential-sentinel' in p.read_text(),'argv_safe':all('credential-sentinel' not in a for a in sys.argv),'hidden_cleared':'PGSERVICE' not in os.environ,'pgpass_path':str(p)}}
Path({str(audit)!r}).write_text(json.dumps(audit))
os.execv({str(PG / 'pg_dump')!r}, [{str(PG / 'pg_dump')!r}, *sys.argv[1:]])"""
        args = self.wrappers(code)
        result = self.cli(args, env=dict(self.env, DB_PASSWORD='credential-sentinel', PGSERVICE='ignored'))
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(audit.read_text())
        self.assertTrue(all(observed[k] for k in ('private','contains_password','argv_safe','hidden_cleared')))
        self.assertFalse(Path(observed['pgpass_path']).exists())
        self.assertNotIn('credential-sentinel', result.stdout + result.stderr)

    def test_dump_failure_keeps_old_group_and_removes_incomplete_staging(self):
        group = self.create()
        args = self.wrappers("import sys; print('credential-sentinel',file=sys.stderr); sys.exit(1)")
        result = self.cli(args)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('credential-sentinel', result.stderr)
        self.assertEqual(list((self.root / 'backups').iterdir()), [group])
        self.assertEqual(self.cli(['verify','--backup',str(group)]).returncode, 0)

    def test_interrupt_cleans_incomplete_staging_and_pgpass(self):
        import signal
        import time
        group = self.create()
        marker = self.root / 'dump-started.json'
        code = f"""import json,os,time
from pathlib import Path
Path({str(marker)!r}).write_text(json.dumps({{'pid':os.getpid(),'pgpass':os.environ['PGPASSFILE']}}))
time.sleep(30)"""
        args = self.wrappers(code)
        process = subprocess.Popen([str(PYTHON),str(SCRIPT),*args], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if marker.exists():
                    break
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            observed = json.loads(marker.read_text())
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(stdout)
            self.assertFalse(Path(observed['pgpass']).exists())
            with self.assertRaises(ProcessLookupError):
                os.kill(observed['pid'], 0)
            self.assertEqual(list((self.root / 'backups').iterdir()), [group])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if marker.exists():
                try:
                    os.kill(json.loads(marker.read_text())['pid'], signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def test_truncated_dump_restore_rolls_back_without_dropping_test_database(self):
        group = self.create()
        dump = group / 'database.dump'
        dump.write_bytes(dump.read_bytes()[:-400])
        manifest = json.loads((group / 'manifest.json').read_text())
        manifest['files']['database.dump'] = hashlib.sha256(dump.read_bytes()).hexdigest()
        (group / 'manifest.json').write_text(json.dumps(manifest))
        args, env = self.restore_args(group)
        self.assertNotEqual(self.cli(args, env=env).returncode, 0)
        self.assertEqual(self.sql("SELECT count(*) FROM pg_tables WHERE schemaname='public'", env['DB_NAME']).strip(), '0')



if __name__ == '__main__':
    unittest.main()
