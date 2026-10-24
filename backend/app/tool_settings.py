"""Fixed tool registry with atomic complete-configuration writes."""
from app import admin_auth as auth
from app.database import connection, transaction
from app.settings import Settings

REGISTRY = {**{f'grid_{i:02}': 'grid' for i in range(1, 10)}, 'dice': 'floating'}
FIELDS = {'tool_key', 'placement', 'is_visible', 'sort_order'}


def validate_tools(payload: object) -> list[dict]:
    """Validate without coercion; return grid order followed by the floating die."""
    if not isinstance(payload, dict) or set(payload) != {'tools'}:
        raise auth.invalid_request()
    items = payload['tools']
    if not isinstance(items, list) or len(items) != len(REGISTRY):
        raise auth.invalid_request()
    seen, grid_orders = set(), set()
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise auth.invalid_request()
        key, placement, visible, order = (item[name] for name in ('tool_key', 'placement', 'is_visible', 'sort_order'))
        if (not isinstance(key, str) or key not in REGISTRY or key in seen
                or placement != REGISTRY[key] or type(visible) is not bool or type(order) is not int):
            raise auth.invalid_request()
        if placement == 'grid':
            if not 0 <= order <= 8 or order in grid_orders:
                raise auth.invalid_request()
            grid_orders.add(order)
        elif order != 0:
            raise auth.invalid_request()
        seen.add(key)
        result.append(dict(item))
    return sorted(result, key=lambda item: (item['placement'] != 'grid', item['sort_order']))


def _read(conn, *, lock: bool = False) -> list[dict]:
    rows = conn.execute('SELECT tool_key, placement, is_visible, sort_order FROM tool_settings ORDER BY tool_key' +
                        (' FOR UPDATE' if lock else '')).fetchall()
    try:
        return validate_tools({'tools': [dict(zip(('tool_key', 'placement', 'is_visible', 'sort_order'), row)) for row in rows]})
    except auth.AdminError:
        # Missing rows, extra rows and corrupt placement/order are operational failures.
        raise auth.unavailable() from None


def load_tools(settings: Settings | None = None) -> list[dict]:
    with connection(settings) as conn:
        return _read(conn)


def save_tools(payload: object, settings: Settings | None = None) -> list[dict]:
    tools = validate_tools(payload)
    with transaction(settings) as conn:
        # All writers lock in stable key order, then validate the stored collection.
        # An incomplete database is never silently filled or replaced by defaults.
        _read(conn, lock=True)
        for item in tools:
            conn.execute('''UPDATE tool_settings SET is_visible=%s, sort_order=%s,
                updated_at=clock_timestamp() WHERE tool_key=%s''',
                         (item['is_visible'], item['sort_order'], item['tool_key']))
    return tools
