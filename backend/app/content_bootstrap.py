"""Explicit development bootstrap. Importing this module never writes data."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
from psycopg.types.json import Jsonb
from app.database import transaction, validate_test_target
from app.admin_uploads import decode_image, storage_directory
from app.settings import get_settings

KEY = 'initial-trip-and-profile-v1'
LOCK = 794675013004
ROOT = Path(__file__).resolve().parents[2]

class BootstrapError(RuntimeError):
    pass


def write_content(conn, data, identifier):
    value = data['project']
    project_id = conn.execute('''INSERT INTO projects(name,summary,category,tech_stack,features,
        cover_file_id,cover_alt,demo_url,source_url,status,published_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'published',now()) RETURNING id''',
        (value['name'],value['summary'],value['category'],value['tech_stack'],value['features'],
         identifier,value['cover_alt'],value['demo_url'],value['source_url'])).fetchone()[0]
    for position, block in enumerate(value['blocks']):
        conn.execute("INSERT INTO project_blocks(project_id,position,kind,body) VALUES (%s,%s,'text',%s)",
                     (project_id,position,block['body']))
    profile=data['profile']
    conn.execute('''INSERT INTO site_profile(name,title,introduction,skills,contacts,social_links)
        VALUES (%s,%s,%s,%s,%s,%s)''',(profile['name'],profile['title'],profile['introduction'],
        profile['skills'],Jsonb(profile['contacts']),Jsonb(profile['social_links'])))
    conn.execute('INSERT INTO content_bootstraps(key,project_id) VALUES (%s,%s)',(KEY,project_id))
    return project_id


def bootstrap(settings):
    if settings.app_env == 'test':
        validate_test_target(settings)
    elif settings.app_env != 'development' or (settings.db_name,settings.db_user) != ('personal_web_dev','personal_web_dev'):
        raise BootstrapError('Development database/account required; refusing initialization')
    created=False
    identifier=uuid4()
    key=str(identifier)
    # Keep directory descriptor until the DB commit, including failure cleanup.
    directory=None
    try:
        with transaction(settings) as conn:
            identity=conn.execute('SELECT current_database(),current_user').fetchone()
            if identity != (settings.db_name,settings.db_user):
                raise BootstrapError('Database identity mismatch; refusing initialization')
            conn.execute("SET LOCAL lock_timeout='5s'")
            conn.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK,))
            previous=conn.execute('SELECT project_id FROM content_bootstraps WHERE key=%s',(KEY,)).fetchone()
            if previous: return previous[0]
            if conn.execute('SELECT EXISTS(SELECT 1 FROM projects) OR EXISTS(SELECT 1 FROM site_profile)').fetchone()[0]:
                raise BootstrapError('Existing content found; refusing to overwrite')
            data=json.loads((ROOT/'backend/content/initial_content.json').read_text())
            image=(ROOT/'frontend/src/assets/trip-preview.png').read_bytes()
            media,width,height=decode_image(image,'trip-preview.jpg','image/jpeg')
            # Enter manually so cleanup remains possible after a failed commit.
            storage=storage_directory(settings,create=True)
            directory=storage.__enter__()
            descriptor=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
            created=True
            with os.fdopen(descriptor,'wb') as output:
                output.write(image); output.flush(); os.fsync(output.fileno())
            conn.execute('''INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''',(identifier,key,'trip-preview.jpg',media,len(image),width,height))
            project_id=write_content(conn,data,identifier)
        return project_id
    except BaseException:
        if created:
            try: os.unlink(key,dir_fd=directory)
            except OSError: pass  # Rolled-back metadata keeps any orphan inaccessible.
        raise
    finally:
        if directory is not None:
            storage.__exit__(None,None,None)


def main():
    settings=get_settings()
    if settings.app_env != 'development':
        print('Development environment required; refusing initialization',file=sys.stderr)
        return 1
    try: bootstrap(settings)
    except Exception:
        print('Content initialization failed; check migrations, storage and existing content.',file=sys.stderr)
        return 1
    print('Initial content ready; existing initialized content preserved.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
