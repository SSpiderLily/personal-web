"""Public profile and authenticated profile editing."""
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool
from app import admin_auth as auth, profile
from app.admin_routes import AdminRoute
from app.content_request import json_content
from app.settings import Settings, get_settings

router = APIRouter(route_class=AdminRoute)


@router.get('/api/profile')
def public_profile(settings: Settings = Depends(get_settings)):
    return profile.load_profile(settings)


@router.get('/api/admin/profile')
def admin_profile(current: auth.AdminSession = Depends(auth.require_admin), settings: Settings = Depends(get_settings)):
    return profile.load_profile(settings)


@router.put('/api/admin/profile')
async def update_profile(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    payload = await json_content(request)
    return await run_in_threadpool(profile.save_profile, payload, settings)
