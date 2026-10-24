"""Atomic project editing, publication and ordered public reads."""
import re
import ipaddress
from urllib.parse import unquote, urlsplit
from uuid import UUID

from app import admin_auth as auth
from app.database import transaction
from app.settings import Settings

FIELDS = ('name', 'summary', 'category', 'tech_stack', 'features', 'cover_file_id',
          'cover_alt', 'demo_url', 'source_url', 'blocks', 'screenshots')
COLUMNS = ('id', *FIELDS[:-2], 'status', 'sort_order', 'published_at', 'updated_at')
SELECT = 'SELECT ' + ', '.join(COLUMNS) + ' FROM projects'


def _text(value, maximum, minimum=0):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or '\x00' in value:
        raise auth.invalid_request()
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise auth.invalid_request() from None
    return value


def _strings(value, maximum, item_maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise auth.invalid_request()
    return [_text(item, item_maximum, 1) for item in value]


def _uuid(value, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
        raise auth.invalid_request()
    return str(UUID(value))


def _url(value, *, demo=False):
    if value is None:
        return None
    _text(value, 2048, 1)
    if demo and value == '/trip/':
        return value
    try:
        if re.search(r'%(?![0-9a-fA-F]{2})', value):
            raise ValueError
        decoded = unquote(value, errors='strict')
        if re.search(r'[\x00-\x20\x7f-\x9f\\]', value + decoded):
            raise ValueError
        matched = re.match(r'https?://([^/?#]+)', value, re.I)
        if matched is None:
            raise ValueError
        authority = matched.group(1)
        if not re.fullmatch(r'(?:\[[0-9a-fA-F:.]+\]|[A-Za-z0-9.-]+)(?::[0-9]*)?', authority):
            raise ValueError
        parsed = urlsplit(value)
        if (parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError
        parsed.port
        host = parsed.hostname
        try:
            ipaddress.ip_address(host)
        except ValueError:
            # A conservative DNS spelling avoids WHATWG's numeric-host coercions.
            labels = host.removesuffix('.').split('.')
            if (len(host) > 253 or not host.isascii() or labels[-1].isdigit()
                    or labels[-1].lower().startswith('0x') or any(not re.fullmatch(
                        r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels)):
                raise ValueError
            host.encode('ascii').decode('idna')
    except (ValueError, UnicodeError):
        raise auth.invalid_request() from None
    return value


def validate_project(payload: object, *, published=False) -> dict:
    if not isinstance(payload, dict) or set(payload) != set(FIELDS):
        raise auth.invalid_request()
    result = {field: _text(payload[field], maximum) for field, maximum in
              (('name',100), ('summary',2000), ('category',100), ('cover_alt',500))}
    result.update(tech_stack=_strings(payload['tech_stack'],20,100), features=_strings(payload['features'],30,500),
                  cover_file_id=_uuid(payload['cover_file_id'],nullable=True),
                  demo_url=_url(payload['demo_url'],demo=True), source_url=_url(payload['source_url']))
    blocks = payload['blocks']
    if not isinstance(blocks,list) or len(blocks)>100:
        raise auth.invalid_request()
    result['blocks'] = []
    for block in blocks:
        if not isinstance(block,dict):
            raise auth.invalid_request()
        if block.get('kind') == 'text' and set(block) == {'kind','body'}:
            result['blocks'].append(dict(kind='text',body=_text(block['body'],10000)))
        elif block.get('kind') == 'image' and set(block) == {'kind','file_id','caption'}:
            result['blocks'].append(dict(kind='image',file_id=_uuid(block['file_id']),caption=_text(block['caption'],500)))
        else:
            raise auth.invalid_request()
    screenshots = payload['screenshots']
    if not isinstance(screenshots,list) or len(screenshots)>30:
        raise auth.invalid_request()
    result['screenshots'] = []
    seen = set()
    for image in screenshots:
        if not isinstance(image,dict) or set(image) != {'file_id','caption'}:
            raise auth.invalid_request()
        identifier = _uuid(image['file_id'])
        if identifier in seen:
            raise auth.invalid_request()
        seen.add(identifier)
        result['screenshots'].append(dict(file_id=identifier,caption=_text(image['caption'],500)))
    if published and (not result['name'].strip() or not result['summary'].strip() or not result['tech_stack']
                      or result['cover_file_id'] is None or not any(
                          block['kind']=='image' or block['body'].strip() for block in result['blocks'])):
        raise auth.invalid_request()
    return result


def _not_found():
    return auth.AdminError(404, 'project_not_found', '项目不存在。')


def _id(identifier):
    if type(identifier) is not int or not 1 <= identifier <= 9223372036854775807:
        raise _not_found()
    return identifier


def _read(conn, identifier, *, public=False, lock=False):
    row = conn.execute(SELECT + " WHERE id=%s" + (" AND status='published'" if public else '') +
                       (' FOR UPDATE' if lock else ''), (_id(identifier),)).fetchone()
    if row is None:
        raise _not_found()
    value = dict(zip(COLUMNS,row))
    value['cover_file_id'] = str(value['cover_file_id']) if value['cover_file_id'] else None
    for name in ('published_at','updated_at'):
        value[name] = value[name].isoformat() if value[name] else None
    value['blocks'] = [dict(kind='text',body=body) if kind=='text' else dict(kind='image',file_id=str(file_id),caption=caption or '')
                       for kind,body,file_id,caption in conn.execute(
                           'SELECT kind,body,file_id,caption FROM project_blocks WHERE project_id=%s ORDER BY position', (identifier,))]
    value['screenshots'] = [dict(file_id=str(file_id),caption=caption or '') for file_id,caption in conn.execute(
        'SELECT file_id,caption FROM project_screenshots WHERE project_id=%s ORDER BY position', (identifier,))]
    return value


def _list(conn, public=False):
    ids = conn.execute("SELECT id FROM projects" + (" WHERE status='published'" if public else '') + ' ORDER BY sort_order,id').fetchall()
    return [_read(conn,row[0],public=public) for row in ids]


def list_projects(settings: Settings | None = None):
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return _list(conn)


def get_project(settings: Settings | None, identifier: int):
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return _read(conn,identifier)


def list_published(settings: Settings | None = None):
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return _list(conn,public=True)


def get_published(settings: Settings | None, identifier: int):
    with transaction(settings) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return _read(conn,identifier,public=True)


def _references(conn, value):
    identifiers = {item['file_id'] for item in value['blocks'] if item['kind']=='image'}
    identifiers.update(item['file_id'] for item in value['screenshots'])
    if value['cover_file_id']:
        identifiers.add(value['cover_file_id'])
    if identifiers:
        existing = {str(row[0]) for row in conn.execute('SELECT id FROM uploaded_files WHERE id=ANY(%s::uuid[]) ORDER BY id FOR KEY SHARE', (sorted(identifiers),))}
        if identifiers != existing:
            raise auth.invalid_request()


def _replace(conn, identifier, value):
    _references(conn,value)
    fields = FIELDS[:-2]
    conn.execute('UPDATE projects SET ' + ','.join(field+'=%s' for field in fields) +
                 ',updated_at=clock_timestamp() WHERE id=%s', tuple(value[field] for field in fields)+(identifier,))
    conn.execute('DELETE FROM project_blocks WHERE project_id=%s',(identifier,))
    conn.execute('DELETE FROM project_screenshots WHERE project_id=%s',(identifier,))
    for position,block in enumerate(value['blocks']):
        conn.execute('INSERT INTO project_blocks(project_id,position,kind,body,file_id,caption) VALUES (%s,%s,%s,%s,%s,%s)',
                     (identifier,position,block['kind'],block.get('body'),block.get('file_id'),block.get('caption')))
    for position,image in enumerate(value['screenshots']):
        conn.execute('INSERT INTO project_screenshots(project_id,position,file_id,caption) VALUES (%s,%s,%s,%s)',
                     (identifier,position,image['file_id'],image['caption']))


def _collection_lock(conn):
    conn.execute('SELECT pg_advisory_xact_lock(794675013004)')


def create_project(payload, settings: Settings | None = None):
    value = validate_project(payload)
    with transaction(settings) as conn:
        _collection_lock(conn)
        identifier = conn.execute('INSERT INTO projects(sort_order) SELECT coalesce(max(sort_order)+1,0) FROM projects RETURNING id').fetchone()[0]
        _replace(conn,identifier,value)
        return _read(conn,identifier)


def save_project(identifier, payload, settings: Settings | None = None):
    with transaction(settings) as conn:
        current = _read(conn,identifier,lock=True)
        value = validate_project(payload,published=current['status']=='published')
        _replace(conn,identifier,value)
        return _read(conn,identifier)


def publish_project(identifier, settings: Settings | None = None):
    with transaction(settings) as conn:
        current = _read(conn,identifier,lock=True)
        value = validate_project({field:current[field] for field in FIELDS},published=True)
        _references(conn,value)
        conn.execute("UPDATE projects SET status='published', published_at=coalesce(published_at,clock_timestamp()), updated_at=clock_timestamp() WHERE id=%s", (identifier,))
        return _read(conn,identifier)


def archive_project(identifier, settings: Settings | None = None):
    with transaction(settings) as conn:
        current = _read(conn,identifier,lock=True)
        if current['status'] != 'published':
            raise auth.AdminError(409,'project_conflict','项目当前状态不允许此操作。')
        conn.execute("UPDATE projects SET status='archived',updated_at=clock_timestamp() WHERE id=%s",(identifier,))
        return _read(conn,identifier)


def reorder_projects(payload, settings: Settings | None = None):
    if not isinstance(payload,dict) or set(payload) != {'ids'} or not isinstance(payload['ids'],list):
        raise auth.invalid_request()
    ids = payload['ids']
    if any(type(identifier) is not int or not 1 <= identifier <= 9223372036854775807 for identifier in ids) or len(set(ids)) != len(ids):
        raise auth.invalid_request()
    with transaction(settings) as conn:
        _collection_lock(conn)
        existing = [row[0] for row in conn.execute('SELECT id FROM projects ORDER BY id FOR UPDATE')]
        if set(existing) != set(ids):
            raise auth.invalid_request()
        for position,identifier in enumerate(ids):
            conn.execute('UPDATE projects SET sort_order=%s,updated_at=clock_timestamp() WHERE id=%s',(position,identifier))
        return _list(conn)
