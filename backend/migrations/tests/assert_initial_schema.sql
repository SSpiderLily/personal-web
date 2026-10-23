-- Run inside a transaction and roll it back. Never commit these fixtures.
DO $test$
DECLARE
    file_a uuid := '00000000-0000-4000-8000-000000000091';
    file_b uuid := '00000000-0000-4000-8000-000000000092';
    visitor uuid := '00000000-0000-4000-8000-000000000093';
    n integer;
BEGIN
    ASSERT current_setting('personal_web.schema_test', true) = 'rollback-only', 'Use transaction-wrapped verify_dev.sql';
    ASSERT to_regclass('projects') IS NOT NULL, 'initial schema is missing';
    INSERT INTO admin_accounts(id,username,password_hash) VALUES(1,'schema-test','not-a-real-password-hash');
    BEGIN
        INSERT INTO admin_accounts(id,username,password_hash) VALUES(2,'other','hash');
        RAISE EXCEPTION 'singleton account constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO admin_accounts(id,username,password_hash) VALUES(1,'duplicate','hash');
        RAISE EXCEPTION 'account primary key missing';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        INSERT INTO admin_sessions(token_hash,admin_id,expires_at) VALUES(decode('01','hex'),1,now()+interval '1 hour');
        RAISE EXCEPTION 'session digest length constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO admin_sessions(token_hash,admin_id,expires_at) VALUES(decode(repeat('ab',32),'hex'),1,now()-interval '1 hour');
        RAISE EXCEPTION 'session expiry constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    INSERT INTO admin_sessions(token_hash,admin_id,expires_at) VALUES(decode(repeat('ab',32),'hex'),1,now()+interval '1 hour');
    INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height) VALUES
        (file_a,'schema-test/a.png','a.png','image/png',10,1,1),
        (file_b,'schema-test/b.png','b.png','image/png',10,1,1);
    BEGIN
        INSERT INTO uploaded_files(storage_key,original_name,media_type,byte_size,width,height) VALUES('schema-test/invalid','x','image/png',0,1,1);
        RAISE EXCEPTION 'file size constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    INSERT INTO projects(id) VALUES(-91001),(-91002);
    ASSERT (SELECT name='' AND status='draft' FROM projects WHERE id=-91001), 'incomplete draft cannot be saved';
    BEGIN
        UPDATE projects SET status='invalid' WHERE id=-91001;
        RAISE EXCEPTION 'project status constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        UPDATE projects SET cover_file_id='00000000-0000-4000-8000-999999999999' WHERE id=-91001;
        RAISE EXCEPTION 'cover foreign key missing';
    EXCEPTION WHEN foreign_key_violation OR restrict_violation THEN NULL; END;
    INSERT INTO project_blocks(id,project_id,position,kind,body) VALUES(-91001,-91001,0,'text',''),(-91002,-91001,1,'text','second');
    BEGIN
        INSERT INTO project_blocks(id,project_id,position,kind,body,file_id) VALUES(-91003,-91001,2,'text','body',file_a);
        RAISE EXCEPTION 'text/image mutual exclusion missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO project_blocks(id,project_id,position,kind) VALUES(-91003,-91001,2,'image');
        RAISE EXCEPTION 'image reference requirement missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO project_blocks(id,project_id,position,kind,body) VALUES(-91003,-91001,0,'text','duplicate position');
        RAISE EXCEPTION 'block position uniqueness missing';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    SET CONSTRAINTS project_blocks_project_position_key DEFERRED;
    UPDATE project_blocks SET position=1 WHERE id=-91001;
    UPDATE project_blocks SET position=0 WHERE id=-91002;
    SET CONSTRAINTS project_blocks_project_position_key IMMEDIATE;
    INSERT INTO project_screenshots(id,project_id,file_id,position) VALUES(-91001,-91001,file_a,0),(-91002,-91001,file_b,1);
    SET CONSTRAINTS project_screenshots_project_position_key DEFERRED;
    UPDATE project_screenshots SET position=1 WHERE id=-91001;
    UPDATE project_screenshots SET position=0 WHERE id=-91002;
    SET CONSTRAINTS project_screenshots_project_position_key IMMEDIATE;
    BEGIN
        INSERT INTO project_screenshots(id,project_id,file_id,position) VALUES(-91003,-91001,file_a,2);
        RAISE EXCEPTION 'duplicate screenshot constraint missing';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        DELETE FROM uploaded_files WHERE id=file_a;
        RAISE EXCEPTION 'referenced file deletion was allowed';
    EXCEPTION WHEN foreign_key_violation OR restrict_violation THEN NULL; END;
    INSERT INTO site_profile(id,name,title,introduction) VALUES(1,'name','title','intro');
    BEGIN
        INSERT INTO site_profile(id,name,title,introduction) VALUES(2,'name','title','intro');
        RAISE EXCEPTION 'profile singleton constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        UPDATE site_profile SET contacts='{}'::jsonb WHERE id=1;
        RAISE EXCEPTION 'contacts array constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        UPDATE site_profile SET social_links='null'::jsonb WHERE id=1;
        RAISE EXCEPTION 'social links array constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    INSERT INTO tool_settings(tool_key,placement) VALUES('schema-test','grid');
    BEGIN
        UPDATE tool_settings SET placement='elsewhere' WHERE tool_key='schema-test';
        RAISE EXCEPTION 'tool placement constraint missing';
    EXCEPTION WHEN check_violation THEN NULL; END;
    INSERT INTO site_daily_visitors VALUES('2000-01-01',visitor),('2000-01-02',visitor);
    INSERT INTO site_daily_visitors VALUES('2000-01-01',visitor) ON CONFLICT DO NOTHING;
    SELECT count(*) INTO n FROM site_daily_visitors WHERE visitor_id=visitor;
    ASSERT n=2, 'same-day visitor deduplication failed';
    SELECT count(DISTINCT visitor_id) INTO n FROM site_daily_visitors WHERE visit_date BETWEEN '2000-01-01' AND '2000-01-02' AND visitor_id=visitor;
    ASSERT n=1, 'cross-day visitor deduplication failed';
    INSERT INTO project_daily_visitors VALUES(-91002,'2000-01-01',visitor),(-91002,'2000-01-02',visitor);
    INSERT INTO project_daily_visitors VALUES(-91002,'2000-01-01',visitor) ON CONFLICT DO NOTHING;
    SELECT count(DISTINCT visitor_id) INTO n FROM project_daily_visitors WHERE project_id=-91002;
    ASSERT n=1, 'project visitor deduplication failed';
    BEGIN
        DELETE FROM projects WHERE id=-91002;
        RAISE EXCEPTION 'project with history was deleted';
    EXCEPTION WHEN foreign_key_violation OR restrict_violation THEN NULL; END;
    DELETE FROM projects WHERE id=-91001;
    ASSERT NOT EXISTS(SELECT FROM project_blocks WHERE project_id=-91001), 'block cascade missing';
    ASSERT NOT EXISTS(SELECT FROM project_screenshots WHERE project_id=-91001), 'screenshot cascade missing';
    ASSERT EXISTS(SELECT FROM uploaded_files WHERE id=file_a), 'project deletion removed physical file metadata';
    DELETE FROM admin_accounts WHERE id=1;
    ASSERT NOT EXISTS(SELECT FROM admin_sessions), 'session cascade missing';
    RAISE NOTICE 'PASS: singleton, sessions, file metadata/FK protection, incomplete drafts, block types, deferred sorting, screenshot uniqueness, profile JSON, tool placement, interval visitor deduplication and cascades';
END
$test$;
