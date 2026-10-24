"""Explicit read-only readiness probe; never creates fixtures, sessions, or visits."""
import json
import sys

from app.database import transaction
from app.settings import Settings, get_settings
from app.admin_uploads import load_image, storage_directory
from app.statistics import read_statistics


def check(settings: Settings) -> dict:
    if settings.app_env not in ('production','test') or not settings.upload_dir:
        raise ValueError('Explicit production/test target and persistent uploads are required')
    if settings.app_env=='production' and (settings.db_name,settings.db_user)!=('personal_web_prod','personal_web_prod'):
        raise ValueError('Production database identity required')
    with storage_directory(settings):
        pass
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if conn.execute('SELECT current_database(),current_user').fetchone()!=(settings.db_name,settings.db_user):
            raise ValueError('Database identity mismatch')
        # These reads pin actual cross-module tables, rather than relying on /api/health.
        counts={name:conn.execute('SELECT count(*) FROM '+name).fetchone()[0]
                for name in ('admin_accounts','admin_sessions','projects','project_blocks','project_screenshots',
                             'site_profile','uploaded_files','tool_settings','site_daily_visitors','project_daily_visitors')}
        images=conn.execute('SELECT id FROM uploaded_files').fetchall()
        for (identifier,) in images:
            load_image(settings,str(identifier),conn=conn)
    read_statistics(settings,7)
    read_statistics(settings,30)
    return {'ready':True,'database':settings.db_name,'user':settings.db_user,'images':len(images),
            'admin_initialized':counts['admin_accounts']==1}


def main():
    try:
        print(json.dumps(check(get_settings())))
        return 0
    except Exception:
        print('Readiness failed: verify production configuration, schema and persistent image storage.',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
