"""Alpha 0.16 Smart Player: official fallback, no untrusted URLs or DRM bypass."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from internet_browser import InternetBrowser, BrowserError
from smart_player import (SmartPlayerError, OFFICIAL_DESTINATIONS,
                          destination_for, options_for)
from launcher import KTVOSServer

PLUTO_ID='5f120e94a5714d00074576a1'


class MockProcess:
    def __init__(self):self.open=True
    def poll(self):return None if self.open else 0
    def terminate(self):self.open=False


class FakePlayer:
    def status(self):return {'available':False,'playing':False}
    def close(self):pass
    def stop(self):return False


class SmartPlayerTests(unittest.TestCase):
    def test_destinations_are_fixed_and_allowlisted(self):
        self.assertEqual(destination_for('pluto',PLUTO_ID),'pluto')
        self.assertEqual(destination_for('public','tv-brasil'),'tv-brasil')
        self.assertEqual(destination_for('public','tv-cultura'),'tv-cultura')
        self.assertIsNone(destination_for('community','abc123'))
        self.assertIsNone(destination_for('channel','0'))
        for ident in ('../../etc/passwd','https://evil.test',None,'a'*24):
            with self.assertRaises(SmartPlayerError):
                destination_for('pluto',ident)
        for ident in ('not-in-catalog','tv-brasil/../../etc/passwd'):
            with self.assertRaises(SmartPlayerError):
                destination_for('public',ident)
        for item in OFFICIAL_DESTINATIONS.values():
            self.assertTrue(item['url'].startswith('https://'))
            self.assertNotIn('jwt=',item['url'])
        self.assertFalse(options_for('pluto',PLUTO_ID,False)['official_available'])
        opts=options_for('pluto',PLUTO_ID,True)
        self.assertTrue(opts['official_available'])
        self.assertFalse(opts['drm_detected'])
        self.assertIsNone(opts.get('url'))  # no external link supplied to browser
        self.assertFalse(options_for('community','abc123',True)['official_available'])

    def test_browser_prefers_optional_chrome_without_installs(self):
        args=[]
        def spawn(cmd,**kwargs):
            args.append((cmd,kwargs))
            return MockProcess()
        browser=InternetBrowser(executable='chromium',popen=spawn,
                                official_executable='google-chrome-stable',safe=False)
        self.assertEqual(browser.status()['official_browser'],'Chrome')
        self.assertFalse(browser.status()['drm_verified'])
        info=browser.open_official('pluto')
        self.assertTrue(info['opened'])
        self.assertFalse(info['drm_verified'])
        self.assertEqual(args[-1][0][0],'google-chrome-stable')
        self.assertEqual(args[-1][0][-1],OFFICIAL_DESTINATIONS['pluto']['url'])
        self.assertNotIn('shell',args[-1][1])
        self.assertNotIn('--no-sandbox',args[-1][0])
        for value in (None, 42, 'https://attacker.test','../../etc/passwd','globoplay'):
            with self.assertRaises(BrowserError):
                browser.open_official(value)
        self.assertEqual(len(args),1)
        fallback=InternetBrowser(executable='chromium',popen=spawn,
                                  official_executable='chromium',safe=True)
        fallback.open_official('tv-brasil')
        self.assertIn('--disable-gpu',args[-1][0])
        self.assertEqual(args[-1][0][0],'chromium')
        self.assertEqual(fallback.status()['official_browser'],'Chromium')

    def test_local_api_enforces_ids_origin_and_no_raw_urls(self):
        class FakeBrowser:
            def __init__(self):self.calls=[]
            def status(self):return {'available':True,'official_available':True}
            def open_official(self,destination):
                self.calls.append(destination)
                return {'opened':True,'name':'Pluto TV','browser':'Chromium','drm_verified':False}
        with tempfile.TemporaryDirectory() as folder:
            fake=FakeBrowser()
            server=KTVOSServer(port=0,state_dir=Path(folder),browser=fake,player=FakePlayer())
            t=threading.Thread(target=server.serve_forever,daemon=True)
            t.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(payload, headers=None):
                return urlopen(Request(base+'/api/smart-player/open',method='POST',
                    data=json.dumps(payload).encode(),headers={
                    'Content-Type':'application/json',**(headers or {})}),timeout=4)
            try:
                with urlopen(base+'/api/smart-player/options?kind=pluto&id='+PLUTO_ID,timeout=4) as r:
                    options=json.load(r)
                    self.assertTrue(options['official_available'])
                    self.assertNotIn('url',options)
                with post({'kind':'pluto','id':PLUTO_ID}) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertEqual(fake.calls,['pluto'])
                with post({'kind':'public','id':'tv-brasil'}) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertEqual(fake.calls,['pluto','tv-brasil'])
                denied=(
                    {'kind':'pluto','id':'http://attacker.test'},
                    {'kind':'public','id':'https://attacker.test'},
                    {'kind':'community','id':'random'},
                    {'kind':'channel','id':'0'},
                    {'kind':'pluto','id':PLUTO_ID,'url':'http://attacker.test'},
                )
                for payload in denied[:-1]:
                    with self.assertRaises(HTTPError) as caught:
                        post(payload)
                    self.assertEqual(caught.exception.code,400)
                with self.assertRaises(HTTPError) as caught:
                    post({'kind':'pluto','id':PLUTO_ID},
                         {'Origin':'https://attacker.test'})
                self.assertEqual(caught.exception.code,403)
                with post(denied[-1]) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertEqual(fake.calls[-1],'pluto')  # ignored untrusted URL field
            finally:
                server.shutdown();server.server_close();t.join(timeout=3)

    def test_ui_includes_official_fallback_and_iso_manifest(self):
        js=(ROOT/'app/app.js').read_text(encoding='utf-8')
        html=(ROOT/'app/index.html').read_text(encoding='utf-8')
        iso=(ROOT/'linux-live/build-iso.sh').read_text(encoding='utf-8')
        self.assertIn("id=\"player-official\"",html)
        self.assertIn("function updateSmartOptions()",js)
        self.assertIn("function openSmartOfficial(",js)
        self.assertIn("noVideoPolls>=3",js)
        self.assertIn('smart_player.py',iso)
        self.assertIn('ALPHA 0.16',html)


if __name__=='__main__':
    unittest.main()
