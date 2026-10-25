"""Explicit production initial real content; never copies a development database."""
from contextlib import nullcontext
import json
import sys
from app import content_bootstrap, database, migrate
from app.production_migrate import snapshot
from app.production_ops import parser, release_lock, validate_target, verify_identity
from app.settings import get_settings


def run(settings, expected_database, expected_user, *, execute=False, lock_file=None, lock_fd=None):
    validate_target(settings, expected_database, expected_user)
    if not execute and (lock_file is not None or lock_fd is not None):
        raise ValueError('Release lock arguments require --execute.')
    try:
        with release_lock(lock_file, lock_fd) if execute else nullcontext():
            if execute:
                identifier = content_bootstrap._bootstrap(settings, require_current_schema=True)
                return {'database':settings.db_name, 'user':settings.db_user,
                        'initialized':True, 'project_id':identifier}
            with database.transaction(settings) as conn:
                conn.execute('SET TRANSACTION READ ONLY')
                verify_identity(conn,settings)
                conn.execute("SET LOCAL lock_timeout='5s'")
                conn.execute('SELECT pg_advisory_xact_lock(%s)', (migrate.LOCK_ID,))
                state=snapshot(conn,settings,migrate._load_migrations(migrate.MIGRATIONS))
                if state['pending']:
                    raise ValueError('Apply all migrations before content initialization.')
                row=conn.execute('SELECT project_id FROM content_bootstraps WHERE key=%s',(content_bootstrap.KEY,)).fetchone()
                return {'database':settings.db_name, 'user':settings.db_user,
                        'initialized':row is not None, 'project_id':row[0] if row else None}
    except (content_bootstrap.BootstrapError,migrate.MigrationError):
        raise ValueError('Content initialization refused; check schema and existing content.') from None


def main(argv=None):
    try:
        args=parser(__doc__).parse_args(argv)
    except SystemExit as error:
        return error.code
    try:
        result=run(get_settings(),args.expect_database,args.expect_user,execute=args.execute,
                   lock_file=args.lock_file,lock_fd=args.lock_fd)
    except Exception:
        print('Production content initialization refused or failed; existing content retained.',file=sys.stderr)
        return 1
    print(json.dumps(result,separators=(',',':')))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
