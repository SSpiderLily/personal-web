"""Synchronous psycopg connection scopes; importing this module performs no I/O.

Use transaction() for every business write/unit of work. One scope owns one
connection; normal exit commits, any exception rolls back, exit always closes.
Use connection() for independent read queries (autocommit, no shared snapshot).
Pass values as execute(sql, parameters), never interpolate user input into SQL.
"""
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
import re

import psycopg

from app.settings import Settings, get_settings


class DatabaseUnavailable(RuntimeError):
    """Connection could not be established; deliberately contains no driver text."""


class DatabaseTargetError(ValueError):
    """An automated test tried to use a shared or nonlocal database."""


def validate_test_target(settings: Settings) -> None:
    """Defense in depth; the test runner creates and owns the actual cluster."""
    if settings.app_env != 'test':
        return
    local = settings.db_host in ('127.0.0.1', '::1', 'localhost') or Path(settings.db_host).is_absolute()
    if (not local or settings.db_port in (5432, 15432)
            or not re.fullmatch(r'personal_web_test_[a-zA-Z0-9_]+', settings.db_name)
            or settings.db_user != 'personal_web_test'):
        raise DatabaseTargetError('Tests require an isolated local personal_web_test_* database and test role on a dedicated port')


@contextmanager
def connection(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    """Open a fresh autocommit connection from Settings; never retries/falls back."""
    settings = settings if settings is not None else get_settings()
    validate_test_target(settings)
    try:
        conn = psycopg.connect(host=settings.db_host, port=settings.db_port,
                               dbname=settings.db_name, user=settings.db_user,
                               password=settings.db_password.get_secret_value(),
                               connect_timeout=5, autocommit=True,
                               options='-c search_path=public,pg_catalog')
    except psycopg.Error:
        raise DatabaseUnavailable('Database connection failed; check the configured target and credentials') from None
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    """One atomic transaction, including deferred constraints at commit.

    Reuse the yielded connection in subfunctions; calling transaction() again
    opens an independent transaction. Do not commit()/rollback() inside a scope.
    """
    with connection(settings) as conn:
        with conn.transaction():
            yield conn
