"""Database-backed admin sessions and reusable FastAPI authorization dependencies.

The ASGI server must restore HTTPS only from explicitly trusted reverse proxies.
This module never reads forwarded headers. No account is created on import/startup.
"""
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
from ipaddress import ip_address
import re
import secrets

from fastapi import Depends, Request
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.database import connection, transaction
from app.settings import Settings, get_settings

COOKIE = 'personal_web_session'
COOKIE_PATH = '/api/admin'
PASSWORDS = PasswordHash.recommended()
# Perform the same Argon2 work when the username is absent.
_DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
_TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{43}\Z')
ANONYMOUS = {'authenticated': False, 'admin': None, 'csrf_token': None, 'expires_at': None}


class AdminError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)


def unavailable():
    return AdminError(503, 'admin_unavailable', '管理服务暂时不可用，请稍后重试。')


def unauthenticated():
    return AdminError(401, 'unauthenticated', '请先登录。')


def invalid_request():
    return AdminError(400, 'invalid_request', '请求格式不正确。')


def check_admin_access(request: Request, settings: Settings = Depends(get_settings)) -> Settings:
    """Fail closed for production administration, independently of public APIs."""
    if settings.app_env == 'production':
        if not settings.admin_allowed_origins:
            raise unavailable()
        origin = f'{request.url.scheme}://{request.url.netloc}'
        if settings.production_mode == 'http_ssh':
            try:
                loopback = request.client is not None and ip_address(request.client.host).is_loopback
            except ValueError:
                loopback = False
            allowed = request.url.scheme == 'http' and loopback
        else:
            allowed = request.url.scheme == 'https'
        if not allowed or origin not in settings.admin_allowed_origins:
            raise AdminError(403, 'origin_forbidden', '此来源不能访问管理服务。')
    origin_header = request.headers.get('origin')
    if origin_header is not None and (origin_header not in settings.admin_allowed_origins
            or (settings.app_env == 'production' and settings.production_mode == 'http_ssh'
                and origin_header != f'{request.url.scheme}://{request.url.netloc}')):
        raise AdminError(403, 'origin_forbidden', '此来源不能访问管理服务。')
    return settings


def require_write_origin(request: Request, settings: Settings = Depends(check_admin_access)) -> Settings:
    if (request.headers.get('x-admin-request') != '1'
            or request.headers.get('origin') not in settings.admin_allowed_origins):
        raise AdminError(403, 'origin_forbidden', '此来源不能执行管理操作。')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise invalid_request()
    return settings


def require_visit_origin(request: Request, settings: Settings = Depends(get_settings)) -> Settings:
    """Anonymous visits have their own public origin; this grants no admin access."""
    if settings.app_env != 'production' or settings.production_mode != 'http_ssh':
        return require_write_origin(request, check_admin_access(request, settings))
    origin = f'{request.url.scheme}://{request.url.netloc}'
    if origin != settings.public_origin or request.headers.get('origin') != settings.public_origin:
        check_admin_access(request, settings)
        if request.headers.get('origin') != origin:
            raise AdminError(403, 'origin_forbidden', '此来源不能记录访问。')
    if request.headers.get('x-admin-request') != '1':
        raise AdminError(403, 'origin_forbidden', '此来源不能记录访问。')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise invalid_request()
    return settings


def secure_cookie(settings: Settings) -> bool:
    return settings.app_env == 'production' and settings.production_mode != 'http_ssh'


def token_digest(token: str | None) -> bytes | None:
    if token is None or not _TOKEN_PATTERN.fullmatch(token):
        return None
    return hashlib.sha256(token.encode('ascii')).digest()


@dataclass(frozen=True)
class AdminSession:
    admin_id: int
    username: str
    expires_at: datetime
    token: str = field(repr=False)

    @property
    def csrf_token(self) -> str:
        return hmac.new(self.token.encode('ascii'), b'personal-web-admin-csrf-v1', hashlib.sha256).hexdigest()

    @property
    def admin(self) -> dict:
        return {'id': self.admin_id, 'username': self.username}

    def response(self) -> dict:
        return {'authenticated': True, 'admin': self.admin, 'csrf_token': self.csrf_token,
                'expires_at': self.expires_at.isoformat()}


def current_session(request: Request, settings: Settings) -> AdminSession | None:
    token = request.cookies.get(COOKIE)
    digest = token_digest(token)
    if digest is None:
        return None
    with connection(settings) as conn:
        row = conn.execute('''SELECT a.id, a.username, s.expires_at
            FROM admin_sessions s JOIN admin_accounts a ON a.id=s.admin_id
            WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()''', (digest,)).fetchone()
    return AdminSession(*row, token) if row else None


def require_admin(request: Request, settings: Settings = Depends(check_admin_access)) -> AdminSession:
    """Reusable read authorization; always checks the database expiry/revocation."""
    session = current_session(request, settings)
    if session is None:
        raise unauthenticated()
    return session


def require_admin_write(request: Request, settings: Settings = Depends(require_write_origin)) -> AdminSession:
    """Reusable write authorization: trusted Origin, JSON, live session, bound CSRF."""
    session = current_session(request, settings)
    if session is None:
        raise unauthenticated()
    check_csrf(request, session)
    return session


def require_admin_upload(request: Request, settings: Settings = Depends(check_admin_access)) -> AdminSession:
    """Upload-only protection; called before reading any multipart/body bytes."""
    if (request.headers.get('x-admin-request') != '1'
            or request.headers.get('origin') not in settings.admin_allowed_origins):
        raise AdminError(403, 'origin_forbidden', '此来源不能执行管理操作。')
    session = current_session(request, settings)
    if session is None:
        raise unauthenticated()
    check_csrf(request, session)
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'multipart/form-data':
        raise invalid_request()
    return session


def check_csrf(request: Request, session: AdminSession) -> None:
    supplied = request.headers.get('x-csrf-token', '')
    if not hmac.compare_digest(supplied.encode('utf-8'), session.csrf_token.encode('ascii')):
        raise AdminError(403, 'csrf_failed', '安全验证失败，请刷新后重试。')


def authenticate(settings: Settings, username: str, password: str, previous: str | None) -> AdminSession:
    with transaction(settings) as conn:
        row = conn.execute('SELECT id, username, password_hash FROM admin_accounts WHERE username=%s', (username,)).fetchone()
        try:
            valid = PASSWORDS.verify(password, row[2] if row else _DUMMY_HASH)
        except UnknownHashError:
            raise unavailable() from None
        if not valid or row is None:
            raise AdminError(401, 'invalid_credentials', '账号或密码不正确。')
        previous_hash = token_digest(previous)
        if previous_hash is not None:
            conn.execute('UPDATE admin_sessions SET revoked_at=clock_timestamp() WHERE token_hash=%s AND revoked_at IS NULL', (previous_hash,))
        token = secrets.token_urlsafe(32)
        expires_at = conn.execute('''INSERT INTO admin_sessions(token_hash,admin_id,expires_at)
            VALUES (%s,%s,clock_timestamp() + %s * interval '1 hour') RETURNING expires_at''',
            (token_digest(token), row[0], settings.admin_session_hours)).fetchone()[0]
    return AdminSession(row[0], row[1], expires_at, token)


def revoke_session(settings: Settings, session: AdminSession) -> None:
    with transaction(settings) as conn:
        row = conn.execute('''UPDATE admin_sessions SET revoked_at=clock_timestamp()
            WHERE token_hash=%s AND revoked_at IS NULL AND expires_at>clock_timestamp() RETURNING admin_id''',
            (token_digest(session.token),)).fetchone()
        if row is None:
            raise unauthenticated()
