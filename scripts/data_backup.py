"""Explicit stopped-writer backup and isolated restore rehearsal (never production restore).

Run with backend/.venv/bin/python. All configuration comes from backend Settings.
A replica is a byte-checked second path; it does not prove off-site isolation.
The caller owns stopping *all* writers and preserving backups/restore failures.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from uuid import UUID, uuid4

# Explicit repository path; never import an unrelated cwd's app package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import psycopg
from psycopg import sql
from app import database
from app.migrate import _load_migrations, MIGRATIONS
from app.settings import get_settings


class BackupError(RuntimeError):
    """Safe operator-facing summary, never includes driver/credential output."""


def require(condition, message):
    if not condition:
        raise BackupError(message)


def checked_path(value):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'Paths must be absolute without traversal')
    path = Path('/', *path.parts[1:])
    for ancestor in reversed((path, *path.parents)):
        if ancestor.exists() or ancestor.is_symlink():
            require(not ancestor.is_symlink(), 'Symbolic link paths are forbidden')
    return path


def private(path, directory=False):
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600)
            and (directory or info.st_nlink == 1), 'Private owned directory/file permissions required')


def directory(value, create=False):
    path = checked_path(value)
    if create and not path.exists():
        # Parent must exist; never recursively manufacture an operator's path.
        path.mkdir(mode=0o700)
    private(path, True)
    return path


def disjoint(*paths):
    require(all(not (a.is_relative_to(b) or b.is_relative_to(a))
                for i, a in enumerate(paths) for b in paths[i + 1:]), 'Storage paths must not overlap')


def digest(path):
    private(path)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def valid_key(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def uploads_inventory(path):
    result = {}
    for item in sorted(path.iterdir()):
        require(valid_key(item.name), 'Upload filename must be a canonical UUID')
        result[item.name] = {'sha256': digest(item), 'size': item.stat().st_size}
    return result


def pg_binaries(value):
    path = checked_path(value)
    require(path.is_dir(), 'PostgreSQL binary directory is invalid')
    for name in ('pg_dump', 'pg_restore'):
        executable = path / name
        info = executable.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid in (0, os.geteuid())
                and not info.st_mode & 0o022 and os.access(executable, os.X_OK), 'Unsafe PostgreSQL executable')
    return path


@contextmanager
def release_lock(value, inherited=None):
    path = checked_path(value)
    owned = None
    try:
        if inherited is None:
            owned = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            private(path)
            fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            private(path)
            info, expected = os.fstat(inherited), path.stat()
            require((info.st_dev, info.st_ino) == (expected.st_dev, expected.st_ino), 'Inherited lock identity mismatch')
            # An independent shared-lock probe must fail: an exclusive lock is held.
            with path.open('rb') as probe:
                try:
                    fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise BackupError('Inherited descriptor does not hold an exclusive lock')
            # Only the descriptor owning that exclusive lock can reacquire it.
            fcntl.flock(inherited, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise BackupError('Release lock is busy or inherited descriptor is not its owner') from None
    finally:
        if owned is not None:
            os.close(owned)


def target(restore=False):
    # This standalone process deliberately removes hidden libpq overrides before
    # Settings/driver use. Nothing can redirect the command away from DB_*.
    for name in list(os.environ):
        if name.startswith('PG'):
            os.environ.pop(name)
    settings = get_settings()
    require(settings.app_env in (('test',) if restore else ('test', 'production')), 'Explicit production or isolated test environment required')
    if settings.app_env == 'test':
        database.validate_test_target(settings)
    else:
        require((settings.db_name, settings.db_user) == ('personal_web_prod', 'personal_web_prod'), 'Exact production database/account required')
    return settings


def identity(conn, settings):
    row = conn.execute('SELECT current_database(), current_user, pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()').fetchone()
    require(row[:2] == (settings.db_name, settings.db_user), 'Connected database/account identity mismatch')
    if settings.app_env == 'test':
        require(row[2] == settings.db_user, 'Test database must be owned by the dedicated test account')


def schema_history(conn):
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        require(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0] == 0,
                'Unversioned application tables cannot be backed up safely')
        return []
    history = conn.execute('SELECT version,checksum FROM public.schema_migrations ORDER BY version').fetchall()
    expected = [(item.version, item.checksum) for item in _load_migrations(MIGRATIONS)]
    require(history == expected[:len(history)], 'Schema migration history does not match this revision')
    return [{'version': version, 'sha256': checksum} for version, checksum in history]


def content_digest(conn):
    # Hash actual values (including all table data) without putting sensitive rows
    # or visitor/session details in the manifest. Sort serialized rows, preserving duplicates.
    result = hashlib.sha256()
    tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    for (name,) in tables:
        result.update(name.encode() + b'\x00')
        with conn.cursor() as cursor:
            cursor.execute(sql.SQL('SELECT to_jsonb(t)::text FROM public.{} AS t ORDER BY to_jsonb(t)::text').format(sql.Identifier(name)))
            for (row,) in cursor:
                data = row.encode()
                result.update(str(len(data)).encode() + b':' + data)
    # Identity sequence values also survive the restore, including unused sequence gaps.
    for (name,) in conn.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename").fetchall():
        row = conn.execute(sql.SQL('SELECT last_value,is_called FROM public.{}').format(sql.Identifier(name))).fetchone()
        result.update(json.dumps([name, *row], separators=(',', ':')).encode())
    return result.hexdigest()


def check_image_metadata(conn, inventory, uploads):
    from PIL import Image
    if conn.execute("SELECT to_regclass('public.uploaded_files')").fetchone()[0] is None:
        require(not inventory, 'Unversioned database cannot establish image references')
        return
    rows = conn.execute('SELECT id,storage_key,media_type,byte_size,width,height FROM public.uploaded_files').fetchall()
    for identifier, key, media, size, width, height in rows:
        require(key == str(identifier) and key in inventory and inventory[key]['size'] == size,
                'Database image reference or byte size does not match uploads')
        with Image.open(uploads / key) as image:
            image.load()
            require(image.size == (width, height) and Image.MIME.get(image.format) == media,
                    'Image metadata does not match actual image bytes')
    # Every relationship is enforced during pg_restore, and all metadata images
    # are read/decoded above; unreferenced on-disk orphan bytes are also preserved.


@contextmanager
def credential_environment(settings):
    with tempfile.TemporaryDirectory(prefix='personal-web-pgpass-') as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        password = settings.db_password.get_secret_value()
        require('\n' not in password and '\r' not in password, 'Database password cannot contain line breaks for pgpass')
        escape = lambda value: str(value).replace('\\', '\\\\').replace(':', '\\:')
        pgpass = root / 'pgpass'
        fd = os.open(pgpass, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(':'.join(escape(v) for v in (settings.db_host, settings.db_port, settings.db_name, settings.db_user, password)) + '\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        env.update(PGPASSFILE=str(pgpass), PGCONNECT_TIMEOUT='5', PGOPTIONS='-c search_path=public,pg_catalog -c timezone=UTC')
        yield env


def pg_run(binary, settings, arguments):
    with credential_environment(settings) as env:
        completed = subprocess.run([str(binary), '--host', settings.db_host, '--port', str(settings.db_port),
                                    '--username', settings.db_user, '--no-password', *arguments], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    require(completed.returncode == 0, 'PostgreSQL backup/restore command failed; driver output suppressed')


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def hex_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def verify(value):
    group = directory(value)
    require({p.name for p in group.iterdir()} == {'manifest.json', 'database.dump', 'uploads.tar'}, 'Backup group is incomplete or contains unexpected files')
    for file in group.iterdir():
        private(file)
    manifest = json.loads((group / 'manifest.json').read_text())
    require(isinstance(manifest, dict) and set(manifest) == {'version','created_at','revision','database','user','schema','files','images','content_sha256'}, 'Invalid backup manifest fields')
    require(type(manifest['version']) is int and manifest['version'] == 1
            and re.fullmatch('[0-9a-f]{40}', manifest['revision']) is not None, 'Invalid backup format or revision')
    require(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z', manifest['created_at']) is not None, 'Invalid UTC backup timestamp')
    datetime.strptime(manifest['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
    require((manifest['database'], manifest['user']) == ('personal_web_prod','personal_web_prod')
            or (re.fullmatch('personal_web_test_[A-Za-z0-9_]+', manifest['database']) and manifest['user'] == 'personal_web_test'), 'Invalid backup database identity')
    expected = [{'version': item.version, 'sha256': item.checksum} for item in _load_migrations(MIGRATIONS)]
    require(isinstance(manifest['schema'], list) and manifest['schema'] == expected[:len(manifest['schema'])]
            and hex_digest(manifest['content_sha256']), 'Backup schema or content digest is invalid')
    require(isinstance(manifest['files'], dict) and set(manifest['files']) == {'database.dump','uploads.tar'}, 'Invalid backup file inventory')
    for name, checksum in manifest['files'].items():
        require(hex_digest(checksum) and digest(group / name) == checksum, 'Backup file checksum mismatch')
    with (group / 'database.dump').open('rb') as dump:
        require(dump.read(5) == b'PGDMP', 'Database backup must be a PostgreSQL custom archive')
    images = manifest['images']
    require(isinstance(images, dict) and set(images) == {'count','files'} and isinstance(images['files'], dict)
            and type(images['count']) is int and images['count'] == len(images['files']), 'Invalid image inventory')
    for key, info in images['files'].items():
        require(valid_key(key) and isinstance(info, dict) and set(info) == {'size','sha256'}
                and type(info['size']) is int and info['size'] > 0 and hex_digest(info['sha256']), 'Invalid image file metadata')
    seen = set()
    with tarfile.open(group / 'uploads.tar', 'r:') as archive:
        for member in archive:
            require(member.isfile() and valid_key(member.name) and member.name not in seen
                    and member.name in images['files'] and member.mode == 0o600
                    and not member.linkname and not member.pax_headers, 'Unsafe or unexpected upload archive member')
            seen.add(member.name)
            info = images['files'][member.name]
            require(member.size == info['size'], 'Upload archive byte size mismatch')
            with archive.extractfile(member) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256'], 'Upload archive image checksum mismatch')
    require(seen == set(images['files']), 'Upload archive image set mismatch')
    return manifest


def create(args):
    require(args.execute and args.writers_stopped, 'create requires --execute and --writers-stopped')
    require(re.fullmatch('[0-9a-f]{40}', args.revision) is not None, 'Revision must be a full lowercase commit SHA')
    settings = target()
    pg_bin = pg_binaries(args.pg_bin)
    uploads = directory(args.uploads_dir)
    backup, replica = checked_path(args.backup_root), checked_path(args.replica_root)
    disjoint(uploads, backup, replica)
    # Validate all upload paths before creating any backup group.
    inventory = uploads_inventory(uploads)
    with release_lock(args.lock_file, args.lock_fd):
        with database.connection(settings) as conn:
            identity(conn, settings)
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                conn.execute("SET LOCAL timezone='UTC'")
                history = schema_history(conn)
                check_image_metadata(conn, inventory, uploads)
                content = content_digest(conn)
                snapshot = conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
                backup, replica = directory(backup, True), directory(replica, True)
                stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                name = stamp.replace(':','').replace('.','') + '-' + args.revision[:12] + '-' + uuid4().hex[:12]
                # Hidden staging directories are never reported as valid backup groups.
                with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=backup) as temporary:
                    stage = Path(temporary)
                    dump = stage / 'database.dump'
                    write_private(dump, b'')
                    pg_run(pg_bin / 'pg_dump', settings, ['--format=custom', '--snapshot', snapshot, '--file', str(dump), '--dbname', settings.db_name])
                    archive_path = stage / 'uploads.tar'
                    write_private(archive_path, b'')
                    with tarfile.open(archive_path, 'w', format=tarfile.USTAR_FORMAT) as archive:
                        for key in inventory:
                            private(uploads / key)
                            with (uploads / key).open('rb') as stream:
                                info = tarfile.TarInfo(key)
                                info.size, info.mode = inventory[key]['size'], 0o600
                                archive.addfile(info, stream)
                    require(uploads_inventory(uploads) == inventory, 'Uploads changed during the stopped-writer window')
                    manifest = dict(version=1, created_at=stamp, revision=args.revision, database=settings.db_name,
                                    user=settings.db_user, schema=history, content_sha256=content,
                                    files={p: digest(stage / p) for p in ('database.dump','uploads.tar')},
                                    images={'count':len(inventory),'files':inventory})
                    write_private(stage / 'manifest.json', (json.dumps(manifest, sort_keys=True) + '\n').encode())
                    verify(stage)
                    with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=replica) as copy_temporary:
                        copied = Path(copy_temporary)
                        for file in stage.iterdir():
                            # Stream potentially large database dumps instead of reading
                            # the entire backup into the deploy process's memory.
                            fd = os.open(copied / file.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                            with file.open('rb') as source, os.fdopen(fd, 'wb') as output:
                                shutil.copyfileobj(source, output, length=1024 * 1024)
                                output.flush()
                                os.fsync(output.fileno())
                        require(verify(copied) == manifest, 'Replica verification mismatch')
                        for file in stage.iterdir():
                            require(digest(file) == digest(copied / file.name), 'Replica byte comparison failed')
                        # Atomically publish only verified groups. Failure can leave a valid
                        # unreported replica; never delete backups in an error handler.
                        copied.rename(replica / name)
                    stage.rename(backup / name)
    return {'backup':str(backup / name)}


def require_empty_restore_target(conn):
    # pg_class alone misses standalone routines/types. All objects scoped to
    # public have a namespace dependency, including operators, text search
    # objects, domains and their constraints. A fresh public schema has none.
    occupied = conn.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_depend
            WHERE refclassid = 'pg_namespace'::regclass
              AND refobjid = 'public'::regnamespace
        ) OR EXISTS (
            SELECT 1 FROM pg_namespace
            WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'public')
              AND nspname NOT LIKE 'pg_toast%' AND nspname NOT LIKE 'pg_temp%'
        ) OR EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
        ) OR EXISTS (
            SELECT 1 FROM pg_extension
            WHERE extname <> 'plpgsql' OR extnamespace <> 'pg_catalog'::regnamespace
        ) OR EXISTS (
            -- PostgreSQL reserves OIDs below FirstNormalObjectId (16384)
            -- for bootstrap objects. User casts between pinned built-in types
            -- can have no pg_depend rows, so inspect their catalog directly.
            SELECT 1 FROM pg_cast WHERE oid >= 16384
        ) OR EXISTS (SELECT 1 FROM pg_proc WHERE oid >= 16384)
          OR EXISTS (SELECT 1 FROM pg_type WHERE oid >= 16384)
          OR EXISTS (SELECT 1 FROM pg_class WHERE oid >= 16384)
          OR EXISTS (SELECT 1 FROM pg_constraint WHERE oid >= 16384)
          OR EXISTS (SELECT 1 FROM pg_default_acl)
          OR EXISTS (SELECT 1 FROM pg_event_trigger)
          OR EXISTS (SELECT 1 FROM pg_foreign_data_wrapper)
          OR EXISTS (SELECT 1 FROM pg_foreign_server)
          OR EXISTS (SELECT 1 FROM pg_largeobject_metadata)
          OR EXISTS (SELECT 1 FROM pg_publication)
          OR EXISTS (SELECT 1 FROM pg_subscription)
          OR EXISTS (SELECT 1 FROM pg_transform)
          OR EXISTS (
              SELECT 1 FROM pg_language
              WHERE lanname NOT IN ('internal', 'c', 'sql', 'plpgsql')
          )
    """).fetchone()[0]
    require(not occupied, 'Restore requires an empty owned test database')


