import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'installer-local'))
from server import KTVServer, safe_name, valid_signature
from build import build


class KTVTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = KTVServer(('127.0.0.1', 0), '127.0.0.1', Path(self.tmp.name))
        # Port=0 requests an ephemeral listening port; rebuild to use assigned port.
        self.port = self.server.server_address[1]
        self.server.base_url = 'http://127.0.0.1:{}'.format(self.port)
        build('127.0.0.1', self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:{}'.format(self.port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def get(self, path, headers=None):
        with urlopen(Request(self.url+path, headers=headers or {}), timeout=5) as r:
            return r.status, r.read(), r.headers

    def post(self, path, body, headers=None):
        with urlopen(Request(self.url+path, data=body, headers=headers or {}, method='POST'), timeout=5) as r:
            return r.status, json.loads(r.read())

    def test_widget_list_matches_zip_size(self):
        _, raw, _ = self.get('/widgetlist.xml')
        root = ET.fromstring(raw)
        url = root.find('./list/widget/download').text
        self.assertTrue(url.endswith('.zip'))
        _, contents, _ = self.get('/Widget/KTV_0.2.0_BR_20261017.zip')
        self.assertEqual(int(root.find('./list/widget/compression').attrib['size']), len(contents))
        with zipfile.ZipFile(self.server.output['archive']) as z:
            self.assertIn('config.xml', z.namelist())
            self.assertIn('index.html', z.namelist())
            self.assertIn(self.url, z.read('js/runtime-config.js').decode('utf-8'))

    def test_auth_required_and_upload_and_playlist(self):
        with self.assertRaises(HTTPError) as err:
            self.get('/api/media')
        self.assertEqual(err.exception.code, 401)
        auth = {'X-KTV-Token':self.server.token}
        png = b'\x89PNG\r\n\x1a\n' + b'\x00'*64
        _, result = self.post('/api/admin/upload?filename=ok.png', png, auth)
        self.assertTrue(result['ok'])
        mid = result['id']
        _, result = self.post('/api/admin/state', json.dumps({'ids':[mid]}).encode(),auth)
        self.assertEqual(len(result['items']), 1)
        _, raw, _ = self.get('/api/state')
        self.assertEqual(json.loads(raw)['items'][0]['id'], mid)
        _, result = self.post('/api/admin/command', b'{"command":"pause"}', auth)
        self.assertFalse(result['playing'])

    def test_range(self):
        with (self.server.media / 'f_test.mp4').open('wb') as out:
            out.write(b'\0\0\0\x18ftypisom0123456789')
        status, raw, headers = self.get('/media/f_test.mp4', {'Range':'bytes=0-3'})
        self.assertEqual(status,206)
        self.assertEqual(raw,b'\0\0\0\x18')
        self.assertEqual(headers['Content-Range'],'bytes 0-3/22')

    def test_untrusted_filename(self):
        self.assertEqual(safe_name('../some\\path\\hi.png'), 'hi.png')
        self.assertIsNone(safe_name('evil.sh'))
        self.assertFalse(valid_signature('.png', b'not a real image'))
        with self.assertRaises(HTTPError) as err:
            self.get('/media/../../README.md')
        self.assertEqual(err.exception.code,404)


if __name__ == '__main__': unittest.main()
