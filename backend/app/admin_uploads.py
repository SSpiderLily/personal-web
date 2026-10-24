"""Private image uploads: authenticate, bound bytes, decode, store, then commit.

There is deliberately no static directory mount. Only metadata-backed, live-admin
reads are available. A crash can leave an orphan; the read path never serves it.
"""
from contextlib import contextmanager
import io
import os
from pathlib import Path
import stat
from uuid import UUID, uuid4
import warnings

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app import admin_auth as auth
from app.admin_routes import AdminRoute
from app.database import connection, transaction
from app.settings import Settings, get_settings

FILE_LIMIT = 10 * 1024 * 1024
BODY_LIMIT = FILE_LIMIT + 64 * 1024
PIXEL_LIMIT = 40_000_000
FORMATS = {'PNG': ('image/png', {'.png'}), 'JPEG': ('image/jpeg', {'.jpg', '.jpeg'}),
           'WEBP': ('image/webp', {'.webp'})}
router = APIRouter(prefix='/api/admin/files', route_class=AdminRoute)


class CompleteMultipartParser(MultiPartParser):
    """Starlette accepts partial forms; uploads require a terminal boundary."""
    complete = False

    def on_end(self):
        self.complete = True

    async def parse(self):
        try:
            form = await super().parse()
            if not self.complete:
                raise MultiPartException('Incomplete multipart data')
            return form
        except BaseException:
            # Includes an unfinished part that has not entered FormData yet.
            for file in self._files_to_close_on_error:
                try:
                    file.close()
                except OSError:
                    pass  # Continue cleanup; preserve the original parse/storage error.
            raise


def unavailable():
    return auth.AdminError(503, 'upload_unavailable', '图片服务暂时不可用，请稍后重试。')


def too_large():
    return auth.AdminError(413, 'file_too_large', '图片或请求超过大小限制。')


def invalid_image():
    return auth.AdminError(400, 'invalid_image', '图片内容不完整或不符合尺寸要求。')


def unsupported():
    return auth.AdminError(415, 'unsupported_image', '仅支持静态 PNG、JPEG 和 WebP 图片，格式声明须一致。')


def configured_path(settings):
    if settings.upload_dir is None:
        raise unavailable()
    path = Path(settings.upload_dir)
    if not path.is_absolute() or '..' in path.parts:
        raise unavailable()
    # Purely lexical: collapse POSIX's special // anchor without following any
    # upload symlinks. Storage still opens every component with O_NOFOLLOW.
    path = Path('/', *path.parts[1:])
    # Runtime only: a storage misconfiguration must not disable public APIs.
    release = Path(__file__).resolve().parents[2]
    if settings.app_env == 'production' and path.is_relative_to(release):
        raise unavailable()
    return path


@contextmanager
def storage_directory(settings, *, create=False):
    """Traverse each component with no-follow and retain a directory descriptor.

    The final private directory is owned by this process user, mode 0700. Parent
    paths may be shared (e.g. /private/tmp), but may never be symbolic links.
    File operations stay relative to the retained descriptor, avoiding path races.
    """
    path = configured_path(settings)
    descriptor = None
    try:
        descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        for part in path.parts[1:]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass  # Concurrent first upload; the no-follow open checks it.
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise unavailable()
        yield descriptor
    except OSError:
        raise unavailable() from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                raise unavailable() from None


def complete_png(data):
    """Pillow verify/load skip the IEND CRC; require the entire terminal chunk."""
    offset = 8  # PNG signature; the decoder has already confirmed actual format.
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        end = offset + 12 + length
        if end > len(data):
            break
        if data[offset + 4:offset + 8] == b'IEND':
            if data[offset:end] == b'\x00\x00\x00\x00IEND\xaeB`\x82':
                return
            break
        offset = end
    raise invalid_image()


def decode_image(data, name, media_type):
    if not data:
        raise invalid_image()
    if len(data) > FILE_LIMIT:
        raise too_large()
    suffix = Path(name).suffix.lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.webp'} or media_type not in {'image/png', 'image/jpeg', 'image/webp'}:
        raise unsupported()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                actual = image.format
                if actual not in FORMATS:
                    raise unsupported()
                actual_type, extensions = FORMATS[actual]
                if media_type != actual_type or suffix not in extensions or getattr(image, 'n_frames', 1) != 1:
                    raise unsupported()
                width, height = image.size
                if width * height > PIXEL_LIMIT:
                    raise invalid_image()
                if actual == 'PNG':
                    complete_png(data)
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()  # Header/verify alone does not prove complete decoding.
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise invalid_image() from None
    return actual_type, width, height


