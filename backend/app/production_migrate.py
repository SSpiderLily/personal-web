"""Explicit production migrations; default is a read-only JSON preflight."""
from contextlib import nullcontext
import json
from pathlib import Path
import sys

import psycopg

from app import database, migrate
from app.production_ops import parser, release_lock, validate_target, verify_identity
from app.settings import get_settings


def snapshot(conn, settings, migrations):
    history = migrate.migration_history(conn, migrations)
    return {'database': settings.db_name, 'user': settings.db_user,
            'applied': [row[0] for row in history],
            'pending': [migration.version for migration in migrations[len(history):]]}


def run(settings, expected_database, expected_user, *, execute=False,
        lock_file=None, lock_fd=None, directory=migrate.MIGRATIONS):
    validate_target(settings, expected_database, expected_user)
    if not execute and (lock_file is not None or lock_fd is not None):
        raise ValueError('Release lock arguments require --execute.')
    migrations = migrate._load_migrations(Path(directory))
    try:
        with release_lock(lock_file, lock_fd) if execute else nullcontext():
            with database.transaction(settings) as conn:
                if not execute:
                    conn.execute('SET TRANSACTION READ ONLY')
                verify_identity(conn, settings)
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SET LOCAL statement_timeout = '30s'")
                # Same lock as development migrations, also protects the snapshot.
                conn.execute('SELECT pg_advisory_xact_lock(%s)', (migrate.LOCK_ID,))
                if execute:
                    migrate._apply_on_connection(conn, migrations)
                return snapshot(conn, settings, migrations)
    except psycopg.Error:
        raise migrate.MigrationError('Migration failed; all pending changes rolled back.') from None


def main(argv=None):
    try:
        args = parser(__doc__).parse_args(argv)
    except SystemExit as error:
        return error.code
    try:
        result = run(get_settings(), args.expect_database, args.expect_user,
                     execute=args.execute, lock_file=args.lock_file, lock_fd=args.lock_fd)
    except (ValueError, migrate.MigrationError, database.DatabaseTargetError,
            database.DatabaseUnavailable, OSError):
        print('Production migration refused or failed; check target, release lock and migration history.', file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
