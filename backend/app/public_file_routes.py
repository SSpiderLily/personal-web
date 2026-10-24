"""Anonymous image reads require a current public content reference."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app import admin_auth as auth, admin_uploads
from app.admin_routes import AdminRoute
from app.database import transaction
from app.file_publication import is_public_reference
from app.settings import Settings, get_settings

router = APIRouter(prefix='/api/files', route_class=AdminRoute)


def not_found():
    return auth.AdminError(404, 'file_not_found', '图片不存在。')


@router.get('/{file_id}')
def read(file_id: str, settings: Settings = Depends(get_settings)):
    try:
        identifier = UUID(file_id)
    except ValueError:
        raise not_found() from None
    with transaction(settings) as conn:
        # The first query establishes one snapshot for reference authorization
        # and file metadata. Concurrent commits affect the following request.
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if not is_public_reference(conn, identifier):
            raise not_found()
        return admin_uploads.load_image(settings, identifier, conn=conn)
