-- Preserve current public display fields without altering prior migrations.
ALTER TABLE projects ADD COLUMN category text NOT NULL DEFAULT '';
ALTER TABLE projects ADD COLUMN features text[] NOT NULL DEFAULT ARRAY[]::text[];
ALTER TABLE projects ADD COLUMN cover_alt text NOT NULL DEFAULT '';
CREATE TABLE content_bootstraps (
    key text PRIMARY KEY,
    project_id bigint NOT NULL REFERENCES projects(id) ON DELETE RESTRICT
);