def restore_test(args):
    require(args.execute, 'restore-test requires --execute')
    settings = target(restore=True)
    pg_bin = pg_binaries(args.pg_bin)
    group = directory(args.backup)
    manifest = verify(group)
    uploads = checked_path(args.uploads_dir)
    disjoint(group, uploads)
    require(not uploads.exists(), 'Restore uploads directory must not already exist')
    directory(uploads.parent)
    started = time.monotonic()
    with database.connection(settings) as conn:
        identity(conn, settings)
        require_empty_restore_target(conn)
        uploads.mkdir(mode=0o700)
        # Transactional database restore rolls back SQL failures. Subsequent validation
        # failures preserve test DB/files for diagnosis; never auto-drop DBs or roles.
        pg_run(pg_bin / 'pg_restore', settings, ['--no-owner','--no-privileges','--exit-on-error','--single-transaction','--dbname',settings.db_name,str(group / 'database.dump')])
        with tarfile.open(group / 'uploads.tar', 'r:') as archive:
            for member in archive:
                with archive.extractfile(member) as stream:
                    write_private(uploads / member.name, stream.read())
        conn.execute("SET timezone='UTC'")
        require(schema_history(conn) == manifest['schema'], 'Restored schema history mismatch')
        require(content_digest(conn) == manifest['content_sha256'], 'Restored database content mismatch')
        inventory = uploads_inventory(uploads)
        require(inventory == manifest['images']['files'], 'Restored upload checksums mismatch')
        check_image_metadata(conn, inventory, uploads)
    return {'restored':True,'database':settings.db_name,'uploads':str(uploads),'elapsed_seconds':round(time.monotonic()-started,3)}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    create_command = commands.add_parser('create')
    for name in ('uploads-dir','backup-root','replica-root','revision','pg-bin','lock-file'):
        create_command.add_argument('--' + name, required=True)
    create_command.add_argument('--lock-fd', type=int)
    create_command.add_argument('--execute', action='store_true')
    create_command.add_argument('--writers-stopped', action='store_true')
    verify_command = commands.add_parser('verify')
    verify_command.add_argument('--backup', required=True)
    restore_command = commands.add_parser('restore-test')
    for name in ('backup','uploads-dir','pg-bin'):
        restore_command.add_argument('--' + name, required=True)
    restore_command.add_argument('--execute', action='store_true')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'create':
            output = create(args)
        elif args.command == 'verify':
            verify(args.backup)
            output = {'verified':True,'backup':str(checked_path(args.backup))}
        else:
            output = restore_test(args)
    except BackupError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (Exception, KeyboardInterrupt):
        # A failure must never leak validation inputs, SQL, passwords, or libpq text.
        print('Backup operation failed; no success reported. Existing backups retained.', file=sys.stderr)
        return 1
    print(json.dumps(output, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
