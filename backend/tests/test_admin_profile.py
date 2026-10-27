"""Profile format boundaries without external services."""
import importlib
import unittest
from uuid import uuid4
from app import admin_auth as auth


def payload():
    return dict(name='', title='', introduction='', skills=[], avatar_file_id=None, contacts=[], social_links=[])


class ProfileValidationTests(unittest.TestCase):
    def setUp(self):
        self.profile = importlib.import_module('app.profile')

    def test_empty_identity_and_exact_fields(self):
        self.assertEqual(self.profile.validate_profile(payload()), payload())
        for value in ({}, payload() | {'projects': []}, payload() | {'name': 1}):
            with self.assertRaises(auth.AdminError): self.profile.validate_profile(value)

    def test_size_and_unicode_boundaries(self):
        for field, limit in [('name',100), ('title',200), ('introduction',20000)]:
            self.profile.validate_profile(payload() | {field:'文'*limit})
            for value in ['文'*(limit+1), '\x00', '\ud800']:
                with self.assertRaises(auth.AdminError): self.profile.validate_profile(payload() | {field:value})
        for skills in [['x']*31, [''], [1], 'x']:
            with self.assertRaises(auth.AdminError): self.profile.validate_profile(payload() | {'skills':skills})

    def test_safe_contacts_and_social_links(self):
        for url in ['mailto:owner@example.com', 'tel:+86-123456789', 'https://example.com/a?x=1', 'http://example.com']:
            self.profile.validate_profile(payload() | {'contacts':[{'label':'联系','url':url}]})
        invalid = ['javascript:alert(1)', '//evil.test', '/trip/', 'https://user:pass@example.com', 'https://example.com\\evil', 'https://example.com\n', 'mailto:a@example.com?body=hi', 'mailto:a@example.com%0d%0aBcc:evil@example.com', 'tel:+123;ext=99', 'tel:+123%0a', 'https://', 'mailto:', 'tel:abc']
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(auth.AdminError):
                self.profile.validate_profile(payload() | {'contacts':[{'label':'联系','url':url}]})
        for url in ['mailto:a@example.com', 'tel:+123']:
            with self.assertRaises(auth.AdminError):
                self.profile.validate_profile(payload() | {'social_links':[{'label':'联系','url':url}]})
        for links in [[{'label':'x','url':'https://example.com'}]*21, [{'label':'','url':'https://example.com'}], [{'label':'x','url':'https://example.com','extra':True}]]:
            with self.assertRaises(auth.AdminError): self.profile.validate_profile(payload() | {'contacts':links})

    def test_avatar_is_uuid_or_null(self):
        value=str(uuid4())
        self.assertEqual(self.profile.validate_profile(payload() | {'avatar_file_id':value})['avatar_file_id'], value)
        for value in ['', 1, True, 'not-a-uuid']:
            with self.assertRaises(auth.AdminError): self.profile.validate_profile(payload() | {'avatar_file_id':value})

    def test_http_links_reject_malformed_browser_urls_before_saving(self):
        for field in ('contacts', 'social_links'):
            for url in ('https://example.com/100%', 'https://example.com/%FF', 'https://%',
                        'https://example.com/%E0%A4', 'https://example.com/%ED%A0%80',
                        'https://bad_host.example/', 'https://example.123/', 'https://127.1/',
                        'https://example.com:bad/', 'https://example.com/\u00a0', 'https://example.com/\ufeff', '', None):
                with self.subTest(field=field, url=url), self.assertRaises(auth.AdminError):
                    self.profile.validate_profile(payload() | {field: [{'label': '链接', 'url': url}]})
            for url in ('https://example.com/100%25', 'https://example.com/%F0%9F%98%80',
                        'https://example.com/路径/😀?q=中文', 'http://localhost:5173/',
                        'http://127.0.0.1:5173/', 'https://[::1]/', 'https://xn--fsqu00a.xn--0zwm56d/路径'):
                value = payload() | {field: [{'label': '链接', 'url': url}]}
                self.assertEqual(self.profile.validate_profile(value), value)


    def test_optional_about_fields_validate_without_breaking_legacy_payloads(self):
        value=payload() | {'about_content':{'page_title':'关于我','current_project_url':'/#/works','about_body':'第一段\n\n第二段'}}
        self.assertEqual(self.profile.validate_profile(value),value)
        for about in [{'unknown':'x'}, {'page_title':5}, {'about_body':'x'*10001}, {'current_project_url':'javascript:alert(1)'}, {'current_project_url':'//evil.example'}, {'current_project_url':'/#/works%0a'}]:
            with self.subTest(about=about),self.assertRaises(auth.AdminError):
                self.profile.validate_profile(payload() | {'about_content':about})
        self.assertEqual(self.profile.validate_profile(payload()),payload())
