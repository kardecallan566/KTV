"""Alpha 0.12 regression: safe browser, authorized M3U, playback compatibility."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from channel_store import ChannelStore, ChannelError, parse_m3u
from internet_browser import InternetBrowser, BrowserError
from player import NativePlayer
from launcher import KTVOSServer


class FakeProcess:
    def __init__(self):
        self.running = True
    def poll(self):
        return None if self.running else 2
    def terminate(self):
        self.running = False
    def wait(self, timeout=3):
        return 2
    def kill(self):
        self.running = False


class UpgradeTests(unittest.TestCase):
    def test_legal_m3u_import_preserves_personal_channels_and_deduplicates(self):
        playlist = ('#EXTM3U\n'
                    '#EXTINF:-1 group-title="Educação",Canal Ciência\n'
                    'https://example.org/ciencia.m3u8\n'
                    '#EXTINF:-1 group-title="Cinema",Filmes gratuitos\n'
                    'https://example.org/filmes.mp4\n'
                    '#EXTINF:-1 group-title="Cinema",Repetido\n'
                    'https://example.org/ciencia.m3u8\n'
                    '#EXTINF:-1 group-title="Invalido",Local\n'
                    'file:///etc/passwd\n'
                    '#EXTINF:-1 group-title="Invalido",Kodi plugin\n'
                    'plugin://video.addon/abc\n')
        entries, ignored = parse_m3u(playlist)
        self.assertEqual(len(entries), 2)
        self.assertEqual(ignored, 3)
        self.assertEqual(entries[0]['category'], 'Educação')
        with tempfile.TemporaryDirectory() as root:
            store = ChannelStore(root)
            store.change('add', {'name':'Canal Original','url':'https://example.org/ciencia.m3u8'})
            result = store.import_m3u(playlist)
            self.assertEqual(result['added'], 1)
            self.assertEqual(result['ignored'], 4)
            self.assertEqual(len(store.load()), 2)
            self.assertEqual(store.load()[0]['name'], 'Canal Original')
            self.assertEqual(store.import_m3u(playlist)['added'], 0)
        with self.assertRaises(ChannelError):
            parse_m3u('#EXTM3U\n#EXTINF:-1,Pirata\njavascript:alert(1)')
        with self.assertRaises(ChannelError):
            parse_m3u('#EXTM3U\n' + ('X' * 100000))

    def test_compatibility_mode_whitelist_and_no_shell(self):
        calls = []
        def start(args, **kwargs):
            calls.append((args, kwargs))
            return FakeProcess()
        player = NativePlayer(executable='mpv', popen=start)
        p = player.play('https://example.org/canal.m3u8', 'Teste',
                        quality='economy', decode='compatible')
        self.assertTrue(p['playing'])
        self.assertEqual(p['decode'], 'compatible')
        argv = calls[-1][0]
        self.assertIn('--hwdec=no', argv)
        self.assertIn('--vo=x11', argv)
        self.assertNotIn('--hwdec=auto-safe', argv)
        self.assertEqual(argv[-2:], ['--', 'https://example.org/canal.m3u8'])
        self.assertNotIn('shell', calls[-1][1])
        for value in ('--vf=evil', True, None, '', 'software;rm -rf /'):
            with self.assertRaises(ValueError):
                player.play('https://example.org/canal.m3u8', 'Teste', decode=value)
        player.close()
        player.play('https://example.org/canal.m3u8', 'Teste', decode='default')
        self.assertIn('--hwdec=auto-safe', calls[-1][0])
        player.close()

    def test_browser_opens_only_encoded_search_not_commands(self):
        commands = []
        def start(argv, **kwargs):
            commands.append((argv, kwargs))
            return FakeProcess()
        browser = InternetBrowser(executable='chromium', popen=start, safe=False)
        result = browser.open_search('Filmes e desenhos & animação')
        self.assertTrue(result['opened'])
        self.assertEqual(commands[0][0][1], '--no-first-run')
        self.assertIn('--new-window', commands[0][0])
        self.assertTrue(commands[0][0][-1].startswith('https://duckduckgo.com/?q='))
        self.assertIn('%26', commands[0][0][-1])
        self.assertNotIn('shell', commands[0][1])
        for bad in (None, True, '', '\nmalicious', 'a'*181):
            with self.assertRaises(BrowserError):
                browser.open_search(bad)
        safe_browser = InternetBrowser(executable='chromium', popen=start, safe=True)
        safe_browser.open_search('noticias')
        self.assertIn('--disable-gpu', commands[-1][0])

    def test_local_api_import_browser_and_decode_guard(self):
        class FakePlayer:
            def __init__(self):self.calls=[]
            def status(self):return {'available':True,'playing':bool(self.calls)}
            def play(self, source, name):
                self.calls.append((source,name))
                return self.status()
            def stop(self):return False
            def close(self):pass
        class FakeBrowser:
            def __init__(self):self.queries=[]
            def status(self):return {'available':True}
            def open_search(self, query):
                if not isinstance(query,str) or not query:
                    raise BrowserError('Busca invalida')
                self.queries.append(query)
                return {'opened':True}
        with tempfile.TemporaryDirectory() as root:
            fake_browser=FakeBrowser()
            fake_player=FakePlayer()
            server=KTVOSServer(port=0,state_dir=Path(root),player=fake_player,
                               browser=fake_browser)
            worker=threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(path, payload, headers=None):
                req=Request(base+path, data=json.dumps(payload).encode(),
                            method='POST',
                            headers={'Content-Type':'application/json',**(headers or {})})
                return urlopen(req,timeout=4)
            try:
                with post('/api/browser/search',{'query':'animação japonesa'}) as response:
                    self.assertTrue(json.load(response)['ok'])
                self.assertEqual(fake_browser.queries,['animação japonesa'])
                m3u='#EXTM3U\n#EXTINF:-1 group-title="Livre",TV Autorizada\nhttps://example.com/live.m3u8\n'
                with post('/api/channels/import-m3u',{'content':m3u}) as response:
                    data=json.load(response)
                    self.assertEqual(data['added'],1)
                self.assertEqual(len(server.channels.load()),1)
                with post('/api/player/play', {'kind':'channel','index':0,
                                                'decode':'default'}) as response:
                    self.assertTrue(json.load(response)['ok'])
                for bad in ('evil', False, '--vo=evil'):
                    with self.assertRaises(HTTPError) as error:
                        post('/api/player/play', {'kind':'channel','index':0,
                                                   'decode':bad})
                    self.assertEqual(error.exception.code,400)
                with self.assertRaises(HTTPError) as error:
                    post('/api/channels/import-m3u',{'content':m3u},
                         headers={'Origin':'https://evil.example'})
                self.assertEqual(error.exception.code,403)
                self.assertEqual(len(server.channels.load()),1)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__=='__main__':
    unittest.main()
