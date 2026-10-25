"""Alpha 0.13: reviewed GitHub TV feeds, green browser and optional X11 keyboard."""
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
from community_catalog import (CommunityCatalog, CommunityCatalogError, SOURCES,
                               allowed_stream, parse_m3u)
from input_support import InputController
from internet_browser import InternetBrowser, BrowserError
from launcher import KTVOSServer

LIVE='https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/master.m3u8'
SECOND='https://canaleducacao-stream.ebc.com.br/index.m3u8'
M3U='#EXTM3U\n#EXTINF:-1 group-title="Notícias",DW English\n'+LIVE+'\n'


class FakeProcess:
    def __init__(self):self.active=True
    def poll(self):return None if self.active else 0
    def terminate(self):self.active=False


class Tests013(unittest.TestCase):
    def test_reviewed_sources_only_https(self):
        for source in SOURCES:
            self.assertTrue(source[1].startswith('https://raw.githubusercontent.com/'))
        self.assertTrue(allowed_stream(LIVE))
        self.assertFalse(allowed_stream('http://dwamdstream102.akamaized.net/x.m3u8'))
        self.assertFalse(allowed_stream('https://evil.example/stream.m3u8'))
        self.assertFalse(allowed_stream('https://user:secret@dwamdstream102.akamaized.net/x.m3u8'))
        self.assertFalse(allowed_stream('https://dwamdstream102.akamaized.net/x.m3u8?jwt=secret'))
        self.assertFalse(allowed_stream('https://dwamdstream102.akamaized.net:8888/x.m3u8'))
        self.assertFalse(allowed_stream('https://dwamdstream102.akamaized.net/x.mp4'))
        self.assertFalse(allowed_stream('https://dwamdstream102.akamaized.net/x.m3u8#fragment'))
        with self.assertRaises(CommunityCatalogError):
            parse_m3u('https://not-m3u', 'Test')

    def test_source_catalog_never_leaks_urls_to_frontend(self):
        calls=[]
        clock=[100]
        def get(url):
            calls.append(url)
            if url==SOURCES[0][1]:
                return M3U
            return '#EXTM3U\n#EXTINF:-1 group-title="Educação",Canal Educação\n'+SECOND+'\n'
        catalog=CommunityCatalog(fetcher=get,clock=lambda:clock[0])
        self.assertEqual(calls,[])  # Boot does not fetch
        listing=catalog.listing()
        self.assertEqual(len(listing['channels']),2)
        self.assertEqual(len(calls),2)
        self.assertNotIn('_url',json.dumps(listing))
        self.assertNotIn('https:',json.dumps(listing))
        ident=listing['channels'][0]['id']
        self.assertEqual(catalog.play_url(ident)[0],LIVE)
        clock[0]+=1700
        catalog.listing()
        self.assertEqual(len(calls),2)
        clock[0]+=150
        catalog.listing()
        self.assertEqual(len(calls),4)
        with self.assertRaises(ValueError):
            catalog.play_url('file:///etc/passwd')

    def test_partial_failure_and_no_stale_playback(self):
        attempts=[0]
        def fetch(url):
            if url==SOURCES[1][1]:
                raise OSError('unavailable')
            attempts[0]+=1
            if attempts[0]>1:
                raise OSError('expired')
            return M3U
        now=[10]
        cat=CommunityCatalog(fetcher=fetch,clock=lambda:now[0])
        self.assertTrue(cat.listing()['partial'])
        ident=cat.listing()['channels'][0]['id']
        now[0]+=2000
        with self.assertRaises(CommunityCatalogError):
            cat.play_url(ident)

    def test_hardware_keyboard_detection_and_native_toggle(self):
        detected='I: Bus=0003\nN: Name="USB Keyboard"\nH: Handlers=sysrq kbd event4\n\n'
        buttons='I: Bus=0019\nN: Name="Power Button"\nH: Handlers=kbd event0\n\n'
        calls=[]
        def spawn(argv,**kwargs):
            calls.append((argv,kwargs))
            return FakeProcess()
        osk=InputController(executable='matchbox-keyboard',popen=spawn,device_reader=lambda:detected)
        self.assertTrue(osk.has_physical_keyboard())
        self.assertFalse(osk.status()['virtual_open'])
        self.assertTrue(osk.toggle()['virtual_open'])
        self.assertEqual(calls[0][0],['matchbox-keyboard'])
        self.assertNotIn('shell',calls[0][1])
        self.assertFalse(osk.toggle()['virtual_open'])
        self.assertFalse(InputController(executable='',device_reader=lambda:buttons).has_physical_keyboard())
        self.assertIsNone(InputController(executable='',device_reader=lambda:'').has_physical_keyboard())

    def test_browser_local_home_strict_origin(self):
        launched=[]
        def spawn(args,**kw):
            launched.append(args)
            return FakeProcess()
        browser=InternetBrowser(executable='chromium',popen=spawn,safe=True)
        self.assertTrue(browser.open_home('http://127.0.0.1:8787/browser.html')['opened'])
        self.assertIn('--disable-gpu',launched[-1])
        self.assertEqual(launched[-1][-1],'http://127.0.0.1:8787/browser.html')
        for target in ('https://evil.example/browser.html',
                       'http://127.0.0.2:8787/browser.html',
                       'http://127.0.0.1:8787/../browser.html',
                       'file:///etc/passwd'):
            with self.assertRaises(BrowserError):
                browser.open_home(target)

    def test_api_community_and_keyboard_and_static_browser(self):
        class FakePlayer:
            def __init__(self):self.calls=[]
            def status(self):return {'available':True,'playing':True}
            def play(self,url,name):
                self.calls.append((url,name))
                return self.status()
            def stop(self):return False
            def close(self):pass
        class FakeBrowser:
            def status(self):return {'available':True}
            def open_home(self,target):
                self.last=target
                return {'opened':True}
        with tempfile.TemporaryDirectory() as folder:
            fakePlayer=FakePlayer()
            fakeBrowser=FakeBrowser()
            controller=InputController(executable='matchbox-keyboard',
                    popen=lambda *a,**k:FakeProcess(),device_reader=lambda:'')
            server=KTVOSServer(port=0,state_dir=Path(folder),player=fakePlayer,
                browser=fakeBrowser,input_controller=controller,
                community=CommunityCatalog(fetcher=lambda url:M3U))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(path,payload,extra=None):
                return urlopen(Request(base+path,method='POST',
                    data=json.dumps(payload).encode(),
                    headers={'Content-Type':'application/json',**(extra or {})}),timeout=4)
            try:
                for filename in ('/browser.html','/browser-green.css','/browser-green.js','/osk.js','/osk.css'):
                    with urlopen(base+filename,timeout=3) as response:
                        self.assertEqual(response.status,200)
                with urlopen(base+'/api/community/channels',timeout=3) as response:
                    channels=json.load(response)['channels']
                self.assertEqual(len(channels),1)
                self.assertNotIn('_url',str(channels))
                with post('/api/player/play',{'kind':'community','id':channels[0]['id']}) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertEqual(fakePlayer.calls[0][0],LIVE)
                with post('/api/browser/home',{}) as response:
                    self.assertTrue(json.load(response)['ok'])
                self.assertEqual(fakeBrowser.last,base+'/browser.html')
                with post('/api/input/virtual-toggle',{}) as response:
                    self.assertTrue(json.load(response)['input']['virtual_open'])
                for payload in ({'kind':'community','id':'malicious'},
                                {'kind':'community','id':'https://evil.example'}):
                    with self.assertRaises(HTTPError) as caught:
                        post('/api/player/play',payload)
                    self.assertEqual(caught.exception.code,400)
                with self.assertRaises(HTTPError) as caught:
                    post('/api/browser/home',{}, {'Origin':'https://evil.example'})
                self.assertEqual(caught.exception.code,403)
            finally:
                controller.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
