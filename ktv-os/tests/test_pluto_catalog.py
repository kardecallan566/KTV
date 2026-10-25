"""Pluto M3U tests: fixed source, strict streams, privacy and on-demand API."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktv_pluto_catalog', ROOT/'pluto_catalog.py')
pluto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pluto)

IDENT = '5f120e94a5714d00074576a1'
OTHER = '5f120f41b7d403000783a6d6'
ROOT_URL = 'https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'
VALID_URL = ROOT_URL + IDENT + '/master.m3u8?country=BR&jwt=TEST_ONLY'
OTHER_URL = ROOT_URL + OTHER + '/master.m3u8?jwt=TEST_ONLY'
M3U = (
    '#EXTM3U\n'
    '#EXTINF:-1 tvg-id="' + IDENT + '" group-title="Filmes",Pluto TV Cine Sucessos\n'
    + VALID_URL + '\n'
    '#EXTINF:-1 group-title="Anime",Pluto TV Anime\n'
    + OTHER_URL + '\n'
)

class CatalogTests(unittest.TestCase):
    def test_groups_ids_and_only_valid_links(self):
        text = M3U + (
            '#EXTINF:-1 group-title="Ataque",Servidor de fora\n'
            'https://evil.example/master.m3u8?jwt=TOKEN\n'
            '#EXTINF:-1 group-title="Filmes",Duplicado\n' + VALID_URL + '\n'
            '#EXTINF:-1 group-title="Teste",Trava\n'
            'http://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'
            + IDENT + '/master.m3u8?jwt=TOKEN\n'
        )
        channels = pluto.parse_playlist(text)
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[OTHER]['category'], 'Anime')
        self.assertEqual(channels[IDENT]['name'], 'Pluto TV Cine Sucessos')
        self.assertNotIn('Trava', str(channels))

    def test_reject_credentials_and_injection(self):
        bad = [
            'https://evil.example/foo.m3u8?jwt=x',
            'https://ipv4.pluto.tv.evil.example/' + IDENT + '/master.m3u8?jwt=x',
            'https://user:pass@ipv4.pluto.tv/' + IDENT + '/master.m3u8?jwt=x',
            'file:///etc/shadow',
            'https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'
            + IDENT + '/master.m3u8#fragment',
            'https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'
            + IDENT + '/master.m3u8?jwt=x\n--input-script=evil',
        ]
        for url in bad:
            self.assertIsNone(pluto._stream_id(url), url)
        with self.assertRaises(pluto.PlutoError):
            pluto.parse_playlist('#EXTM3U\n#EXTINF:-1,Untrusted\nfile:///tmp/file\n')

    def test_no_background_download_short_cache_and_no_token_json(self):
        calls = []
        tick = [100.]
        def fetch():
            calls.append(True)
            return M3U
        catalog = pluto.PlutoCatalog(fetcher=fetch, clock=lambda:tick[0])
        self.assertEqual(calls, [])  # no fetch at boot
        listings = catalog.listing()
        self.assertEqual(len(listings), 2)
        self.assertNotIn('jwt=', json.dumps(listings))
        self.assertNotIn('TEST_ONLY', json.dumps(listings))
        self.assertEqual(catalog.play_url(IDENT)[0], VALID_URL)
        self.assertEqual(len(calls), 1)
        tick[0] += 299
        catalog.play_url(IDENT)
        self.assertEqual(len(calls), 1)
        tick[0] += 2
        catalog.play_url(IDENT)
        self.assertEqual(len(calls), 2)
        with self.assertRaises(ValueError):
            catalog.play_url('http://evil.example/x')

    def test_refresh_failure_does_not_use_expired_token(self):
        tick = [0]
        times = [0]
        def fetch():
            times[0] += 1
            if times[0] > 1:
                raise OSError('remote unavailable, do not expose URL')
            return M3U
        catalog = pluto.PlutoCatalog(fetcher=fetch,clock=lambda:tick[0])
        self.assertEqual(len(catalog.listing()),2)
        tick[0] += 301
        with self.assertRaises(pluto.PlutoError):
            catalog.play_url(IDENT)

class APITests(unittest.TestCase):
    def test_api_plays_only_indexed_pluto_id(self):
        spec2=importlib.util.spec_from_file_location('ktv_pluto_launcher', ROOT/'launcher.py')
        launcher=importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(launcher)
        class FakePlayer:
            def __init__(self):self.calls=[]
            def status(self):return {'available':True,'playing':bool(self.calls),'name':None}
            def play(self,source,name):
                self.calls.append((source,name))
                return self.status()
            def stop(self):return True
            def close(self):pass
        with tempfile.TemporaryDirectory() as temp:
            player=FakePlayer()
            catalog=pluto.PlutoCatalog(fetcher=lambda:M3U)
            server=launcher.KTVOSServer(port=0,player=player,pluto=catalog,
                                        state_dir=Path(temp))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base='http://127.0.0.1:' + str(server.server_address[1])
            try:
                with urlopen(base+'/api/pluto/channels',timeout=3) as response:
                    obj=json.load(response)
                    self.assertEqual(len(obj['channels']),2)
                    self.assertNotIn('jwt',json.dumps(obj))
                def post(payload):
                    req=Request(base+'/api/player/play',data=json.dumps(payload).encode(),
                                method='POST',headers={'Content-Type':'application/json'})
                    return urlopen(req,timeout=3)
                with post({'kind':'pluto','id':IDENT}) as response:
                    self.assertEqual(response.status,200)
                self.assertEqual(player.calls[-1],(VALID_URL,'Pluto TV Cine Sucessos'))
                for value in ('missing','https://evil.example',None):
                    with self.assertRaises(HTTPError) as error:
                        post({'kind':'pluto','id':value,'url':'file:///etc/shadow'})
                    self.assertEqual(error.exception.code,400)
                self.assertEqual(len(player.calls),1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

if __name__=='__main__':
    unittest.main()
