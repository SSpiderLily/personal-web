"""Run backend tests using a fresh local PostgreSQL cluster, never an existing DB."""
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


def find_pg_bin():
    """PG_BIN overrides discovery; otherwise support Linux PATH/pg_config and macOS."""
    if os.environ.get('PG_BIN'):
        candidates = [Path(os.environ['PG_BIN'])]
    else:
        candidates = []
        if executable := shutil.which('initdb'):
            candidates.append(Path(executable).parent)
        if executable := shutil.which('pg_config'):
            result = subprocess.run([executable, '--bindir'], capture_output=True, text=True, check=True)
            candidates.append(Path(result.stdout.strip()))
        candidates.extend([Path('/Library/PostgreSQL/17/bin')])
        candidates.extend(sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True))
    for candidate in candidates:
        if all((candidate / name).is_file() for name in ('initdb', 'pg_ctl', 'psql')):
            return candidate
    raise RuntimeError('PostgreSQL binaries unavailable; set PG_BIN to a directory containing initdb, pg_ctl and psql')


def main():
    backend = Path(__file__).resolve().parents[1] / 'backend'
    pg_bin = find_pg_bin()
    # Clear libpq and application DB overrides before creating our owned target.
    env = {key: value for key, value in os.environ.items() if not key.startswith(('PG', 'DB_'))}
    with tempfile.TemporaryDirectory(prefix='pwdb-', dir='/tmp') as directory:
        root = Path(directory)
        data, sockets, log = root / 'data', root / 'socket', root / 'postgres.log'
        sockets.mkdir(mode=0o700)
        subprocess.run([str(pg_bin / 'initdb'), '-D', str(data), '-U', 'personal_web_test',
                        '--auth=trust', '--encoding=UTF8', '--no-locale'], env=env,
                       stdout=subprocess.DEVNULL, check=True)
        with ExitStack() as cleanup:
            # Register cleanup before startup to also stop a partly started server.
            cleanup.callback(subprocess.run, [str(pg_bin / 'pg_ctl'), '-D', str(data), '-m', 'immediate', '-w', 'stop'],
                             env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                subprocess.run([str(pg_bin / 'pg_ctl'), '-D', str(data), '-l', str(log), '-w', 'start',
                                '-o', f"-k {sockets} -p 25432 -c listen_addresses='' -c fsync=off"],
                               env=env, stdout=subprocess.DEVNULL, check=True)
            except subprocess.CalledProcessError:
                print(log.read_text() if log.exists() else 'PostgreSQL failed before writing its log', file=sys.stderr)
                raise
            db_name = 'personal_web_test_' + uuid.uuid4().hex
            subprocess.run([str(pg_bin / 'psql'), '-X', '-h', str(sockets), '-p', '25432',
                            '-U', 'personal_web_test', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
                            '-c', f'CREATE DATABASE {db_name}'], env=env, stdout=subprocess.DEVNULL, check=True)
            env.update(APP_ENV='test', DEBUG='false', APP_RUN_DB_TESTS='1', APP_TEST_PG_BIN=str(pg_bin), DB_HOST=str(sockets),
                       DB_PORT='25432', DB_NAME=db_name, DB_USER='personal_web_test', DB_PASSWORD='')
            version = subprocess.run([str(pg_bin / 'psql'), '-X', '-h', str(sockets), '-p', '25432',
                                      '-U', 'personal_web_test', '-d', db_name, '-Atc', 'SHOW server_version'],
                                     env=env, capture_output=True, text=True, check=True).stdout.strip()
            print(f'Isolated PostgreSQL {version}; temporary cluster, Unix socket only.', flush=True)
            result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_database*.py', '-v', *sys.argv[1:]],
                                    cwd=backend, env=env)
            return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
