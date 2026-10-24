import json
import unittest
from starlette.requests import Request
from app import admin_auth as auth
from app.content_request import json_content


def request(data):
    async def receive():
        return {'type': 'http.request', 'body': data, 'more_body': False}
    return Request({'type': 'http', 'method': 'PUT', 'path': '/', 'headers': []}, receive)


class ContentRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_content_and_exact_limit(self):
        data = b'{"text":"' + b'x' * (262144 - 11) + b'"}'
        data += b' ' * (262144 - len(data))
        self.assertEqual(len(data), 262144)
        self.assertGreater(len((await json_content(request(data)))['text']), 4096)
        with self.assertRaises(auth.AdminError):
            await json_content(request(data + b' '))

    async def test_rejects_invalid_nested_values(self):
        for data in (b'[]', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}',
                     b'{"a":"\\u0000"}', b'{"a":"\\ud800"}', b'{"a":1,"a":2}',
                     b'{"a":{"x":"\\u0000"}}', b'\xff'):
            with self.subTest(data=data), self.assertRaises(auth.AdminError):
                await json_content(request(data))

    async def test_accepts_unicode_and_nested_blocks(self):
        value = {'name': '漫游', 'blocks': [{'kind': 'text', 'body': '详情'}]}
        self.assertEqual(await json_content(request(json.dumps(value).encode())), value)
