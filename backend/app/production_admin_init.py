"""Explicit production first administrator; read-only preflight unless --execute."""
from contextlib import nullcontext
import getpass
import json
import sys
from urllib.parse import urlsplit
import warnings

import psycopg

from app import database, migrate
from app.admin_init import _credential_hash
from app.production_migrate import snapshot
from app.production_ops import parser, release_lock, validate_target, verify_identity
from app.settings import get_settings


def _origins(settings):
    if not settings.admin_allowed_origins:
        raise ValueError('Trusted HTTPS administrator origins are required.')
    for origin in settings.admin_allowed_origins:
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or '*' in origin
                or origin != f'https://{parsed.netloc}'):
            raise ValueError('Exact trusted HTTPS administrator origins required.')
        _ = parsed.port


def run(settings, expected_database, expected_user, *, execute=False,
        lock_file=None, lock_fd=None, username=None, password=None):
    validate_target(settings, expected_database, expected_user)
    _origins(settings)
    if not execute and (lock_file is not None or lock_fd is not None or username is not None or password is not None):
        raise ValueError('Execution arguments require --execute.')
    migrations = migrate._load_migrations(migrate.MIGRATIONS)
    encoded = _credential_hash(username, password) if execute else None
    try:
        with release_lock(lock_file, lock_fd) if execute else nullcontext():
            with database.transaction(settings) as conn:
                if not execute:
                    conn.execute('SET TRANSACTION READ ONLY')
                verify_identity(conn, settings)
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SET LOCAL statement_timeout = '30s'")
                conn.execute('SELECT pg_advisory_xact_lock(%s)', (migrate.LOCK_ID,))
                state = snapshot(conn, settings, migrations)
                if state['pending']:
                    raise ValueError('Apply all migrations before administrator initialization.')
                # Verify actual essential business columns, not just history claims.
                conn.execute('SELECT id, username, password_hash, created_at, updated_at FROM public.admin_accounts LIMIT 0')
                initialized = conn.execute('SELECT EXISTS(SELECT 1 FROM public.admin_accounts)').fetchone()[0]
                if execute:
                    if initialized:
                        raise ValueError('Administrator already exists; initialization never overwrites it.')
                    conn.execute('INSERT INTO public.admin_accounts(id,username,password_hash) VALUES (1,%s,%s)', (username, encoded))
                    initialized = True
                return {'database': settings.db_name, 'user': settings.db_user,
                        'schema_ready': True, 'initialized': initialized}
    except psycopg.Error:
        raise ValueError('Administrator initialization failed; verify database schema and account state.') from None


def main(argv=None):
    try:
        args = parser(__doc__).parse_args(argv)
    except SystemExit as error:
        return error.code
    try:
        settings = get_settings()
        credentials = {}
        if args.execute:
            validate_target(settings, args.expect_database, args.expect_user)
            _origins(settings)
            if not sys.stdin.isatty() or not sys.stderr.isatty():
                raise ValueError('Interactive terminal required.')
            with open('/dev/tty', 'r') as terminal:
                if not terminal.isatty():
                    raise ValueError('Interactive terminal required.')
            username = input('Username: ')
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                password = getpass.getpass('Password (12–128 characters): ')
                repeated = getpass.getpass('Repeat password: ')
            if password != repeated:
                raise ValueError('Passwords do not match.')
            credentials = {'username': username, 'password': password}
        result = run(settings, args.expect_database, args.expect_user, execute=args.execute,
                     lock_file=args.lock_file, lock_fd=args.lock_fd, **credentials)
    except (ValueError, migrate.MigrationError, database.DatabaseTargetError,
            database.DatabaseUnavailable, OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print('Production administrator initialization refused or failed; check terminal, origins, target, lock and schema.', file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
