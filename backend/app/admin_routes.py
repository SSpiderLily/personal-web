"""Admin HTTP contract. Errors contain neither request bodies nor driver details."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
import psycopg
from starlette.concurrency import run_in_threadpool

from app import admin_auth as auth
from app.database import DatabaseTargetError, DatabaseUnavailable
from app.settings import Settings


class AdminRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                response = await handler(request)
            except (DatabaseUnavailable, DatabaseTargetError, psycopg.Error):
                error = auth.unavailable()
                response = JSONResponse({'error': {'code': error.code, 'message': error.message}}, status_code=error.status)
            except (auth.AdminError, RequestValidationError) as error:
                if isinstance(error, RequestValidationError):
                    error = auth.invalid_request()
                response = JSONResponse({'error': {'code': error.code, 'message': error.message}}, status_code=error.status)
            response.headers['Cache-Control'] = 'no-store'
            return response
        return safe_handler


router = APIRouter(prefix='/api/admin', route_class=AdminRoute)


async def json_object(request: Request) -> dict:
    """Bound bytes before parsing, avoiding FastAPI validation input echo."""
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4096:
            raise auth.invalid_request()
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise auth.invalid_request() from None
    if not isinstance(value, dict):
        raise auth.invalid_request()
    return value


@router.get('/session')
def session(request: Request, settings: Settings = Depends(auth.check_admin_access)):
    current = auth.current_session(request, settings)
    return current.response() if current else auth.ANONYMOUS


@router.post('/login')
async def login(request: Request, settings: Settings = Depends(auth.require_write_origin)):
    value = await json_object(request)
    username, password = value.get('username'), value.get('password')
    if (set(value) != {'username', 'password'} or not isinstance(username, str)
            or not 1 <= len(username) <= 64 or username != username.strip()
            or not isinstance(password, str) or not 1 <= len(password) <= 128):
        raise auth.invalid_request()
    try:
        username.encode('utf-8')
        password.encode('utf-8')
    except UnicodeError:
        raise auth.invalid_request() from None
    if '\x00' in username or '\x00' in password:
        raise auth.invalid_request()
    previous = await run_in_threadpool(auth.current_session, request, settings)
    if previous is not None:
        auth.check_csrf(request, previous)
    current = await run_in_threadpool(auth.authenticate, settings, username, password, request.cookies.get(auth.COOKIE))
    response = JSONResponse(current.response())
    response.set_cookie(auth.COOKIE, current.token, max_age=settings.admin_session_hours * 3600,
                        path=auth.COOKIE_PATH, secure=settings.app_env == 'production', httponly=True, samesite='strict')
    return response


@router.post('/logout')
async def logout(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write),
                 settings: Settings = Depends(auth.check_admin_access)):
    await json_object(request)
    await run_in_threadpool(auth.revoke_session, settings, current)
    response = JSONResponse(auth.ANONYMOUS)
    response.delete_cookie(auth.COOKIE, path=auth.COOKIE_PATH, secure=settings.app_env == 'production', httponly=True, samesite='strict')
    return response


@router.get('/overview')
def overview(current: auth.AdminSession = Depends(auth.require_admin)):
    return {'admin': current.admin, 'modules': [
        {'id': key, 'label': label, 'status': 'ready'}
        for key, label in (('projects', '项目管理'), ('statistics', '访问统计'), ('content', '网站内容'), ('tools', '小工具管理'))]}
