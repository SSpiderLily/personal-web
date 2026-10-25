"""Shared fail-closed target and release-lock guards for explicit production tools."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import sys

from app import database


class ProductionOperationError(ValueError):
    """Safe operation rejection without connection or credential details."""


def validate_target(settings, expected_database, expected_user):
    identity = (settings.db_name, settings.db_user)
    if settings.app_env == 'production':
        if identity != ('personal_web_prod', 'personal_web_prod'):
            raise ProductionOperationError('Production database and account must be personal_web_prod.')
    elif settings.app_env == 'test':
        database.validate_test_target(settings)
    else:
        raise ProductionOperationError('Explicit production or isolated test environment required.')
    if identity != (expected_database, expected_user):
        raise ProductionOperationError('Expected database/account does not match Settings.')


def verify_identity(conn, settings):
    if conn.execute('SELECT current_database(), current_user').fetchone() != (settings.db_name, settings.db_user):
        raise ProductionOperationError('Connected database/account does not match expected identity.')


def _same_file(fd, path):
    descriptor, named = os.fstat(fd), os.stat(path, follow_symlinks=False)
    if (not stat.S_ISREG(descriptor.st_mode) or not stat.S_ISREG(named.st_mode)
            or (descriptor.st_dev, descriptor.st_ino) != (named.st_dev, named.st_ino)
            or descriptor.st_uid != os.geteuid() or descriptor.st_mode & 0o022):
        raise ProductionOperationError('Release lock must be the same owned regular file without unsafe write permissions.')


@contextmanager
def release_lock(path, inherited_fd=None):
    """Own a nonblocking flock, or verify and borrow an already-held descriptor.

    An independent shared-lock probe must be blocked while the inherited open-file
    description succeeds. Both checks are nonblocking; borrowed locks remain held.
    """
    if not path or (inherited_fd is not None and inherited_fd < 0):
        raise ProductionOperationError('Execution requires a release lock file.')
    target = Path(path)
    if not target.is_absolute() or '..' in target.parts:
        raise ProductionOperationError('Release lock requires an absolute path without traversal.')
    fd = None
    try:
        # Reject symbolic links at every existing path component.
        if any(component.is_symlink() for component in (target, *target.parents)):
            raise ProductionOperationError('Release lock path must not contain symbolic links.')
        if inherited_fd is not None:
            _same_file(inherited_fd, target)
            probe = os.open(target, os.O_RDWR | os.O_NOFOLLOW)
            try:
                _same_file(probe, target)
                try:
                    fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise ProductionOperationError('Inherited exclusive release lock is not held.')
                try:
                    fcntl.flock(inherited_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ProductionOperationError('Provided descriptor does not hold the release lock.') from None
                _same_file(inherited_fd, target)
            finally:
                os.close(probe)
        else:
            fd = os.open(target, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            _same_file(fd, target)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ProductionOperationError('Another release operation holds the lock.') from None
            _same_file(fd, target)
        yield
    except OSError:
        raise ProductionOperationError('Release lock is unavailable or invalid.') from None
    finally:
        if fd is not None:
            os.close(fd)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, 'Invalid production operation arguments; use --help.\n')


def parser(description):
    result = SafeArgumentParser(description=description, allow_abbrev=False)
    result.add_argument('--expect-database', required=True)
    result.add_argument('--expect-user', required=True)
    result.add_argument('--execute', action='store_true')
    result.add_argument('--lock-file')
    result.add_argument('--lock-fd', type=int)
    return result
