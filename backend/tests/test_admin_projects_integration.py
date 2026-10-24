"""Project transactions and HTTP contracts on the owned temporary PostgreSQL."""
import copy
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from uuid import uuid4
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import database, migrate, projects, admin_auth as auth
from app.admin_routes import router as auth_router
from test_admin_projects import payload


@unittest.skipUnless(os.environ.get('APP_RUN_DB_TESTS') == '1','run isolated PostgreSQL projects tests')
class ProjectIntegrationTests(unittest.TestCase):
    def setUp(self):
        with database.transaction() as conn:
            conn.execute('DROP SCHEMA public CASCADE'); conn.execute('CREATE SCHEMA public')
        migrate.apply_migrations()
        self.image = str(uuid4())
        with database.transaction() as conn:
            conn.execute("INSERT INTO uploaded_files(id,storage_key,original_name,media_type,byte_size,width,height) VALUES(%s,%s,'test.png','image/png',10,2,2)", (self.image,self.image))
        self.value = payload() | dict(name='旅行助手', summary='简介', tech_stack=['Vue'],cover_file_id=self.image,blocks=[dict(kind='text',body='详情'),dict(kind='image',file_id=self.image,caption='图片')],screenshots=[dict(file_id=self.image,caption='截图')])

    def test_draft_publish_save_archive_and_public_filter(self):
        draft = projects.create_project(payload())
        self.assertEqual(draft['status'],'draft'); self.assertEqual(projects.list_published(),[])
        with self.assertRaises(auth.AdminError): projects.publish_project(draft['id'])
        project = projects.save_project(draft['id'],self.value)
        self.assertEqual(project['blocks'],self.value['blocks']); self.assertEqual(project['screenshots'],self.value['screenshots'])
        published = projects.publish_project(draft['id'])
        self.assertEqual(projects.get_published(None,draft['id']),published)
        self.assertEqual(projects.publish_project(draft['id'])['published_at'],published['published_at'])
        for field in ('name','summary','tech_stack','cover_file_id','blocks'):
            with self.assertRaises(auth.AdminError): projects.save_project(draft['id'],self.value | {field:payload()[field]})
            self.assertEqual(projects.get_published(None,draft['id'])['name'],'旅行助手')
        projects.archive_project(draft['id']); self.assertEqual(projects.list_published(),[])
        with self.assertRaises(auth.AdminError) as raised: projects.get_published(None,draft['id'])
        self.assertEqual(raised.exception.code,'project_not_found')
        with self.assertRaises(auth.AdminError) as raised: projects.archive_project(draft['id'])
        self.assertEqual(raised.exception.status,409)
        projects.save_project(draft['id'],payload())
        with self.assertRaises(auth.AdminError): projects.publish_project(draft['id'])

    def test_invalid_references_and_database_failures_rollback_all_rows(self):
        current = projects.create_project(self.value)
        for field in ('cover_file_id','blocks','screenshots'):
            missing = str(uuid4())
            bad = self.value | {field: missing if field=='cover_file_id' else [dict(kind='image',file_id=missing,caption='')] if field=='blocks' else [dict(file_id=missing,caption='')]}
            with self.assertRaises(auth.AdminError): projects.save_project(current['id'],bad)
            self.assertEqual(projects.get_project(None,current['id']),current)
        with database.transaction() as conn:
            conn.execute("""CREATE FUNCTION reject_screenshot() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'secret'; END $$""")
            conn.execute('CREATE TRIGGER fail_save BEFORE INSERT ON project_screenshots FOR EACH ROW EXECUTE FUNCTION reject_screenshot()')
        with self.assertRaises(psycopg.errors.RaiseException): projects.save_project(current['id'],self.value | dict(name='changed',blocks=[]))
        self.assertEqual(projects.get_project(None,current['id']),current)
        with self.assertRaises(psycopg.errors.RaiseException): projects.create_project(self.value)
        self.assertEqual(len(projects.list_projects()),1)

    def test_reordering_exact_set_and_new_projects_share_collection_lock(self):
        first = projects.create_project(payload()); second = projects.create_project(payload())
        for ids in ([first['id']], [first['id'],first['id']], [first['id'],999], [True,second['id']]):
            with self.assertRaises(auth.AdminError): projects.reorder_projects(dict(ids=ids))
        ordered = projects.reorder_projects(dict(ids=[second['id'],first['id']]))
        self.assertEqual([item['sort_order'] for item in ordered],[0,1])
        self.assertEqual([item['id'] for item in ordered],[second['id'],first['id']])
        with ThreadPoolExecutor(max_workers=4) as pool:
            created = list(pool.map(lambda _: projects.create_project(payload()), range(8)))
        self.assertEqual(sorted(item['sort_order'] for item in created),list(range(2,10)))
        all_projects = projects.list_projects()
        self.assertEqual([item['sort_order'] for item in all_projects],list(range(10)))

    def test_concurrent_saves_are_whole_and_invalid_published_save_keeps_public_value(self):
        item = projects.create_project(self.value); projects.publish_project(item['id'])
        first = self.value | dict(name='first',blocks=[dict(kind='text',body='first')])
        second = self.value | dict(name='second',blocks=[dict(kind='text',body='second')])
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda value: projects.save_project(item['id'],value),(first,second)))
        stored = projects.get_published(None,item['id'])
        self.assertIn(stored,values)
        self.assertEqual(stored['name'],stored['blocks'][0]['body'])

    def test_routes_auth_csrf_full_body_safe_errors_and_order_static_route(self):
        from app.project_routes import router
        app = FastAPI(); app.include_router(auth_router); app.include_router(router)
        client = self.enterContext(TestClient(app,base_url='http://127.0.0.1:5180'))
        self.assertEqual(client.get('/api/projects').json(),{'projects':[]})
        self.assertEqual(client.get('/api/admin/projects').status_code,401)
        with database.transaction() as conn:
            conn.execute('INSERT INTO admin_accounts(username,password_hash) VALUES (%s,%s)',('owner',auth.PASSWORDS.hash('test-only-password')))
        write = {'Origin':'http://127.0.0.1:5180','X-Admin-Request':'1'}
        login = client.post('/api/admin/login',headers=write,json=dict(username='owner',password='test-only-password'))
        headers = write | {'X-CSRF-Token':login.json()['csrf_token']}
        self.assertEqual(client.post('/api/admin/projects',headers=write,json=self.value).status_code,403)
        value = self.value | dict(blocks=[dict(kind='text',body='x'*10000)])
        response = client.post('/api/admin/projects',headers=headers,json=value)
        self.assertEqual(response.status_code,200,response.text); identifier=response.json()['project']['id']
        self.assertEqual(client.get(f'/api/projects/{identifier}').status_code,404)
        self.assertEqual(client.post(f'/api/admin/projects/{identifier}/publish',headers=headers,json={}).status_code,200)
        self.assertEqual(client.get(f'/api/projects/{identifier}').json()['project']['blocks'],value['blocks'])
        self.assertEqual(client.put('/api/admin/projects/order',headers=headers,json=dict(ids=[identifier])).status_code,200)
        for path in (f'/api/admin/projects/999', '/api/projects/999'):
            self.assertEqual(client.get(path).json()['error']['code'],'project_not_found')
        self.assertEqual(client.put(f'/api/admin/projects/{identifier}',headers=headers,json=value|dict(name='')).status_code,400)
        self.assertEqual(client.post(f'/api/admin/projects/{identifier}/archive',headers=headers,json={'status':'draft'}).status_code,400)
        self.assertEqual(client.post(f'/api/admin/projects/{identifier}/archive',headers=headers,json={}).status_code,200)
        self.assertEqual(client.get('/api/projects').json(),{'projects':[]})
        with database.transaction() as conn: conn.execute('DROP TABLE project_screenshots')
        response=client.get('/api/admin/projects')
        self.assertEqual(response.status_code,503); self.assertNotIn('project_screenshots',response.text)
