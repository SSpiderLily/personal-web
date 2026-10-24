"""Public profile and authenticated profile editing."""
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool
from app import admin_auth as auth, profile, projects
from app.admin_routes import AdminRoute
from app.content_request import json_content
from app.settings import Settings, get_settings

router = APIRouter(route_class=AdminRoute)


def with_projects(value, settings):
    return value | {'projects': [{'name': item['name'], 'description': item['summary']}
                                  for item in projects.list_published(settings)]}



@router.get('/api/profile')
def public_profile(settings: Settings = Depends(get_settings)):
    return with_projects(profile.load_profile(settings), settings)


@router.get('/api/admin/profile')
def admin_profile(current: auth.AdminSession = Depends(auth.require_admin), settings: Settings = Depends(get_settings)):
    return with_projects(profile.load_profile(settings), settings)


@router.put('/api/admin/profile')
async def update_profile(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    payload = await json_content(request)
    value = await run_in_threadpool(profile.save_profile, payload, settings)
    return await run_in_threadpool(with_projects, value, settings)