def metadata(identifier, media_type, byte_size, width, height):
    return {'id': str(identifier), 'media_type': media_type, 'byte_size': byte_size,
            'width': width, 'height': height, 'url': '/api/admin/files/' + str(identifier)}


def save_image(settings, data, original_name, media_type):
    media_type, width, height = decode_image(data, original_name, media_type)
    identifier = uuid4()
    key = str(identifier)
    with storage_directory(settings, create=True) as directory:
        created = False
        try:
            descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            created = True
            with os.fdopen(descriptor, 'wb') as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            with transaction(settings) as conn:
                conn.execute('''INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)''', (identifier, key, original_name, media_type, len(data), width, height))
        except Exception:
            if created:
                try:
                    os.unlink(key, dir_fd=directory)
                except OSError:
                    pass  # An unlinked/unremovable orphan has no committed metadata.
            raise unavailable() from None
    return metadata(identifier, media_type, len(data), width, height)


async def bounded_body(request):
    length = request.headers.get('content-length')
    if length is not None:
        if not length.isascii() or not length.isdigit():
            raise auth.invalid_request()
        if len(length) > 12 or int(length) > BODY_LIMIT:
            raise too_large()
    body = bytearray()
    async for chunk in request.stream():
        if len(chunk) > BODY_LIMIT - len(body):
            raise too_large()
        body.extend(chunk)
    return bytes(body)


@router.post('', status_code=201)
async def upload(request: Request, current: auth.AdminSession = Depends(auth.require_admin_upload),
                 settings: Settings = Depends(get_settings)):
    configured_path(settings)
    body = await bounded_body(request)
    async def stream():
        yield body
    # Parsing starts only after both auth and the entire request size bound.
    try:
        form = await CompleteMultipartParser(request.headers, stream(), max_files=1, max_fields=0).parse()
    except OSError:
        raise unavailable() from None
    except (MultiPartException, ValueError, UnicodeError):
        raise auth.invalid_request() from None
    try:
        items = form.multi_items()
        if len(items) != 1 or items[0][0] != 'file' or not isinstance(items[0][1], UploadFile):
            raise auth.invalid_request()
        file = items[0][1]
        name = file.filename
        if not name or len(name) > 1024 or '\x00' in name:
            raise auth.invalid_request()
        data = await file.read(FILE_LIMIT + 1)
        if len(data) > FILE_LIMIT:
            raise too_large()
    except BaseException as error:
        try:
            await form.close()
        except OSError:
            pass  # Cleanup must not replace a size/validation error or cancellation.
        if isinstance(error, OSError):
            raise unavailable() from None
        raise
    try:
        await form.close()
    except OSError:
        raise unavailable() from None
    # Release temporary storage before committing any final file/metadata.
    return await run_in_threadpool(save_image, settings, data, name, file.content_type)


def load_image(settings, identifier, *, conn=None):
    configured_path(settings)
    if conn is None:
        with connection(settings) as owned:
            row = owned.execute('SELECT storage_key,media_type,byte_size FROM uploaded_files WHERE id=%s', (identifier,)).fetchone()
    else:
        row = conn.execute('SELECT storage_key,media_type,byte_size FROM uploaded_files WHERE id=%s', (identifier,)).fetchone()
    if row is None:
        raise auth.AdminError(404, 'file_not_found', '图片不存在。')
    key, media_type, size = row
    if key != str(identifier) or media_type not in {'image/png', 'image/jpeg', 'image/webp'} or not 1 <= size <= FILE_LIMIT:
        raise unavailable()
    with storage_directory(settings) as directory:
        try:
            descriptor = os.open(key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(descriptor, 'rb') as file:
                info = os.fstat(file.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size != size):
                    raise unavailable()
                data = file.read(FILE_LIMIT + 1)
                if len(data) != size:
                    raise unavailable()
        except OSError:
            raise unavailable() from None
    return Response(data, media_type=media_type, headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})


@router.get('/{file_id}')
def read(file_id: str, current: auth.AdminSession = Depends(auth.require_admin),
         settings: Settings = Depends(get_settings)):
    try:
        identifier = UUID(file_id)
    except ValueError:
        raise auth.invalid_request() from None
    return load_image(settings, identifier)
