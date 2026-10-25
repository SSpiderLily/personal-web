"""Production data command adapter. No shell, environment dumps, or implicit writes."""
import json
import ipaddress
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
from urllib.parse import urlsplit
import urllib.request
import urllib.error

ENV_KEYS={'APP_ENV','DEBUG','DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD','UPLOAD_DIR','ADMIN_ALLOWED_ORIGINS','ADMIN_SESSION_HOURS','PRODUCTION_MODE','PUBLIC_ORIGIN'}


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
    mode=data.get('mode','https')
    if mode not in ('https','http_ssh'):
        raise RuntimeError('Unsupported production transport mode')
    needed=('environment_file','uploads_dir','backup_root','replica_root','pg_bin','maintenance_file')
    if any(not isinstance(data.get(k),str) or not data[k] for k in needed):
        raise RuntimeError('Complete data_safety paths are required')
    for key in needed:
        p=Path(data[key])
        if not p.is_absolute() or '..' in p.parts or p.is_symlink():
            raise RuntimeError('Data paths must be absolute and cannot be symlinks')
    prerequisites=data.get('prerequisites',{})
    required=('restore_drill_passed','previous_schema_compatible','exclusive_writer_service')
    if mode=='https':
        try:
            origin=urlsplit(data.get('https_origin',''))
            if (origin.scheme!='https' or not origin.hostname or origin.username or origin.password
                    or origin.path or origin.query or origin.fragment or origin.hostname.endswith(('.invalid','.test'))):
                raise ValueError()
            origin.port
        except ValueError:
            raise RuntimeError('A real exact HTTPS origin is required') from None
        required+=('tls_verified','replica_encrypted_offsite')
    else:
        try:
            origin=urlsplit(data.get('public_origin',''))
            address=ipaddress.ip_address(origin.hostname or '')
            if (address.version!=4 or not address.is_global or address.is_multicast
                    or data['public_origin']!='http://'+str(address)):
                raise ValueError()
        except (ValueError,KeyError):
            raise RuntimeError('A real exact HTTP public IP origin is required') from None
        if data.get('admin_origin')!='http://127.0.0.1:18880':
            raise RuntimeError('The exact SSH loopback admin origin is required')
        required+=('ssh_tunnel_verified','public_admin_blocked','local_backup_accepted')
    if not isinstance(prerequisites,dict) or any(prerequisites.get(k) is not True for k in required):
        raise RuntimeError('Production prerequisite evidence must be explicitly accepted')
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
    mode=data.get('mode','https')
    if env.get('PRODUCTION_MODE','https')!=mode:
        raise RuntimeError('Production transport mode must match deployment')
    try:origins=json.loads(env.get('ADMIN_ALLOWED_ORIGINS','[]'))
    except ValueError:raise RuntimeError('Explicit admin origins are required') from None
    if mode=='http_ssh':
        if env.get('PUBLIC_ORIGIN')!=data['public_origin'] or origins!=[data['admin_origin']]:
            raise RuntimeError('HTTP public and SSH admin origins must match deployment exactly')
        public_origin=data['public_origin']
    else:
        if not isinstance(origins,list) or data['https_origin'] not in origins:
            raise RuntimeError('Deployment HTTPS origin must be explicitly allowed')
        public_origin=data['https_origin']
    if Path(data['maintenance_file']).exists():
        raise RuntimeError('An existing maintenance window must be resolved before deploying')
    # HTTPS uses urllib certificate verification; both modes require the exact
    # current revision and refuse redirects, before opening maintenance.
    try:
        expected=(Path(config['root'])/'current/REVISION').read_text().strip()
        for origin in ([public_origin,data['admin_origin']] if mode=='http_ssh' else [public_origin]):
            url=origin+'/__release.txt'
            with urllib.request.urlopen(url,timeout=10) as response:
                if response.geturl()!=url or response.read(128).decode().strip()!=expected:
                    raise ValueError()
        if mode=='http_ssh':
            for method,path in [('GET','/admin'),('GET','/api/admin/session'),('POST','/api/admin/login')]:
                url=public_origin+path
                request=urllib.request.Request(url,method=method)
                try:
                    with urllib.request.urlopen(request,timeout=10):
                        raise ValueError()
                except urllib.error.HTTPError as error:
                    if error.code!=404 or error.geturl()!=url:raise ValueError()
            url=data['admin_origin']+'/api/admin/session'
            try:
                with urllib.request.urlopen(url,timeout=10) as response:
                    if response.geturl()!=url:raise ValueError()
            except urllib.error.HTTPError as error:
                # The legacy release may not yet implement sessions. New-release
                # authentication and CSRF are verified after activation.
                if error.code not in (401,404) or error.geturl()!=url:raise ValueError()
    except Exception:
        raise RuntimeError('Public transport, private admin or current release verification failed') from None
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
