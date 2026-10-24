#!/usr/bin/env python3
"""Linux deployment entry point. Inert without --execute and enabled config."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deploy_runtime as data_runtime


def run(*args, cwd=None, env=None):
    try:
        return subprocess.check_output(args, cwd=cwd, env=env, text=True, timeout=900).strip()
    except subprocess.CalledProcessError as error:
        if error.output:
            print(error.output, file=sys.stderr)
        raise


def switch(root, target):
    link = root / '.current-next'
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    os.replace(link, root / 'current')


def healthy(config, sha):
    run('/usr/bin/systemctl', 'is-active', '--quiet', 'fastapi-personal-web')
    def get(path):
        req = urllib.request.Request(config['health_url'].rstrip('/') + path,
                                     headers={'Host': config['health_host']})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode()
    if json.loads(get('/api/health')).get('status') != 'ok':
        raise RuntimeError('API health check failed')
    if get('/__release.txt').strip() != sha:
        raise RuntimeError('Nginx is not serving the expected release')
    html = get('/')
    assets = re.findall(r'(?:src|href)=[\"\'](/assets/[^\"\']+)[\"\']', html)
    if not assets:
        raise RuntimeError('Homepage has no built assets')
    for asset in assets:
        get(asset)


def wait_healthy(config, sha):
    for attempt in range(10):
        try:
            healthy(config, sha)
            return
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)


def restart():
    run('/usr/bin/sudo', '-n', '/usr/bin/systemctl', 'restart', 'fastapi-personal-web')


def activate(root, release, config):
    previous = (root / 'current').resolve(strict=True)
    old_sha = (previous / 'REVISION').read_text().strip()
    sha = (release / 'REVISION').read_text().strip()
    # Include switching in the rollback boundary, also for SIGTERM/SIGHUP.
    try:
        switch(root, release)
        restart()
        wait_healthy(config, sha)
    except BaseException:
        switch(root, previous)
        restart()
        wait_healthy(config, old_sha)
        print('Deployment failed; previous release restored: ' + old_sha, file=sys.stderr)
        raise
    print('Deployed: ' + sha, flush=True)


def fetch(config, cache):
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15'
    run('git', '--git-dir', str(cache), 'fetch', '--no-tags', config['repository'],
        '+refs/heads/main:refs/heads/main', env=env)
    return run('git', '--git-dir', str(cache), 'rev-parse', 'refs/heads/main')


def prepare(config, root, cache, sha):
    env = os.environ.copy()
    env['PATH'] = config['tool_path'] + ':/usr/bin:/bin'
    # Build/import validation must never inherit production credentials or select production.
    for key in list(env):
        if key.startswith(('DB_', 'PG')) or key in ('APP_ENV','DEBUG','UPLOAD_DIR','ADMIN_ALLOWED_ORIGINS'):
            env.pop(key)
    env.update(APP_ENV='test', DEBUG='false')
    # Never inherit frontend production overrides from the SSH login environment.
    for key in list(env):
        if key.startswith(('VITE_', 'UV_', 'PYTHON')) or key in ('VIRTUAL_ENV', 'NODE_ENV', 'NODE_OPTIONS'):
            env.pop(key)
    if run('node', '--version', env=env) != 'v22.22.1':
        raise RuntimeError('Node 22.22.1 required')
    if run('uv', '--version', env=env).split()[:2] != ['uv', '0.12.3']:
        raise RuntimeError('uv 0.12.3 required')
    if not run(config['python'], '--version').startswith('Python 3.14.'):
        raise RuntimeError('Python 3.14 required')
    # Keep the final absolute directory throughout uv installation: venv shebangs
    # contain it, so a completed release must never be renamed.
    release = Path(tempfile.mkdtemp(prefix=sha[:12] + '-', dir=root / 'releases'))
    release.chmod(0o755)  # Nginx's worker user must be able to traverse it.
    archive = release / 'source.tar'
    run('git', '--git-dir', str(cache), 'archive', '--format=tar', '-o', str(archive), sha)
    run('tar', '-xf', str(archive), '-C', str(release))
    archive.unlink()
    print('Installing locked production dependencies for ' + sha, flush=True)
    backend = release / 'backend'
    run('uv', 'venv', '--python', config['python'], '.venv', cwd=backend, env=env)
    requirements = run('uv', 'export', '--locked', '--no-dev', '--no-emit-project',
                       '--python', config['python'], '--format', 'requirements-txt',
                       cwd=backend, env=env)
    (backend / 'deployment-requirements.txt').write_text(requirements + '\n')
    run('uv', 'pip', 'sync', '--python', str(backend / '.venv/bin/python'),
        '--require-hashes', '--index-url', config.get('python_index', 'https://pypi.org/simple'),
        'deployment-requirements.txt', cwd=backend, env=env)
    run(str(release / 'backend/.venv/bin/gunicorn'), '--check-config', 'app.main:app',
        '-w', '2', '-k', 'uvicorn.workers.UvicornWorker', cwd=release / 'backend', env=env)
    print('Building frontend for ' + sha, flush=True)
    run('npm', 'ci', '--no-audit', '--no-fund', cwd=release / 'frontend', env=env)
    run('npm', 'run', 'build', cwd=release / 'frontend', env=env)
    (release / 'REVISION').write_text(sha + '\n')
    (release / 'frontend/dist/__release.txt').write_text(sha + '\n')
    return release



def preflight_data(config, release):
    return data_runtime.preflight(config, release)


def backup_data(config, release, lock_fd):
    return data_runtime.backup(config, release, lock_fd)


def migrate_data(config, release, lock_fd):
    return data_runtime.migrate(config, release, lock_fd)


def verify_data(config, release, lock_fd):
    return data_runtime.verify(config, release, lock_fd)


def maintenance(config, enabled):
    path = Path(config['data_safety']['maintenance_file'])
    if enabled:
        # Exclusive creation avoids clearing another operator's maintenance flag.
        with path.open('x') as stream:
            stream.write('personal-web deployment\n')
        path.chmod(0o644)
    else:
        if path.is_symlink():
            raise RuntimeError('Maintenance marker unexpectedly changed')
        path.unlink()


def stop():
    run('/usr/bin/sudo', '-n', '/usr/bin/systemctl', 'stop', 'fastapi-personal-web')
    state = run('/usr/bin/systemctl', 'show', 'fastapi-personal-web', '--property=ActiveState', '--value')
    if state != 'inactive':
        raise RuntimeError('All application workers must stop before backup')


def activate_data(root, release, config, lock_fd):
    previous = (root / 'current').resolve(strict=True)
    old_sha = (previous / 'REVISION').read_text().strip()
    sha = (release / 'REVISION').read_text().strip()
    preflight_data(config, release)
    maintenance(config, True)
    try:
        stop()
        backup_data(config, release, lock_fd)
        migrate_data(config, release, lock_fd)
        switch(root, release)
        restart()
        wait_healthy(config, sha)
        verify_data(config, release, lock_fd)
    except BaseException:
        # Pending migrations are atomic and applied extensions must remain old-compatible.
        # Never restore a database or uploads automatically after a code failure.
        switch(root, previous)
        restart()
        wait_healthy(config, old_sha)
        maintenance(config, False)
        raise
    maintenance(config, False)
    print('Deployed with verified data safeguards: ' + sha, flush=True)

def deploy(config, sha):
    data_runtime.data_config(config)
    root = Path(config['root'])
    if not root.is_absolute() or not (root / 'current').is_symlink():
        raise RuntimeError('Initialize a validated current release before enabling deployment')
    descriptor = os.open(root / 'deploy.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise RuntimeError('Deployment lock must be an owned single-link regular file')
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = (root / 'current').resolve(strict=True)
        old_sha = (current / 'REVISION').read_text().strip()
        wait_healthy(config, old_sha)
        cache = root / 'repository.git'
        if not cache.exists():
            run('git', 'init', '--bare', str(cache))
        if fetch(config, cache) != sha:
            raise RuntimeError('Refusing stale SHA: requested commit is no longer main HEAD')
        if old_sha == sha:
            print('Already deployed and healthy: ' + sha)
            return
        release = prepare(config, root, cache, sha)
        if fetch(config, cache) != sha:
            raise RuntimeError('main changed during preparation; current release unchanged')
        activate_data(root, release, config, lock.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sha')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--config', default='/etc/personal-web/deploy.json')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.sha):
        parser.error('A full lowercase commit SHA is required')
    if not args.execute:
        print('Draft only: no commands executed. Requires --execute and enabled configuration.')
        return
    config = json.loads(Path(args.config).read_text())
    if config.get('enabled') is not True:
        parser.error('Deployment is disabled in configuration')
    if sys.platform != 'linux':
        parser.error('Real deployment requires Linux')
    def interrupted(signum, frame):
        raise RuntimeError('Deployment interrupted by signal ' + str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    deploy(config, args.sha)


if __name__ == '__main__':
    main()
