"""Production data command adapter. No shell, environment dumps, or implicit writes."""
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
from urllib.parse import urlsplit
import urllib.request

ENV_KEYS={'APP_ENV','DEBUG','DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD','UPLOAD_DIR','ADMIN_ALLOWED_ORIGINS','ADMIN_SESSION_HOURS'}


def private_environment(path):
    path=Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError('A protected absolute environment file is required')
    info=path.stat()
    # Dedicated deployment group may read; group/world writes and world reads forbidden.
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0,os.geteuid())
            or stat.S_IMODE(info.st_mode) not in (0o600,0o640)):
        raise RuntimeError('Environment file must be owner-controlled mode 0600 or 0640')
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    try:
        for line in path.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            key,separator,value=line.partition('=')
            if not separator or key not in ENV_KEYS or key in env:
                raise ValueError()
            parts=shlex.split(value,comments=False,posix=True)
            if len(parts)>1:raise ValueError()
            env[key]=parts[0] if parts else ''
    except (ValueError,UnicodeError):
        raise RuntimeError('Unsupported environment file syntax; use one literal KEY=value per line') from None
    if (env.get('APP_ENV')!='production' or env.get('DEBUG','').lower()!='false'
            or env.get('DB_NAME')!='personal_web_prod' or env.get('DB_USER')!='personal_web_prod'
            or not env.get('DB_PASSWORD')):
        raise RuntimeError('Explicit production environment and database credentials are required')
    return env


def data_config(config):
    data=config.get('data_safety')
    if not isinstance(data,dict) or data.get('enabled') is not True:
        raise RuntimeError('data_safety.enabled is required before database-backed deployment')
    needed=('environment_file','uploads_dir','backup_root','replica_root','pg_bin','maintenance_file','https_origin')
    if any(not isinstance(data.get(k),str) or not data[k] for k in needed):
        raise RuntimeError('Complete data_safety paths and HTTPS origin are required')
    for key in needed[:-1]:
        p=Path(data[key])
        if not p.is_absolute() or '..' in p.parts or p.is_symlink():
            raise RuntimeError('Data paths must be absolute and cannot be symlinks')
    origin=urlsplit(data['https_origin'])
    if (origin.scheme!='https' or not origin.hostname or origin.username or origin.password
            or origin.path or origin.query or origin.fragment or origin.hostname.endswith(('.invalid','.test'))):
        raise RuntimeError('A real exact HTTPS origin is required')
    prerequisites=data.get('prerequisites',{})
    if any(prerequisites.get(k) is not True for k in ('tls_verified','replica_encrypted_offsite','restore_drill_passed','previous_schema_compatible','exclusive_writer_service')):
        raise RuntimeError('Production prerequisite evidence must be explicitly accepted')
    try:
        origin.port
    except ValueError:
        raise RuntimeError('Invalid HTTPS origin port') from None
    root=Path(config['root']).resolve()
    paths={k:Path(data[k]).resolve() for k in ('uploads_dir','backup_root','replica_root','maintenance_file')}
    for p in paths.values():
        if p.is_relative_to(root):raise RuntimeError('Persistent data must be outside release root')
    directories=[paths[k] for k in ('uploads_dir','backup_root','replica_root')]
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(directories) for b in directories[i+1:]):
        raise RuntimeError('Upload and backup destinations must not overlap')
    if any(paths['maintenance_file'].is_relative_to(p) for p in directories):
        raise RuntimeError('Maintenance marker must be outside uploads and backups')
    return data


def command(release,argv,env,lock_fd=None):
    """Use the prepared release interpreter; output only structured safe results."""
    args=[str(Path(release)/'backend/.venv/bin/python'),*map(str,argv)]
    try:
        result=subprocess.run(args,cwd=Path(release)/'backend',env=env,
                              pass_fds=() if lock_fd is None else (lock_fd,),
                              capture_output=True,text=True,timeout=900,check=False)
        if result.returncode:raise RuntimeError('Production data operation failed; current release must remain protected')
        value=json.loads(result.stdout)
        if not isinstance(value,dict):raise ValueError()
        return value
    except (OSError,subprocess.TimeoutExpired,ValueError):
        raise RuntimeError('Production data operation did not return a valid result') from None


def expected_args(root,lock_fd):
    return ['--expect-database','personal_web_prod','--expect-user','personal_web_prod',
            '--lock-file',str(Path(root)/'deploy.lock'),'--lock-fd',str(lock_fd)]


def preflight(config,release):
    data=data_config(config)
    env=private_environment(data['environment_file'])
    if env.get('UPLOAD_DIR')!=data['uploads_dir']:
        raise RuntimeError('UPLOAD_DIR must match deployment persistent directory')
    try:origins=json.loads(env.get('ADMIN_ALLOWED_ORIGINS','[]'))
    except ValueError:raise RuntimeError('Explicit HTTPS origins are required') from None
    if data['https_origin'] not in origins:
        raise RuntimeError('Deployment HTTPS origin must be explicitly allowed')
    if Path(data['maintenance_file']).exists():
        raise RuntimeError('An existing maintenance window must be resolved before deploying')
    # urllib verifies the public certificate and host before opening a maintenance window.
    try:
        with urllib.request.urlopen(data['https_origin']+'/__release.txt',timeout=10) as response:
            if response.geturl()!=data['https_origin']+'/__release.txt':
                raise ValueError()
            revision=response.read(128).decode().strip()
        if revision!=(Path(config['root'])/'current/REVISION').read_text().strip():
            raise ValueError()
    except Exception:
        raise RuntimeError('Public TLS or current release verification failed') from None
    return command(release,['-m','app.production_migrate','--expect-database','personal_web_prod',
                            '--expect-user','personal_web_prod'],env)


def backup(config,release,lock_fd):
    data=data_config(config);env=private_environment(data['environment_file'])
    revision=(Path(config['root'])/'current/REVISION').read_text().strip()
    value=command(release,[str(Path(release)/'scripts/data_backup.py'),'create',
        '--uploads-dir',data['uploads_dir'],'--backup-root',data['backup_root'],
        '--replica-root',data['replica_root'],'--revision',revision,'--pg-bin',data['pg_bin'],
        '--lock-file',str(Path(config['root'])/'deploy.lock'),'--lock-fd',str(lock_fd),
        '--execute','--writers-stopped'],env,lock_fd)
    if not isinstance(value.get('backup'),str) or not Path(value['backup']).is_absolute():
        raise RuntimeError('Backup receipt is missing')
    command(release,[str(Path(release)/'scripts/data_backup.py'),'verify','--backup',value['backup']],env)
    return value


def migrate(config,release,lock_fd):
    value=command(release,['-m','app.production_migrate',*expected_args(config['root'],lock_fd),'--execute'],
                  private_environment(data_config(config)['environment_file']),lock_fd)
    if value.get('pending')!=[]:raise RuntimeError('Schema migration is incomplete')
    return value


def verify(config,release,lock_fd):
    data=data_config(config);env=private_environment(data['environment_file'])
    value=command(release,['-m','app.production_migrate','--expect-database','personal_web_prod',
                           '--expect-user','personal_web_prod'],env)
    if value.get('pending')!=[]:raise RuntimeError('Schema is not ready')
    return command(release,['-m','app.production_readiness'],env)


def verify_rollback(config, release, lock_fd):
    # Old schema may intentionally precede pending migrations. Probe only its actual
    # tables/images, allowing the initial legacy site with no business schema.
    env=private_environment(data_config(config)['environment_file'])
    return command(release,['-m','app.production_readiness','--allow-empty-schema'],env)
