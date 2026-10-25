"""7A router; the sole anonymous statistics write exception is POST /visits.

Not mounted by this module. Public event hooks and statistics UI belong to 7B.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import admin_auth as auth, statistics, visitors
from app.admin_routes import AdminRoute, json_object
from app.settings import Settings

router = APIRouter(prefix='/api/admin', route_class=AdminRoute)


@router.post('/visits')
async def collect_visit(request: Request, settings: Settings = Depends(auth.require_write_origin)):
    value = await json_object(request)
    kind = value.get('kind')
    project_id = value.get('project_id')
    if not ((kind == 'website' and set(value) == {'kind'}) or
            (kind == 'project' and set(value) == {'kind', 'project_id'}
             and type(project_id) is int and 0 < project_id < 2**63)):
        raise auth.invalid_request()
    # The browser sends the existing Path=/api/admin session cookie here.
    # Client-provided identity/preview flags are never trusted for exclusion.
    current = await run_in_threadpool(auth.current_session, request, settings)
    if current is not None:
        return {'recorded': False}
    visitor, fresh = visitors.resolve_visitor(request.cookies.get(visitors.COOKIE))
    recorded = await run_in_threadpool(visitors.record_visit, settings, kind, visitor, project_id)
    response = JSONResponse({'recorded': recorded})
    if recorded and fresh:
        response.set_cookie(visitors.COOKIE, str(visitor), max_age=visitors.COOKIE_MAX_AGE,
                            path=visitors.COOKIE_PATH, secure=settings.app_env == 'production',
                            httponly=True, samesite='strict')
    return response


@router.get('/statistics')
def get_statistics(request: Request, current: auth.AdminSession = Depends(auth.require_admin),
                   settings: Settings = Depends(auth.check_admin_access)):
    query = request.query_params
    values = query.getlist('days')
    if set(query) - {'days'} or len(values) > 1 or (values and values[0] not in ('7', '30')):
        raise auth.invalid_request()
    return statistics.read_statistics(settings, int(values[0]) if values else 7)
