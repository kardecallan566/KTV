"""End-to-end test for native KTV OS playback and mounted USB access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktv_api_launcher', ROOT/'launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class FakePlayer:
    def __init__(self):
        self.calls = []
        self.playing = False
    def status(self):
        return {'available': True, 'playing': self.playing, 'name': self.calls[-1][1] if self.playing else None}
    def play(self, source, name):
        self.calls.append((source, name))
        self.playing = True
        return self.status()
    def stop(self):
        self.playing = False
        return True
    def close(self):
        self.stop()

class NativeAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.media = self.root/'media'
        self.media.mkdir()
        self.usb = self.root/'usb'
        self.usb.mkdir()
        self.state = self.root/'state'
        self.state.mkdir()
        self.fake = FakePlayer()
        self.server = launcher.KTVOSServer(port=0, media_dir=str(self.media), state_dir=self.state, player=self.fake)
        self.url = 'http://127.0.0.1:{}'.format(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def get(self, path):
        with urlopen(self.url + path, timeout=4) as response:
            return response.status, json.loads(response.read())

    def post(self, path, payload, headers=None):
        meta = {'Content-Type': 'application/json'}
        meta.update(headers or {})
        request = Request(self.url+path, data=json.dumps(payload).encode('utf-8'),
                          headers=meta, method='POST')
        with urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read())

    def test_native_channel_and_stop(self):
        (self.state/'channels.json').write_text(json.dumps({'channels': [
            {'name': 'Meu sinal HLS', 'url': 'https://example.org/authorized/live.m3u8', 'category':'Legal'}
        ]}),encoding='utf-8')
        code,data=self.post('/api/player/play',{'kind':'channel','index':0})
        self.assertEqual(code,200)
        self.assertTrue(data['player']['playing'])
        self.assertEqual(self.fake.calls[-1],('https://example.org/authorized/live.m3u8','Meu sinal HLS'))
        _,data=self.get('/api/status')
        self.assertTrue(data['player']['available'])
        self.assertTrue(data['player']['playing'])
        _,data=self.post('/api/player/stop',{})
        self.assertFalse(data['player']['playing'])
        with self.assertRaises(HTTPError) as e:
            self.post('/api/player/play',{'kind':'channel','index':100})
        self.assertEqual(e.exception.code,400)

    def test_channel_cannot_play_arbitrary_url(self):
        for payload in ({'kind':'channel','url':'file:///etc/shadow'},
                        {'kind':'media','name':'../secret.mp4'},
                        {'kind':'usb','device':'/etc','name':'passwd'},
                        {'kind':'channel','index':True},
                        {}):
            with self.assertRaises(HTTPError) as e:
                self.post('/api/player/play',payload)
            self.assertEqual(e.exception.code,400)
        self.assertEqual(self.fake.calls, [])

    def test_same_origin_and_json_required(self):
        with self.assertRaises(HTTPError) as ex:
            self.post('/api/player/stop',{}, {'Origin':'https://unrelated.example'})
        self.assertEqual(ex.exception.code,403)
        req=Request(self.url+'/api/player/stop',data=b'a=b',
                    headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
        with self.assertRaises(HTTPError) as ex:
            urlopen(req,timeout=4)
        self.assertEqual(ex.exception.code,415)

    def test_local_media_mpv_and_opt_in(self):
        (self.media/'meu video.mp4').write_bytes(b'test')
        code,data=self.post('/api/player/play',{'kind':'media','name':'meu video.mp4'})
        self.assertEqual(code,200)
        self.assertEqual(self.fake.calls[-1][0],str(self.media/'meu video.mp4'))
        with self.assertRaises(HTTPError) as err:
            self.post('/api/player/play',{'kind':'media','name':'missing.mp4'})
        self.assertEqual(err.exception.code,400)

    def test_usb_browser_and_path_restriction(self):
        (self.usb/'film.mp4').write_bytes(b'0123456789')
        with mock.patch.object(launcher,'usb_mounts',return_value={'usb-example':(self.usb,'USB Exemplo')}):
            _,data=self.get('/api/devices')
            self.assertEqual(data['devices'][0]['id'],'usb-example')
            _,data=self.get('/api/media?source=usb&device=usb-example')
            self.assertEqual(data['items'][0]['name'],'film.mp4')
            _,data=self.post('/api/player/play',{'kind':'usb','device':'usb-example','name':'film.mp4'})
            self.assertEqual(self.fake.calls[-1][0],str(self.usb/'film.mp4'))
            req=Request(self.url+'/media/usb/usb-example/film.mp4',
                        headers={'Range':'bytes=0-2'})
            with urlopen(req,timeout=4) as response:
                self.assertEqual(response.status,206)
                self.assertEqual(response.read(),b'012')
            with self.assertRaises(HTTPError) as e:
                self.get('/api/media?source=usb&device=bad')
            self.assertEqual(e.exception.code,404)

if __name__ == '__main__':
    unittest.main()
