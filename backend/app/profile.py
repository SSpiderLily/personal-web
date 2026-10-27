"""Single site profile, exact validation and atomic writes."""
import re
from urllib.parse import unquote, urlsplit
from uuid import UUID
from psycopg.types.json import Jsonb
from app import admin_auth as auth, projects, about_content
from app.database import connection, transaction
from app.settings import Settings

FIELDS = ('name', 'title', 'introduction', 'skills', 'avatar_file_id', 'contacts', 'social_links')


def _text(value, maximum, minimum=0):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or '\x00' in value:
        raise auth.invalid_request()
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise auth.invalid_request() from None
    return value


def _url(value, contact):
    value = _text(value, 2048, 1)
    decoded = unquote(value)
    if any(c.isspace() or c == '\ufeff' for c in value) or any(ord(c) <= 32 or ord(c) == 127 or c == '\\' for c in value + decoded):
        raise auth.invalid_request()
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in ('http', 'https'):
            # Reuse the browser-compatible HTTP policy; _text above still
            # enforces profile links being required strings, never null.
            return projects._url(value)
        elif contact and parsed.scheme.lower() == 'mailto':
            if not re.fullmatch(r'mailto:[A-Za-z0-9.!#$&\'*+/=_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value, re.I):
                raise ValueError
        elif contact and parsed.scheme.lower() == 'tel':
            if not re.fullmatch(r'tel:\+?[0-9][0-9().-]*', value, re.I):
                raise ValueError
        else:
            raise ValueError
    except ValueError:
        raise auth.invalid_request() from None
    return value


def validate_profile(payload):
    if not isinstance(payload, dict) or set(payload) not in (set(FIELDS), set(FIELDS) | {'about_content'}):
        raise auth.invalid_request()
    result = {key: _text(payload[key], limit) for key, limit in [('name', 100), ('title', 200), ('introduction', 20000)]}
    skills = payload['skills']
    if not isinstance(skills, list) or len(skills) > 30:
        raise auth.invalid_request()
    result['skills'] = [_text(value, 100, 1) for value in skills]
    avatar = payload['avatar_file_id']
    if avatar is not None:
        if not isinstance(avatar, str):
            raise auth.invalid_request()
        try:
            avatar = str(UUID(avatar))
        except (ValueError, AttributeError):
            raise auth.invalid_request() from None
    result['avatar_file_id'] = avatar
    for key in ('contacts', 'social_links'):
        links = payload[key]
        if not isinstance(links, list) or len(links) > 20:
            raise auth.invalid_request()
        result[key] = []
        for item in links:
            if not isinstance(item, dict) or set(item) != {'label', 'url'}:
                raise auth.invalid_request()
            result[key].append({'label': _text(item['label'], 100, 1), 'url': _url(item['url'], key == 'contacts')})
    if 'about_content' in payload:
        result['about_content']=about_content.validate(payload['about_content'])
    return result


def _read(conn):
    row = conn.execute('SELECT name,title,introduction,skills,avatar_file_id,contacts,social_links,about_content FROM site_profile WHERE id=1').fetchone()
    if row is None:
        return dict(name='', title='', introduction='', skills=[], avatar_file_id=None, contacts=[], social_links=[], projects=[])
    value = dict(zip(FIELDS, row))
    value['avatar_file_id'] = str(value['avatar_file_id']) if value['avatar_file_id'] else None
    if len(row)>len(FIELDS) and row[len(FIELDS)]:
        value['about_content']=row[len(FIELDS)]
    return value | {'projects': []}


def load_profile(settings: Settings | None = None):
    with connection(settings) as conn:
        return _read(conn)


def save_profile(payload, settings: Settings | None = None):
    value = validate_profile(payload)
    with transaction(settings) as conn:
        # Covers first insertion as well as updates; every writer uses this lock.
        conn.execute('SELECT pg_advisory_xact_lock(194521, 5)')
        if value['avatar_file_id'] is not None:
            if conn.execute('SELECT id FROM uploaded_files WHERE id=%s FOR KEY SHARE', (value['avatar_file_id'],)).fetchone() is None:
                raise auth.invalid_request()
        conn.execute('''INSERT INTO site_profile(id,name,title,introduction,skills,avatar_file_id,contacts,social_links)
            VALUES (1,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,title=excluded.title,introduction=excluded.introduction,skills=excluded.skills,
            avatar_file_id=excluded.avatar_file_id,contacts=excluded.contacts,social_links=excluded.social_links,updated_at=clock_timestamp()''',
            tuple(Jsonb(value[key]) if key in ('contacts','social_links') else value[key] for key in FIELDS))
        if 'about_content' in value:
            conn.execute('UPDATE site_profile SET about_content=%s WHERE id=1',(Jsonb(value['about_content']),))
        result = _read(conn)
    return result
