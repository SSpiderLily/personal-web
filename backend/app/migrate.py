"""Explicit migration command: cd backend && uv run --locked python -m app.migrate.

SQL files are immutable, ordered NNN_name.sql files with no transaction-control
statements. All pending versions and history updates commit together. This uses
the existing psql history table and advisory lock. No automatic startup migration,
production execution, seed data, repair of manual drift or down migrations.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sys

import psycopg

from app import database
from app.settings import get_settings

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'
LOCK_ID = 794675013001


class MigrationError(RuntimeError):
    """Unsafe target, invalid history/file set, or failed atomic migration."""


@dataclass(frozen=True)
class Migration:
    version: str
    checksum: str
    sql: str


def _load_migrations(directory: Path) -> list[Migration]:
    migrations = []
    prefixes = set()
    for path in sorted(directory.glob('[0-9]*.sql')):
        if not re.fullmatch(r'[0-9]{3}_[a-z][a-z0-9_]*', path.stem):
            raise MigrationError('Migration filenames must use NNN_name.sql')
        prefix = path.stem.split('_', 1)[0]
        if prefix in prefixes:
            raise MigrationError('Duplicate migration number; refusing changes')
        prefixes.add(prefix)
        content = path.read_bytes()
        migrations.append(Migration(path.stem, hashlib.sha256(content).hexdigest(), content.decode('utf-8')))
    if not migrations:
        raise MigrationError('No versioned migrations found; refusing changes')
    return migrations


def apply_migrations(directory: Path = MIGRATIONS) -> list[str]:
    """Apply all pending versions; return applied names, [] for a verified no-op."""
    settings = get_settings()
    if settings.app_env == 'production':
        raise MigrationError('Production migrations are disabled until deployment integration')
    if settings.app_env == 'development' and (settings.db_name, settings.db_user) != ('personal_web_dev', 'personal_web_dev'):
        raise MigrationError('Development database/account required; refusing migration')
    migrations = _load_migrations(Path(directory))
    applied = []
    try:
        with database.transaction(settings) as conn:
            identity = conn.execute('SELECT current_database(), current_user').fetchone()
            if identity != (settings.db_name, settings.db_user):
                raise MigrationError('Database identity does not match Settings; refusing migration')
            conn.execute("SET LOCAL lock_timeout = '5s'")
            conn.execute("SET LOCAL statement_timeout = '30s'")
            conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
            conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
                version varchar(100) PRIMARY KEY,
                checksum varchar(64) NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
                applied_at timestamptz NOT NULL DEFAULT now()
            )''')
            history = conn.execute('SELECT version, checksum FROM schema_migrations ORDER BY version').fetchall()
            expected = [(migration.version, migration.checksum) for migration in migrations]
            if history != expected[:len(history)]:
                raise MigrationError('Migration version/checksum history mismatch; refusing changes')
            for migration in migrations[len(history):]:
                conn.execute(migration.sql)
                conn.execute('INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)',
                             (migration.version, migration.checksum))
                applied.append(migration.version)
    except psycopg.Error:
        raise MigrationError('Migration failed; all pending changes rolled back') from None
    return applied


def main() -> int:
    try:
        applied = apply_migrations()
    except (MigrationError, database.DatabaseTargetError, database.DatabaseUnavailable) as error:
        print(str(error), file=sys.stderr)
        return 1
    print('Applied: ' + ', '.join(applied) if applied else 'All migrations already applied; no changes.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
