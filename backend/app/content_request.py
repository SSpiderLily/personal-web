"""Bounded JSON for content endpoints; existing small requests stay unchanged."""
import json
import math
from app import admin_auth as auth

CONTENT_LIMIT = 262144


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate key')
        value[key] = item
    return value


def _validate(value):
    if isinstance(value, str):
        if '\x00' in value:
            raise ValueError('Invalid string')
        value.encode('utf-8')
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite number')
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate(key)
            _validate(item)
    elif isinstance(value, list):
        for item in value:
            _validate(item)


async def json_content(request):
    body = bytearray()
    async for chunk in request.stream():
        if len(chunk) > CONTENT_LIMIT - len(body):
            raise auth.invalid_request()
        body.extend(chunk)
    try:
        value = json.loads(body, object_pairs_hook=_object)
        if not isinstance(value, dict):
            raise ValueError('Object required')
        _validate(value)
    except (ValueError, UnicodeError, RecursionError):
        raise auth.invalid_request() from None
    return value
