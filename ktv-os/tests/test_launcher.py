import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen, Request

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktvos_launcher', HERE / 'launcher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class KTVOSSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.media = self.root / 'media'
        self.media.mkdir()
        self.state = self.root / 'state'
        self.server = m.KTVOSServer(port=0, media_dir=str(self.media), state_dir=self.state)
        self.url = 'http://127.0.0.1:{}'.format(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def fetch(self, path, headers=None):
        with urlopen(Request(self.url + path, headers=headers or {}), timeout=5) as response:
            return response.status, response.read(), response.headers

    def post_json(self, path, payload):
        request = Request(self.url + path, data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=5) as response:
            return response.status, response.read()

    def test_ui_loads_and_health(self):
        code, html, _ = self.fetch('/')
        self.assertEqual(code, 200)
        self.assertIn(b'KTV OS', html)
        self.assertIn(b'data-screen="inicio"', html)
        _, js, _ = self.fetch('/app.js')
        self.assertIn(b'ArrowRight', js)
        _, css, _ = self.fetch('/style.css')
        self.assertIn(b'.tile-grid', css)
        _, raw, _ = self.fetch('/api/status')
        self.assertFalse(json.loads(raw)['usb_direct_tv'])

    def test_media_opt_in_with_range(self):
        file = self.media / 'clip.mp4'
        file.write_bytes(b'abcdefghij')
        code, payload, _ = self.fetch('/api/media')
        self.assertEqual(json.loads(payload)['items'][0]['name'], file.name)
        code, body, headers = self.fetch('/media/clip.mp4', {'Range': 'bytes=2-5'})
        self.assertEqual(code, 206)
        self.assertEqual(body, b'cdef')
        self.assertEqual(headers['Content-Range'], 'bytes 2-5/10')
        with self.assertRaises(HTTPError) as ctx:
            self.fetch('/media/../launcher.py')
        self.assertEqual(ctx.exception.code, 404)

    def test_channels_are_local_and_filtered(self):
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / 'channels.json').write_text(json.dumps({'channels': [
            {'name':'Canal proprio', 'url':'https://example.org/live.m3u8', 'category':'teste'},
            {'name':'Rede local bloqueada', 'url':'http://localhost/live.m3u8'},
            {'name':'Inseguro', 'url':'javascript:alert(1)'},
            {'name':'Site HTML', 'url':'http://example.com/embed'},
        ]}), encoding='utf-8')
        _, body, _ = self.fetch('/api/channels')
        content = json.loads(body)
        self.assertEqual(len(content['channels']), 1)
        self.assertEqual(content['channels'][0]['name'], 'Canal proprio')

    def test_external_iptv_catalog_is_windows_only_and_separate(self):
        _, raw, _ = self.fetch('/api/iptv-free/channels')
        catalog = json.loads(raw)
        if m.sys.platform != 'win32':
            self.assertFalse(catalog['enabled'])
            self.assertEqual(catalog['channels'], [])
        else:
            self.assertTrue(catalog['enabled'])
            self.assertGreater(len(catalog['channels']), 1800)
            self.assertIsInstance(catalog['playback_enabled'], bool)
            self.assertNotIn('url', catalog['channels'][0])
            self.assertNotIn('streams', catalog['channels'][0])
            self.assertIsInstance(catalog['channels'][0]['playable'], bool)
        _, personal_raw, _ = self.fetch('/api/channels')
        self.assertEqual(json.loads(personal_raw)['channels'], [])
    def test_external_iptv_channel_resolves_private_stream_and_plays(self):
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / 'iptv_free_catalog.json').write_text(json.dumps({
            'schema': 'ktv-iptv-playlist-v3',
            'channels': [{
                'id': 'demo-123', 'name': 'Canal Demo', 'category': 'Teste',
                'categories': ['Teste'], 'tvg_id': 'demo.br', 'logo': None,
                'streams': [
                    {'format': 'hls', 'url': 'https://example.org/live.m3u8'},
                    {'format': 'ts', 'url': 'https://example.org/live.ts'}
                ]
            }]
        }), encoding='utf-8')
        with mock.patch.object(m.NativePlayer, 'play', return_value={'playing': True}) as play:
            _, body = self.post_json('/api/player/play', {
                'kind': 'iptv_free', 'id': 'demo-123', 'format': 'ts'
            })
        self.assertEqual(play.call_args.args[0], 'https://example.org/live.ts')
        self.assertNotIn(b'https://example.org/live.ts', body)
        _, status_raw, _ = self.fetch('/api/player/status')
        cache_status = json.loads(status_raw)['iptv_cache']
        self.assertTrue(cache_status['active'])
        self.assertEqual(cache_status['channel']['id'], 'demo-123')
        self.post_json('/api/player/stop', {})
        _, stopped_raw, _ = self.fetch('/api/player/status')
        self.assertFalse(json.loads(stopped_raw)['iptv_cache']['active'])

    def test_usb_devices_are_metadata_only(self):
        _, raw, _ = self.fetch('/api/devices')
        self.assertIsInstance(json.loads(raw)['devices'], list)
        empty_server = m.KTVOSServer(port=0, state_dir=self.root/'empty')
        self.assertEqual(m.read_media(empty_server.media_dir), [])
        empty_server.server_close()

if __name__ == '__main__':
    unittest.main()
