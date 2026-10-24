"""Public project reads and authenticated project management."""
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool
from app import admin_auth as auth, projects
from app.admin_routes import AdminRoute
from app.content_request import json_content
from app.settings import Settings, get_settings

router = APIRouter(route_class=AdminRoute)


@router.get('/api/projects')
def public_projects(settings: Settings = Depends(get_settings)):
    return {'projects': projects.list_published(settings)}


@router.get('/api/projects/{identifier}')
def public_project(identifier: int, settings: Settings = Depends(get_settings)):
    return {'project': projects.get_published(settings,identifier)}


@router.get('/api/admin/projects')
def admin_projects(current: auth.AdminSession = Depends(auth.require_admin), settings: Settings = Depends(get_settings)):
    return {'projects': projects.list_projects(settings)}


@router.post('/api/admin/projects')
async def create(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    return {'project': await run_in_threadpool(projects.create_project, await json_content(request), settings)}


@router.put('/api/admin/projects/order')
async def reorder(request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    return {'projects': await run_in_threadpool(projects.reorder_projects, await json_content(request), settings)}


@router.get('/api/admin/projects/{identifier}')
def admin_project(identifier: int, current: auth.AdminSession = Depends(auth.require_admin), settings: Settings = Depends(get_settings)):
    return {'project': projects.get_project(settings,identifier)}


@router.put('/api/admin/projects/{identifier}')
async def save(identifier: int, request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    return {'project': await run_in_threadpool(projects.save_project,identifier, await json_content(request),settings)}


async def _action(request, identifier, operation, settings):
    if await json_content(request) != {}:
        raise auth.invalid_request()
    return {'project': await run_in_threadpool(operation,identifier,settings)}


@router.post('/api/admin/projects/{identifier}/publish')
async def publish(identifier: int, request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    return await _action(request,identifier,projects.publish_project,settings)


@router.post('/api/admin/projects/{identifier}/archive')
async def archive(identifier: int, request: Request, current: auth.AdminSession = Depends(auth.require_admin_write), settings: Settings = Depends(get_settings)):
    return await _action(request,identifier,projects.archive_project,settings)
