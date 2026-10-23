-- psql -X -v ON_ERROR_STOP=1 -v migration_checksum=<SHA-256 of 001_admin_schema.sql> -f apply_dev.sql
-- Uses the configured connection; it must be the development database/account.
\set ON_ERROR_STOP on
\if :{?migration_checksum}
\else
    DO $error$ BEGIN RAISE EXCEPTION 'Missing migration_checksum; no changes made'; END $error$;
\endif
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = public, pg_catalog;
DO $guard$
BEGIN
    IF current_database() <> 'personal_web_dev' OR current_user <> 'personal_web_dev' THEN
        RAISE EXCEPTION 'Development database/account required; refusing migration';
    END IF;
END
$guard$;
SELECT :'migration_checksum' ~ '^[0-9a-f]{64}$' AS valid_checksum \gset
\if :valid_checksum
\else
    DO $error$ BEGIN RAISE EXCEPTION 'Invalid SHA-256 checksum; no changes made'; END $error$;
\endif
-- Serialize migration attempts before creating the tracking table.
SELECT pg_advisory_xact_lock(794675013001);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version varchar(100) PRIMARY KEY,
    checksum varchar(64) NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);
SELECT EXISTS (
    SELECT FROM schema_migrations WHERE version = '001_admin_schema' AND checksum <> :'migration_checksum'
) AS checksum_mismatch,
EXISTS (
    SELECT FROM schema_migrations WHERE version = '001_admin_schema'
) AS already_applied \gset
\if :checksum_mismatch
    DO $error$ BEGIN RAISE EXCEPTION 'Previously applied migration has a different checksum; refusing changes'; END $error$;
\endif
\if :already_applied
    \echo '001_admin_schema already applied; no schema or data changes.'
\else
    \ir 001_admin_schema.sql
    INSERT INTO schema_migrations(version, checksum) VALUES ('001_admin_schema', :'migration_checksum');
\endif
COMMIT;
