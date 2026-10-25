"""Alpha 0.14: streaming link compatibility, restrictions and manual OSK."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from channel_store import ChannelStore, ChannelError, parse_m3u
from community_catalog import allowed_stream, parse_m3u as community_parse
from player import NativePlayer
from stream_urls import validate_stream_url, StreamURLError
from launcher import KTVOSServer


class MockProc:
    def __init__(self):self.alive=True
    def poll(self):return None if self.alive else 0
    def terminate(self):self.alive=False
    def wait(self, timeout=3):return 0
    def kill(self):self.alive=False


class StreamTests(unittest.TestCase):
    def test_formats_supported_and_preserve_safe_queries(self):
        for ext in ('m3u8','mpd','ts','mp4','m4v','webm','flv'):
            address='https://cdn.example.org/channel/live.'+ext+'?id=channel&mode=1'
            self.assertEqual(validate_stream_url(address),address)
        self.assertEqual(validate_stream_url('http://media.example.org:8080/live.ts'),
                         'http://media.example.org:8080/live.ts')
        self.assertEqual(validate_stream_url('https://media.example.org:8443/dash.mpd'),
                         'https://media.example.org:8443/dash.mpd')

    def test_reject_private_and_malformed_urls(self):
        unsafe=[
            'file:///etc/passwd','rtsp://example.org/live.mpd',
            'https://localhost/channel.m3u8','http://127.0.0.1/admin/live.ts',
            'https://[::1]/stream.mpd', 'http://10.0.0.5/live.m3u8',
            'http://192.168.1.1/live.mp4','https://169.254.169.254/live.mpd',
            'http://172.16.0.10/live.mp4','https://[fe80::1]/live.mpd',
            'https://100.64.0.1/channel.webm','https://server.local/live.mpd',
            'https://box.internal/live.mpd','https://host.home.arpa/live.ts',
            'https://2130706433/live.m3u8',
            'https://user:secret@cdn.example.org/live.mpd',
            'https://cdn.example.org:22/live.mpd',
            'https://cdn.example.org:3306/live.m3u8',
            'https://cdn.example.org/live.mpd#private',
            'https://cdn.example.org/live.m3u',
            'https://cdn.example.org/live.m3u8\n--script=bad',
            'https://cdn.example.org/live.m3u8%0a--script=bad',
            '--input-ipc-server=/tmp/socket','',
        ]
        for target in unsafe:
            with self.subTest(target=target):
                with self.assertRaises(StreamURLError):
                    validate_stream_url(target)

    def test_m3u_import_new_media_and_filter_untrusted(self):
        playlist='#EXTM3U\n'+''.join(
            '#EXTINF:-1 group-title="Livre",Canal '+ext+'\n'
            'https://media.example.org/live.'+ext+'\n'
            for ext in ('mpd','ts','webm','flv','m4v'))
        playlist+='#EXTINF:-1,Local\nhttp://localhost/test.mpd\n'
        channels, skipped=parse_m3u(playlist)
        self.assertEqual(len(channels),5)
        self.assertEqual(skipped,1)
        with tempfile.TemporaryDirectory() as folder:
            store=ChannelStore(folder)
            stats=store.import_m3u(playlist)
            self.assertEqual(stats['added'],5)
            self.assertEqual(len(store.load()),5)
            self.assertEqual(store.load()[0]['url'],'https://media.example.org/live.mpd')

    def test_broadcaster_dash_only_and_no_unchecked_catalog_host(self):
        url='https://vs-cmaf-pushb-ww-live.akamaized.net/x/bbc_arabic_tv/pc_hd_abr_v2.mpd'
        self.assertTrue(allowed_stream(url))
        self.assertFalse(allowed_stream('https://evil.example/live.mpd'))
        self.assertFalse(allowed_stream('https://dwamdstream102.akamaized.net/live.mpd'))
        self.assertFalse(allowed_stream('https://vs-cmaf-pushb-ww-live.akamaized.net/x.mpd?jwt=abc'))
        p='#EXTM3U\n#EXTINF:-1 group-title="News",BBC Arabic\n'+url+'\n'
        self.assertEqual(len(community_parse(p,'Free-TV')),1)

    def test_mpv_no_shell_and_mpd_without_hls_selection(self):
        calls=[]
        def launch(argv,**opts):
            calls.append((argv,opts))
            return MockProc()
        player=NativePlayer(executable='mpv',popen=launch)
        for ext in ('mpd','ts','flv','webm','m3u8'):
            player.play('https://media.example.org/live.'+ext,'Cultura')
            self.assertEqual(calls[-1][0][-2:],
                             ['--','https://media.example.org/live.'+ext])
            self.assertEqual(any(arg.startswith('--hls-bitrate=')
                                  for arg in calls[-1][0]),ext=='m3u8')
            self.assertNotIn('shell',calls[-1][1])
        player.close()
        for blocked in ('file:///etc/shadow','https://localhost/live.mpd',
                        'rtsp://example.org:554/live'):
            with self.assertRaises(ValueError):
                player.play(blocked,'Blocked')

    def test_toggle_is_explicit_not_automatically_focused(self):
        source=(ROOT/'app'/'osk.js').read_text(encoding='utf-8')
        self.assertIn("toggle.textContent=state?'✕ Fechar teclado':'⌨ Abrir teclado'", source)
        self.assertIn("toggle.setAttribute('aria-pressed',state?'true':'false')", source)
        self.assertNotIn('automatic=false',source)
        self.assertNotIn('if(automatic)',source)
        self.assertNotIn("fetch(\u0027/api/input/status\u0027",source)
        self.assertIn("toggle.addEventListener(\u0027click\u0027",source)

    def test_local_api_rejects_private_targets_and_accepts_dash(self):
        class FakePlayer:
            def status(self):return {'available':False,'playing':False}
            def stop(self):pass
            def close(self):pass
        with tempfile.TemporaryDirectory() as folder:
            server=KTVOSServer(port=0,state_dir=Path(folder),player=FakePlayer())
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            root='http://127.0.0.1:'+str(server.server_address[1])
            def post(obj):
                req=Request(root+'/api/channels/change',data=json.dumps(obj).encode('utf-8'),
                            headers={'Content-Type':'application/json'},method='POST')
                return urlopen(req,timeout=4)
            try:
                with post({'action':'add','name':'Notícias','url':'https://cdn.example.org/live.mpd'}) as response:
                    self.assertTrue(json.load(response)['ok'])
                for bad in ('http://127.0.0.1/live.m3u8',
                            'http://169.254.169.254/live.ts',
                            'file:///etc/passwd'):
                    with self.assertRaises(HTTPError) as raised:
                        post({'action':'add','name':'Bad','url':bad})
                    self.assertEqual(raised.exception.code,400)
                self.assertEqual(len(server.channels.load()),1)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
