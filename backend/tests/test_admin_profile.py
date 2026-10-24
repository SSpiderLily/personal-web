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
