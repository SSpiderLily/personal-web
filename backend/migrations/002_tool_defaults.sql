-- Fill only missing registry entries. Existing visibility and order are retained.
INSERT INTO tool_settings (tool_key, placement, is_visible, sort_order) VALUES
    ('grid_01', 'grid', true, 0),
    ('grid_02', 'grid', true, 1),
    ('grid_03', 'grid', true, 2),
    ('grid_04', 'grid', true, 3),
    ('grid_05', 'grid', true, 4),
    ('grid_06', 'grid', true, 5),
    ('grid_07', 'grid', true, 6),
    ('grid_08', 'grid', true, 7),
    ('grid_09', 'grid', true, 8),
    ('dice', 'floating', true, 0)
ON CONFLICT (tool_key) DO NOTHING;
