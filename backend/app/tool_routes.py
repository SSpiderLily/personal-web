"""Public and admin tool endpoints; mounted by the application entry point."""
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from app import admin_auth as auth, tool_settings
from app.admin_routes import AdminRoute, json_object
from app.settings import Settings, get_settings

router = APIRouter(route_class=AdminRoute)


@router.get('/api/tools')
def public_tools(settings: Settings = Depends(get_settings)):
    return {'tools': tool_settings.load_tools(settings)}


@router.get('/api/admin/tools')
def admin_tools(current: auth.AdminSession = Depends(auth.require_admin),
                settings: Settings = Depends(get_settings)):
    return {'tools': tool_settings.load_tools(settings)}


@router.put('/api/admin/tools')
async def update_tools(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write),
                       settings: Settings = Depends(get_settings)):
    payload = await json_object(request)
    return {'tools': await run_in_threadpool(tool_settings.save_tools, payload, settings)}
