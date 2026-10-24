"""Anonymous visit identity and deduplicated writes, without IP/UA storage."""
from datetime import datetime
import re
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.database import transaction
from app.settings import Settings

TIMEZONE = 'Asia/Shanghai'
COOKIE = 'personal_web_visitor'
COOKIE_PATH = '/api/admin/visits'
COOKIE_MAX_AGE = 31_536_000
_UUID_COOKIE = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')


def today():
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def resolve_visitor(value: str | None) -> tuple[UUID, bool]:
    if value is not None and _UUID_COOKIE.fullmatch(value):
        return UUID(value), False
    return uuid4(), True


def record_visit(settings: Settings, kind: str, visitor_id: UUID, project_id: int | None = None) -> bool:
    """Return acceptance (including duplicates), after the transaction commits.

    Lock the project while checking publication to serialize with archive/delete.
    Dates come only from the server; callers cannot backfill historical events.
    """
    if kind not in ('website', 'project') or (kind == 'project' and (type(project_id) is not int or not 0 < project_id < 2**63)):
        raise ValueError('Invalid visit')
    visit_date = today()
    with transaction(settings) as conn:
        if kind == 'website':
            conn.execute('INSERT INTO site_daily_visitors(visit_date,visitor_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                         (visit_date, visitor_id))
        else:
            row = conn.execute("SELECT id FROM projects WHERE id=%s AND status='published' FOR SHARE", (project_id,)).fetchone()
            if row is None:
                return False
            conn.execute('INSERT INTO project_daily_visitors(project_id,visit_date,visitor_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                         (project_id, visit_date, visitor_id))
    return True
