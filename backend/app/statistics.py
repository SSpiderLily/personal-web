"""Authenticated statistics data: distinct visitors over a fixed server window."""
from datetime import timedelta

from app import visitors
from app.database import transaction
from app.settings import Settings


def date_window(days: int):
    if type(days) is not int or days not in (7, 30):
        raise ValueError('Statistics days must be 7 or 30')
    end = visitors.today()
    return end - timedelta(days=days - 1), end


def read_statistics(settings: Settings, days: int = 7) -> dict:
    start, end = date_window(days)
    # One stable snapshot across the site count and current project list/counts.
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        website_visitors = conn.execute('''SELECT count(DISTINCT visitor_id) FROM site_daily_visitors
            WHERE visit_date BETWEEN %s AND %s''', (start, end)).fetchone()[0]
        rows = conn.execute('''SELECT p.id,p.name,count(DISTINCT v.visitor_id)
            FROM projects p LEFT JOIN project_daily_visitors v
                ON v.project_id=p.id AND v.visit_date BETWEEN %s AND %s
            GROUP BY p.id ORDER BY p.sort_order,p.id''', (start, end)).fetchall()
    return {'days': days, 'timezone': visitors.TIMEZONE, 'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'website_visitors': website_visitors,
            'projects': [{'project_id': row[0], 'name': row[1], 'visitors': row[2]} for row in rows]}
