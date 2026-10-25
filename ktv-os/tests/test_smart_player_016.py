"""Integrated KTV player regression tests: direct channels and authorized widgets."""
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
from smart_player import (SmartPlayerError, EMBED_PLAYERS, EMBED_URLS,
                          embed_for, options_for, live_tv_listing)
from launcher import KTVOSServer

PLUTO_ID='5f120e94a5714d00074576a1'


class FakePlayer:
    def status(self):return {'available':True,'playing':False}
    def close(self):pass
    def stop(self):return False


class IntegratedPlayerTests(unittest.TestCase):
    def test_embeds_are_explicit_official_widgets_only(self):
        self.assertEqual(embed_for('public','tv-brasil')['url'],
                         'https://aovivo.ebc.com.br/embed-tvbrasil.html')
        self.assertEqual(embed_for('public','tv-cultura')['url'],
                         'https://culturaplay.tvcultura.com.br/channels/14/embed')
        self.assertIsNone(embed_for('pluto',PLUTO_ID))
        self.assertIsNone(embed_for('public','tv-camara'))
        self.assertIsNone(embed_for('community','test'))
        self.assertIsNone(embed_for('channel','0'))
        for value in ('../../etc/passwd','https://evil.example',None,'g'*24):
            with self.assertRaises(SmartPlayerError):embed_for('pluto',value)
        for value in ('../../etc/passwd','missing','tv-brasil.fake'):
            with self.assertRaises(SmartPlayerError):embed_for('public',value)
        with self.assertRaises(SmartPlayerError):embed_for('file','whatever')
        for value in EMBED_PLAYERS.values():
            self.assertTrue(value['url'].startswith('https://'))
            self.assertNotIn('jwt=',value['url'])
            self.assertNotIn('?',value['url'])
            self.assertIn(value['url'],EMBED_URLS)
        self.assertTrue(options_for('public','tv-brasil')['embed_available'])
        self.assertFalse(options_for('pluto',PLUTO_ID)['embed_available'])
        self.assertFalse(options_for('public','tv-camara')['embed_available'])
        self.assertFalse(options_for('public','tv-cultura')['drm_detected'])

    def test_open_tv_contains_playable_channels_not_website_cards(self):
        listings=live_tv_listing()
        names={c['name'] for c in listings}
        self.assertIn('TV Brasil',names)
        self.assertIn('TV Cultura',names)
        self.assertNotIn('SBT',names)
        self.assertFalse(any(c.get('url') or c.get('site') for c in listings))
        self.assertTrue(any(c['embed_available'] for c in listings))
        self.assertTrue(any(not c['embed_available'] for c in listings))

    def test_routes_no_external_launch_and_no_client_links(self):
        with tempfile.TemporaryDirectory() as folder:
            server=KTVOSServer(port=0,state_dir=Path(folder),player=FakePlayer())
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(path,payload, origin=None):
                headers={'Content-Type':'application/json'}
                if origin:headers['Origin']=origin
                return urlopen(Request(base+path,method='POST',
                    data=json.dumps(payload).encode(),headers=headers),timeout=3)
            try:
                with urlopen(base+'/api/smart-player/options?kind=public&id=tv-brasil',timeout=3) as r:
                    data=json.load(r)
                self.assertEqual(data['embed_url'],EMBED_PLAYERS['tv-brasil']['url'])
                self.assertTrue(data['embed_available'])
                with urlopen(base+'/api/smart-player/options?kind=pluto&id='+PLUTO_ID,timeout=3) as r:
                    self.assertFalse(json.load(r)['embed_available'])
                with urlopen(base+'/api/tv-aberta',timeout=3) as r:
                    channels=json.load(r)['channels']
                    self.assertNotIn('SBT',[x['name'] for x in channels])
                for path in ('/api/smart-player/open','/api/tv-aberta/open'):
                    with self.assertRaises(HTTPError) as exc:
                        post(path,{'kind':'public','id':'tv-brasil','url':'https://evil.example'})
                    self.assertEqual(exc.exception.code,404)
                for path in ('/api/smart-player/options?kind=public&id=https://evil.example',
                             '/api/smart-player/options?kind=file&id=any'):
                    with self.assertRaises(HTTPError) as exc:urlopen(base+path,timeout=3)
                    self.assertEqual(exc.exception.code,400)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)

    def test_ui_is_sandboxed_and_no_general_website_fallback(self):
        html=(ROOT/'app/index.html').read_text()
        js=(ROOT/'app/app.js').read_text()
        iso=(ROOT/'linux-live/build-iso.sh').read_text()
        self.assertIn('id="tv-embed"',html)
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-forms allow-presentation"',html)
        self.assertIn('referrerpolicy="strict-origin-when-cross-origin"',html)
        self.assertIn('id="player-embed"',html)
        self.assertIn('function openSmartEmbed(',js)
        self.assertIn("embedFrame.removeAttribute('src')",js)
        self.assertNotIn('function openSmartOfficial(',js)
        self.assertNotIn("'/api/smart-player/open'",js)
        self.assertNotIn('Site oficial',js)
        self.assertIn('smart_player.py',iso)
        self.assertIn('ALPHA 0.17',html)


if __name__=='__main__':
    unittest.main()
