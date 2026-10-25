"""Alpha 0.15: Pluto signed URL regression, XMLTV now/next, health and OSK."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from epg_guide import EPGGuide, EPGError, parse_xmltv
from stream_urls import validate_pluto_url, validate_stream_url, StreamURLError
from stream_check import StreamCheck
from player import NativePlayer
from internet_browser import InternetBrowser, BrowserError, BROADCASTERS
from community_catalog import SOURCES
from launcher import KTVOSServer

PLUTO_ID='5f120e94a5714d00074576a1'
PLUTO_BASE='https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'+PLUTO_ID+'/master.m3u8'
PLUTO_URL=PLUTO_BASE+'?jwt='+('A'*2600)+'&country=BR'
NOW=datetime(2026,10,25,14,15,tzinfo=timezone.utc)
GUIDE=('<?xml version="1.0"?><tv>'
 '<channel id="'+PLUTO_ID+'"><display-name>Pluto TV Cine Sucessos</display-name></channel>'
 '<programme channel="'+PLUTO_ID+'" start="20261025140000 +0000" stop="20261025150000 +0000"><title>Filme atual</title></programme>'
 '<programme channel="'+PLUTO_ID+'" start="20261025150000 +0000" stop="20261025163000 +0000"><title>Próximo filme</title></programme>'
 '</tv>').encode()

class Proc:
    def __init__(self):self.running=True
    def poll(self):return None if self.running else 0
    def terminate(self):self.running=False
    def wait(self,timeout=3):return 0
    def kill(self):self.running=False

class Tests015(unittest.TestCase):
    def test_pluto_long_signed_url_in_native_player(self):
        self.assertGreater(len(PLUTO_URL),1800)
        self.assertLess(len(PLUTO_URL),6000)
        self.assertEqual(validate_pluto_url(PLUTO_URL),PLUTO_URL)
        with self.assertRaises(StreamURLError):
            validate_stream_url(PLUTO_URL)
        calls=[]
        player=NativePlayer(executable='mpv',popen=lambda a,**k:(calls.append(a) or Proc()))
        player.play(PLUTO_URL,'Pluto TV',quality='balanced')
        self.assertEqual(calls[-1][-2:],['--',PLUTO_URL])
        self.assertIn('--hls-bitrate=4000000',calls[-1])
        player.close()
        for bad in (PLUTO_URL.replace('ipv4.pluto.tv','127.0.0.1'),
                    PLUTO_URL.replace('ipv4.pluto.tv','ipv4.pluto.tv.evil.example'),
                    PLUTO_URL.replace('master.m3u8','malicious.m3u8'),
                    PLUTO_BASE+'?country=BR',
                    PLUTO_URL+'%0a--script=evil\n'):
            with self.assertRaises(StreamURLError):
                validate_pluto_url(bad)

    def test_epg_now_and_next_with_real_time_and_missing_data(self):
        parsed=parse_xmltv(GUIDE,NOW)
        self.assertEqual(parsed[PLUTO_ID]['now']['title'],'Filme atual')
        self.assertEqual(parsed[PLUTO_ID]['next']['title'],'Próximo filme')
        calls=[]
        guide=EPGGuide(fetcher=lambda kind:(calls.append(kind) or GUIDE),
                       clock=lambda:100,utcnow=lambda:NOW)
        result=guide.now_next('pluto',PLUTO_ID)
        self.assertEqual(result['now']['title'],'Filme atual')
        self.assertEqual(guide.now_next('pluto',name='Pluto TV Cine Sucessos')['next']['title'],'Próximo filme')
        self.assertEqual(len(calls),1)
        listing=guide.listing('pluto')
        self.assertEqual(listing['programmes'][PLUTO_ID]['now']['title'],'Filme atual')
        self.assertFalse(guide.now_next('pluto',name='Não existe')['available'])
        with self.assertRaises(ValueError):guide.now_next('https://evil.example')
        with self.assertRaises(EPGError):
            parse_xmltv(b'<!DOCTYPE foo [<!ENTITY boom "hi">]><tv/>',NOW)

    def test_probe_is_preliminary_and_cached(self):
        tick=[0];calls=[]
        def probe(url):
            calls.append(url)
            return {'status':'reachable','message':'Servidor respondeu'}
        check=StreamCheck(probe=probe,clock=lambda:tick[0])
        status=check.check('pluto',PLUTO_ID,lambda:(PLUTO_URL,'Cine'))
        self.assertEqual(status['status'],'reachable')
        check.check('pluto',PLUTO_ID,lambda:(PLUTO_URL,'Cine'))
        self.assertEqual(len(calls),1)
        tick[0]+=91
        check.check('pluto',PLUTO_ID,lambda:(PLUTO_URL,'Cine'))
        self.assertEqual(len(calls),2)
        with self.assertRaises(ValueError):
            check.check('file','x',lambda:('file:///etc/shadow','x'))

    def test_websites_use_fixed_browser_allowlist(self):
        calls=[]
        browser=InternetBrowser(executable='chromium',popen=lambda a,**k:(calls.append(a) or Proc()))
        self.assertIn('sbt',BROADCASTERS)
        self.assertIn('globo',BROADCASTERS)
        self.assertTrue(browser.open_broadcaster('sbt')['opened'])
        self.assertEqual(calls[-1][-1],BROADCASTERS['sbt']['url'])
        self.assertNotIn('--no-sandbox',calls[-1])
        for value in ('https://evil.com','',None):
            with self.assertRaises(BrowserError):
                browser.open_broadcaster(value)

    def test_keyboard_drag_and_reset_present_and_manual(self):
        s=(ROOT/'app'/'osk.js').read_text(encoding='utf-8')
        self.assertIn("head.addEventListener('pointerdown'",s)
        self.assertIn("head.addEventListener('pointermove'",s)
        self.assertIn("panel.style.left='';panel.style.top=''",s)
        self.assertIn("['abc','ABC']",s)
        self.assertIn("['accents','Acentos']",s)
        self.assertNotIn('automatic=',s)
        self.assertIn("toggle.addEventListener('click'",s)

    def test_endpoints_sanitize_and_return_guide(self):
        class Browser:
            def open_broadcaster(self, ident):
                if ident not in BROADCASTERS:raise BrowserError('Invalid')
                return {'opened':True}
            def status(self):return {'available':True}
        class Player:
            def status(self):return {'available':True,'playing':False}
            def stop(self):pass
            def close(self):pass
        class Pluto:
            def play_url(self,ident):
                if ident!=PLUTO_ID:raise ValueError('Unknown channel')
                return PLUTO_URL,'Pluto'
            def listing(self):return []
        with tempfile.TemporaryDirectory() as folder:
            guide=EPGGuide(fetcher=lambda kind:GUIDE,clock=lambda:100,utcnow=lambda:NOW)
            checker=StreamCheck(probe=lambda _: {'status':'reachable','message':'ok'})
            server=KTVOSServer(port=0,state_dir=Path(folder),player=Player(),
                browser=Browser(),pluto=Pluto(),epg=guide,stream_check=checker)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(payload):
                req=Request(base+'/api/tv-aberta/open',method='POST',
                    data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                return urlopen(req,timeout=4)
            try:
                with urlopen(base+'/api/tv-aberta',timeout=4) as r:
                    self.assertIn('SBT',[c['name'] for c in json.load(r)['channels']])
                with post({'id':'globo'}) as r:self.assertTrue(json.load(r)['ok'])
                with self.assertRaises(HTTPError) as caught:post({'id':'https://evil.example'})
                self.assertEqual(caught.exception.code,400)
                with urlopen(base+'/api/epg/list?kind=pluto',timeout=4) as r:
                    self.assertIn(PLUTO_ID,json.load(r)['programmes'])
                with urlopen(base+'/api/channels/check?kind=pluto&id='+PLUTO_ID,timeout=4) as r:
                    self.assertEqual(json.load(r)['status'],'reachable')
            finally:
                server.shutdown();server.server_close();worker.join(timeout=3)

if __name__=='__main__':unittest.main()
