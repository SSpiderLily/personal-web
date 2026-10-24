"""Public image references, evaluated inside the caller's database snapshot."""


def is_public_reference(conn, identifier):
    """Only current published projects and the current profile expose images.

    Do not open a second connection: the caller owns transaction consistency
    between this decision and metadata-backed storage loading.
    """
    return conn.execute('''SELECT
        EXISTS (SELECT 1 FROM projects WHERE status='published' AND cover_file_id=%s)
        OR EXISTS (
            SELECT 1 FROM project_blocks b JOIN projects p ON p.id=b.project_id
            WHERE p.status='published' AND b.kind='image' AND b.file_id=%s)
        OR EXISTS (
            SELECT 1 FROM project_screenshots s JOIN projects p ON p.id=s.project_id
            WHERE p.status='published' AND s.file_id=%s)
        OR EXISTS (SELECT 1 FROM site_profile WHERE avatar_file_id=%s)
        ''', (identifier, identifier, identifier, identifier)).fetchone()[0]
