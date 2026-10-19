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
from server import KTVServer, safe_name, valid_signature, valid_stream_url
from build import build, DIAGNOSTIC_FILENAME, BARE_FILENAME, FLAT_FILENAME


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
        _, contents, _ = self.get('/Widget/KTV_0.4.2_BR_20261018.zip')
        self.assertEqual(int(root.find('./list/widget/compression').attrib['size']), len(contents))
        with zipfile.ZipFile(self.server.output['archive']) as z:
            self.assertIn('config.xml', z.namelist())
            self.assertIn('index.html', z.namelist())
            self.assertIn(b'<ver>0.402</ver>', z.read('config.xml'))
            self.assertNotIn(b'clsid:SAMSUNG-INFOLINK-PLAYER', z.read('index.html'))
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

    def test_client_telemetry(self):
        _, raw, _ = self.get('/api/state?client=orsay')
        self.assertEqual(json.loads(raw)['version'], 1)
        token = {'X-KTV-Token': self.server.token}
        _, payload, _ = self.get('/api/status', token)
        status = json.loads(payload)
        self.assertEqual(status['clients']['orsay']['ip'], '127.0.0.1')
        self.assertNotIn('preview', status['clients'])
        _, _, _ = self.get('/api/event?client=orsay&event=image-loaded')
        _, payload, _ = self.get('/api/status', token)
        self.assertEqual(json.loads(payload)['media_events']['orsay']['event'], 'image-loaded')
        with self.assertRaises(HTTPError) as err:
            self.get('/api/event?client=orsay&event=unknown')
        self.assertEqual(err.exception.code, 400)
        _, _, _ = self.get('/api/event?client=orsay&event=html-start')
        _, _, _ = self.get('/api/event?client=orsay&event=app-start')
        _, _, _ = self.get('/api/event?client=orsay&event=hls-deferred')
        _, _, _ = self.get('/api/state?client=preview')
        _, payload, _ = self.get('/api/status', token)
        self.assertIn('preview', json.loads(payload)['clients'])

    def test_diagnostic_widget_bootstrap(self):
        _, raw, _ = self.get('/widgetlist.xml')
        root = ET.fromstring(raw)
        apps = root.findall('./list/widget')
        self.assertEqual([app.attrib['id'] for app in apps], ['KTV', 'KTVDiag', 'KTVBare', 'KTVFlat'])
        info = root.find("./list/widget[@id='KTVDiag']")
        _, content, _ = self.get('/Widget/' + DIAGNOSTIC_FILENAME)
        self.assertEqual(int(info.find('compression').attrib['size']), len(content))
        with zipfile.ZipFile(self.server.output['diagnostic_archive']) as z:
            html = z.read('index.html').decode('utf-8')
            self.assertIn('widgetAPI.sendReadyEvent();', html)
            self.assertIn('$MANAGER_WIDGET/Common/API/Widget.js', html)
            self.assertIn(self.url, z.read('js/runtime-config.js').decode('utf-8'))
            self.assertIn('<widgetname>KTVDiag</widgetname>', z.read('config.xml').decode('utf-8'))

    def test_main_widget_sends_ready(self):
        with zipfile.ZipFile(self.server.output['archive']) as z:
            self.assertIn('$MANAGER_WIDGET/Common/API/Widget.js', z.read('index.html').decode('utf-8'))
            self.assertIn('window.widgetAPI.sendReadyEvent();', z.read('js/app.js').decode('utf-8'))
            self.assertIn('<ver>0.402</ver>', z.read('config.xml').decode('utf-8'))

    def test_minimal_ab_boot_widgets(self):
        for name, filename in (('KTVBare', BARE_FILENAME), ('KTVFlat', FLAT_FILENAME)):
            _, binary, _ = self.get('/Widget/' + filename)
            with zipfile.ZipFile(self.server.output['bare_archive' if name == 'KTVBare' else 'flat_archive']) as archive:
                self.assertGreater(len(binary), 200)
                self.assertIn('index.html', archive.namelist())
                self.assertIn('config.xml', archive.namelist())
                html = archive.read('index.html').decode('utf-8')
                config = archive.read('config.xml').decode('utf-8')
                self.assertIn('$MANAGER_WIDGET/Common/API/Widget.js', html)
                self.assertIn('sendReadyEvent()', html)
                self.assertNotIn('XMLHttpRequest', html)
                self.assertIn('<widgetname', config)
                if name == 'KTVBare':
                    self.assertIn('xmlns="http://www.samsung.com/"', config)
                    self.assertIn('itemtype=', config)
                else:
                    self.assertNotIn('xmlns="http://www.samsung.com/"', config)

    def test_tv_browser_information_probe(self):
        _, html, headers = self.get('/tv-info/')
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'navigator.userAgent', html)
        _, probe, _ = self.get('/api/tv-probe', {'User-Agent': 'SamsungSmartTV Maple'})
        self.assertIn(b'Diagnostico local recebido', probe)
        _, status, _ = self.get('/api/status', {'X-KTV-Token': self.server.token})
        entries = json.loads(status)['tv_probes']
        self.assertEqual(entries[-1]['ip'], '127.0.0.1')
        self.assertEqual(entries[-1]['user_agent'], 'SamsungSmartTV Maple')

    def test_range(self):
        with (self.server.media / 'f_test.mp4').open('wb') as out:
            out.write(b'\0\0\0\x18ftypisom0123456789')
        status, raw, headers = self.get('/media/f_test.mp4', {'Range':'bytes=0-3'})
        self.assertEqual(status,206)
        self.assertEqual(raw,b'\0\0\0\x18')
        self.assertEqual(headers['Content-Range'],'bytes 0-3/22')

    def test_channel_admin_and_tune(self):
        auth = {'X-KTV-Token': self.server.token}
        with self.assertRaises(HTTPError) as err:
            self.get('/api/channels')
        self.assertEqual(err.exception.code, 401)
        stream = 'http://127.0.0.1:{}/hls/demo.m3u8'.format(self.port)
        self.assertTrue(valid_stream_url(stream))
        for bad in ('javascript:alert(1)', 'https://user:pass@example.com/live.m3u8',
                    'https://site.example/embed', 'http://site.example/canal.m3u8|COMPONENT=WV',
                    'https://site.example/canal.m3u8#fragment'):
            self.assertFalse(valid_stream_url(bad), bad)
        _, result = self.post('/api/admin/channels', json.dumps({'action': 'add', 'name':'Teste local', 'url':stream}).encode(), auth)
        channel = result['channels'][0]
        _, result = self.post('/api/admin/tune', json.dumps({'id':channel['id']}).encode(), auth)
        self.assertEqual(result['items'][0]['type'], 'hls')
        _, content, _ = self.get('/api/state?client=orsay')
        self.assertEqual(json.loads(content)['items'][0]['url'], stream)
        # Lista permanece persistida em arquivo; nenhuma URL externa foi consultada.
        self.assertEqual(json.loads((self.server.workspace/'channels.json').read_text())[0]['name'],'Teste local')
        _, result = self.post('/api/admin/channels', json.dumps({'action':'delete', 'id':channel['id']}).encode(), auth)
        self.assertEqual(result['channels'], [])

    def test_local_hls_serving(self):
        index = self.server.hls / 'demo.m3u8'
        index.write_text('#EXTM3U\n#EXTINF:4,\ndemo_00000.ts\n', encoding='utf-8')
        segment = self.server.hls / 'demo_00000.ts'
        segment.write_bytes(b'\x47' + b'\x00' * 187)
        code, raw, headers = self.get('/hls/demo.m3u8')
        self.assertEqual(code, 200)
        self.assertTrue(raw.startswith(b'#EXTM3U'))
        self.assertEqual(headers['Content-Type'], 'application/vnd.apple.mpegurl')
        code, raw, headers = self.get('/hls/demo_00000.ts')
        self.assertEqual(code, 200)
        self.assertEqual(len(raw), 188)
        self.assertEqual(headers['Content-Type'], 'video/mp2t')
        with self.assertRaises(HTTPError) as err:
            self.get('/hls/../state.json')
        self.assertEqual(err.exception.code, 404)

    def test_untrusted_filename(self):
        self.assertEqual(safe_name('../some\\path\\hi.png'), 'hi.png')
        self.assertIsNone(safe_name('evil.sh'))
        self.assertFalse(valid_signature('.png', b'not a real image'))
        with self.assertRaises(HTTPError) as err:
            self.get('/media/../../README.md')
        self.assertEqual(err.exception.code,404)


if __name__ == '__main__': unittest.main()
