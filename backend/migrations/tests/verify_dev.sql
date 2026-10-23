-- Fixtures, including explicit IDs, are rolled back and never become application data.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SET LOCAL search_path = public, pg_catalog;
SET LOCAL personal_web.schema_test = 'rollback-only';
DO $guard$
BEGIN
    IF current_database() <> 'personal_web_dev' OR current_user <> 'personal_web_dev' THEN
        RAISE EXCEPTION 'Development database/account required';
    END IF;
    IF EXISTS (SELECT FROM admin_accounts) OR EXISTS (SELECT FROM projects)
       OR EXISTS (SELECT FROM uploaded_files) OR EXISTS (SELECT FROM site_profile)
       OR EXISTS (SELECT FROM tool_settings) OR EXISTS (SELECT FROM site_daily_visitors)
       OR EXISTS (SELECT FROM project_daily_visitors) THEN
        RAISE EXCEPTION 'Initial-schema verification requires empty business tables';
    END IF;
END
$guard$;
\ir assert_initial_schema.sql
ROLLBACK;
