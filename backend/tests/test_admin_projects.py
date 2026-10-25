"""Project validation independent of a database."""
import unittest
from uuid import uuid4
from app import projects
from app.admin_auth import AdminError


def payload():
    return dict(name='', summary='', category='', tech_stack=[], features=[], cover_file_id=None,
                cover_alt='', demo_url=None, source_url=None, blocks=[], screenshots=[])


class ProjectValidationTests(unittest.TestCase):
    def test_empty_draft_and_complete_published(self):
        self.assertEqual(projects.validate_project(payload()), payload())
        with self.assertRaises(AdminError): projects.validate_project(payload(), published=True)
        value = payload() | dict(name='项目', summary='简介', tech_stack=['Vue'], cover_file_id=str(uuid4()), blocks=[dict(kind='text', body='详情')])
        self.assertEqual(projects.validate_project(value, published=True), value)
        for field in ('name','summary','tech_stack','cover_file_id','blocks'):
            with self.subTest(field=field), self.assertRaises(AdminError):
                projects.validate_project(value | {field: payload()[field]}, published=True)
        with self.assertRaises(AdminError): projects.validate_project(value | {'blocks':[dict(kind='text', body='  ')]}, published=True)

    def test_exact_fields_types_lengths_and_unicode(self):
        invalid = [payload() | {'id':1}, payload() | {'status':'published'}, payload() | {'name':False},
                   payload() | {'summary':'a'*2001}, payload() | {'category':'a'*101}, payload() | {'cover_alt':'x'*501},
                   payload() | {'name':'\x00'}, payload() | {'name':'\ud800'}, payload() | {'tech_stack':['']},
                   payload() | {'tech_stack':['a']*21}, payload() | {'features':['x'*501]}, payload() | {'features':['a']*31},
                   payload() | {'blocks':[{'kind':'text','body':'x'*10001}]}, payload() | {'blocks':[{'kind':'text','body':''}]*101},
                   payload() | {'blocks':[{'kind':'text','body':'a','id':1}]}, payload() | {'cover_file_id':'bad'},
                   payload() | {'screenshots':[{'file_id':str(uuid4()),'caption':''}]*2},
                   payload() | {'screenshots':[{'file_id':str(uuid4()),'caption':''} for _ in range(31)]}]
        for value in invalid:
            with self.subTest(value=repr(value)[:160]), self.assertRaises(AdminError): projects.validate_project(value)
        boundary = payload() | dict(name='a'*100, summary='x'*2000, category='x'*100, cover_alt='x'*500, tech_stack=['a'*100]*20, features=['b'*500]*30, blocks=[dict(kind='text',body='x'*10000)]*100)
        self.assertEqual(projects.validate_project(boundary), boundary)

    def test_only_safe_absolute_links_and_exact_trip_demo(self):
        for url in ('https://example.com/path?q=1', 'http://localhost:5173/', '/trip/'):
            self.assertEqual(projects.validate_project(payload() | {'demo_url':url})['demo_url'], url)
        for url in ('//example.com', '/trip', '/trip/?x', '/other/', 'javascript:alert(1)', 'https://a:b@example.com', 'https://example.com\\evil', 'https://example.com\n', 'http:///bad', 'https://example.com:bad', 'https://example.com/%0a', 'https://example.com/%5c'):
            with self.subTest(url=url), self.assertRaises(AdminError): projects.validate_project(payload() | {'demo_url':url})
        with self.assertRaises(AdminError): projects.validate_project(payload() | {'source_url':'/trip/'})

    def test_unicode_codepoint_boundaries_and_strict_url_roundtrip_contract(self):
        value = payload() | dict(name='😀'*100, summary='😀'*2000, category='😀'*100, cover_alt='😀'*500,
                                 tech_stack=['😀'*100], features=['😀'*500], blocks=[dict(kind='text',body='😀'*10000)])
        self.assertEqual(projects.validate_project(value),value)
        for url in ('https://example.com/100%', 'https://example.com/%FF', 'https://%', 'https://example.com/%E0%A4',
                    'https://bad_host.example/', 'https://example.123/', 'https://127.1/', 'https://example.com/%ED%A0%80'):
            with self.subTest(url=url), self.assertRaises(AdminError): projects.validate_project(payload() | dict(demo_url=url))
        for url in ('https://example.com/100%25', 'https://example.com/%F0%9F%98%80', 'https://example.com/😀', 'http://localhost:5173/', 'http://127.0.0.1:5173/', 'https://[::1]/'):
            self.assertEqual(projects.validate_project(payload() | dict(demo_url=url))['demo_url'],url)
