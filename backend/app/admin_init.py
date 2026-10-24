"""Terminal-only bootstrap: `uv run --locked python -m app.admin_init`.

No password flags or password environment variables are accepted. Production
bootstrap is deliberately unavailable in phase B pending production HTTPS and
an explicitly approved initialization procedure. No implicit migration occurs.
"""
import getpass
import sys
import warnings

import psycopg

from app.admin_auth import PASSWORDS
from app.database import DatabaseTargetError, DatabaseUnavailable, transaction
from app.settings import Settings, get_settings


class AdminAlreadyExists(RuntimeError):
    """The single account is already initialized; never replaces it."""


class AdminInitializationError(ValueError):
    """Safe bootstrap rejection, without credential input."""


def _credential_hash(username: str, password: str) -> str:
    if not isinstance(username, str) or not 1 <= len(username) <= 64 or username != username.strip():
        raise AdminInitializationError('Username must contain 1–64 characters without surrounding whitespace.')
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise AdminInitializationError('Password must contain 12–128 characters.')
    try:
        username.encode('utf-8')
        password.encode('utf-8')
    except UnicodeError:
        raise AdminInitializationError('Username and password contain unsupported characters.') from None
    if '\x00' in username or '\x00' in password:
        raise AdminInitializationError('Username and password contain unsupported characters.')
    encoded = PASSWORDS.hash(password)
    return encoded


def initialize_admin(settings: Settings, username: str, password: str) -> None:
    """Atomic single-admin insert. Database constraints arbitrate concurrent calls."""
    if settings.app_env == 'production':
        raise AdminInitializationError('Production initialization is unavailable in phase B; use a separately approved production procedure.')
    encoded = _credential_hash(username, password)
    try:
        with transaction(settings) as conn:
            conn.execute('INSERT INTO admin_accounts(id,username,password_hash) VALUES (1,%s,%s)', (username, encoded))
    except psycopg.errors.UniqueViolation:
        raise AdminAlreadyExists('Administrator already exists; initialization never overwrites an account.') from None


def main() -> int:
    if len(sys.argv) != 1:
        print('Use python -m app.admin_init without arguments. Passwords are accepted only at the terminal prompt.', file=sys.stderr)
        return 1
    try:
        settings = get_settings()
        if settings.app_env == 'production':
            raise AdminInitializationError('Production initialization is unavailable in phase B; use a separately approved production procedure.')
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise AdminInitializationError('Interactive terminal required; piped input is not accepted.')
        # getpass normally falls back to echoing stdin when /dev/tty is absent.
        # Verify the terminal first, and turn any later fallback warning into failure.
        with open('/dev/tty', 'r') as terminal:
            if not terminal.isatty():
                raise AdminInitializationError('Interactive terminal required.')
        print(f'Initialize one administrator: {settings.app_env}, {settings.db_name} at {settings.db_host}:{settings.db_port}')
        username = input('Username: ')
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Password (12–128 characters): ')
            repeated = getpass.getpass('Repeat password: ')
        if password != repeated:
            raise AdminInitializationError('Passwords do not match.')
        initialize_admin(settings, username, password)
        print('Administrator initialized.')
        return 0
    except AdminAlreadyExists as error:
        print(str(error), file=sys.stderr)
    except AdminInitializationError as error:
        print(str(error), file=sys.stderr)
    except (DatabaseUnavailable, DatabaseTargetError, psycopg.Error):
        print('Initialization failed: database unavailable; check configuration and migrations.', file=sys.stderr)
    except (OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print('Initialization cancelled: a working interactive terminal is required.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
