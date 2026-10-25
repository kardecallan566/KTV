"""Alpha 0.20: external free-to-air programme metadata, never media URLs."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reidos_guide import (ReiGuide, DiscoveryError, parse_response,
                         SOURCE_URL, normalize, MAX_BYTES)
from launcher import KTVOSServer

NOW=1792960800  # fixed test wall clock, not run-dependent
def program(title,start,end):
    return {'title':title,'start_time':start,'end_time':end,
            'embed_url':'https://attacker.example/never-play.m3u8'}

SOURCE={
    'success':True,'total':7,
    'data':[
        {'id':'globo','name':'Globo SP','category':'Canais Abertos',
         'logo_url':'https://untrusted.example/logo.svg',
         'embeds':[{'embed_url':'https://untrusted.example/globo.m3u8'}],
         'epg':{'current':program('Jornal local',NOW-30,NOW+1700),
                'next':program('Documentário',NOW+1800,NOW+3600)}},
        {'id':'tv-brasil','name':'TV Brasil','category':'Canais Abertos',
         'embeds':[{'embed_url':'https://untrusted.example/ebc'}],
         'epg':{'current':program('Programa público',NOW-80,NOW+1600)}},
        {'id':'tv-cultura','name':'TV Cultura','category':'Canais Abertos',
         'epg':{'current':program('<script>alert(1)</script>',NOW-20,NOW+1800)}},
        {'id':'premiere','name':'Premiere','category':'Esportes',
         'embeds':[{'embed_url':'https://untrusted.example/premiere'}]},
        {'id':'hbo','name':'HBO','category':'Filmes',
         'embeds':[{'embed_url':'https://untrusted.example/hbo'}]},
        {'id':'sbt','name':'SBT','category':'Canais Abertos',
         'epg':{'current':program('Programa antigo',NOW-3600,NOW-1000),
                'next':program('Próximo jornal',NOW+300,NOW+1300)}},
        {'id':'cnn','name':'CNN Brasil','category':'Notícias',
         'epg':{'current':program('CNN',NOW-30,NOW+1500)}},
    ]
}


class GuideTests(unittest.TestCase):
    def test_metadata_never_contains_embeds_or_paid_streams(self):
        rows=parse_response(json.dumps(SOURCE).encode(),now=NOW)
        self.assertEqual({x['name'] for x in rows},
                         {'Globo','TV Brasil','TV Cultura','SBT'})
        blob=json.dumps(rows,ensure_ascii=False)
        self.assertNotIn('embed',blob)
        self.assertNotIn('untrusted',blob)
        self.assertNotIn('https:',blob)
        self.assertNotIn('HBO',blob)
        self.assertNotIn('Premiere',blob)
        globo=next(x for x in rows if x['name']=='Globo')
        self.assertEqual(globo['now']['title'],'Jornal local')
        self.assertEqual(globo['next']['title'],'Documentário')
        self.assertIsNone(globo['play_id'])
        ebc=next(x for x in rows if x['name']=='TV Brasil')
        self.assertEqual(ebc['play_id'],'tv-brasil')
        sbt=next(x for x in rows if x['name']=='SBT')
        self.assertIsNone(sbt['now'])  # stale "live" data not displayed
        self.assertEqual(sbt['next']['title'],'Próximo jornal')

    def test_invalid_responses_and_control_characters(self):
        for raw in (b'not json',b'[]',b'{}',b'{"success":false,"data":[]}',
                    json.dumps({'success':True,'data':'bad'}).encode(),
                    b'{}'+b'x'*(MAX_BYTES+2)):
            with self.subTest(raw=raw[:18]):
                with self.assertRaises(DiscoveryError):
                    parse_response(raw,now=NOW)
        copied=dict(SOURCE)
        entries=list(SOURCE['data'])
        copied['data']=entries+[{'name':'TV Brasil\n<h1>',
                                  'epg':{'current':program('Programação',NOW-1,NOW+1)}}]
        rows=parse_response(json.dumps(copied).encode(),now=NOW)
        self.assertEqual(len(rows),4)
        self.assertEqual(normalize('TV CULTURA'),'tv cultura')

    def test_fetch_is_lazy_and_cached_for_five_minutes(self):
        times=[0];calls=[]
        def fetcher():
            calls.append(1)
            return json.dumps(SOURCE).encode()
        guide=ReiGuide(fetcher=fetcher,clock=lambda:times[0],unix_time=lambda:NOW)
        self.assertEqual(calls,[])
        self.assertEqual(len(guide.listing()['channels']),4)
        self.assertEqual(len(calls),1)
        times[0]+=299
        guide.listing()
        self.assertEqual(len(calls),1)
        times[0]+=2
        guide.listing()
        self.assertEqual(len(calls),2)
        self.assertEqual(SOURCE_URL,'https://api.reidoscanais.cam/channels')

    def test_api_exposes_only_sanitized_programming(self):
        class FakePlayer:
            def status(self):return {'available':False,'playing':False}
            def stop(self):return False
            def close(self):pass
        with tempfile.TemporaryDirectory() as folder:
            guide=ReiGuide(fetcher=lambda:json.dumps(SOURCE).encode(),
                           unix_time=lambda:NOW)
            server=KTVOSServer(port=0,state_dir=Path(folder),player=FakePlayer(),
                               rei_guide=guide)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                with urlopen(base+'/api/guide/reidos/aberta',timeout=4) as response:
                    self.assertEqual(response.status,200)
                    body=json.load(response)
                self.assertEqual(body['playback_policy'],'verified_ktv_only')
                self.assertEqual(len(body['channels']),4)
                self.assertNotIn('embed',json.dumps(body))
                self.assertNotIn('hbo',json.dumps(body).lower())
                with self.assertRaises(HTTPError) as err:
                    urlopen(base+'/api/guide/reidos/arbitrary',timeout=4)
                self.assertEqual(err.exception.code,404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_iso_and_ui_have_no_untrusted_external_frames(self):
        html=(ROOT/'app/index.html').read_text()
        js=(ROOT/'app/app.js').read_text()
        iso=(ROOT/'linux-live/build-iso.sh').read_text()
        self.assertIn('reidos_guide.py',iso)
        self.assertIn('ALPHA 0.20',html)
        self.assertIn('id="reidos-guide-channels"',html)
        self.assertIn("'/api/guide/reidos/aberta'",js)
        self.assertNotIn('api.reidoscanais.cam/',js)
        self.assertNotIn('reidoscanais.cam/embed',js)


if __name__=='__main__':
    unittest.main()
