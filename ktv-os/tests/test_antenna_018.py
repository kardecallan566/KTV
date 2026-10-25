"""Alpha 0.18: local ISDB-Tb over-the-air TV without websites or Internet."""
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from antenna_tv import AntennaTV, AntennaError, parse_zap
from launcher import KTVOSServer

SAMPLE=(
    'TV Globo HD:473142857:INVERSION_AUTO:BANDWIDTH_6_MHZ:FEC_AUTO:'
    'FEC_AUTO:QAM_64:TRANSMISSION_MODE_8K:GUARD_INTERVAL_1_16:'
    'HIERARCHY_NONE:301:302:1\n'
    'SBT HD:479142857:INVERSION_AUTO:BANDWIDTH_6_MHZ:FEC_AUTO:'
    'FEC_AUTO:QAM_64:TRANSMISSION_MODE_8K:GUARD_INTERVAL_1_16:'
    'HIERARCHY_NONE:401:402:2\n'
)

class MockProc:
    def __init__(self):
        self.running=True
    def wait(self,timeout=None):
        self.running=False
        return 0
    def poll(self):
        return None if self.running else 0
    def terminate(self):
        self.running=False
    def kill(self):
        self.running=False

class FakePlayer:
    def __init__(self):
        self.calls=[]
    def play(self,source,name):
        self.calls.append((source,name))
        return {'available':True,'playing':True,'name':name}
    def stop(self):return True
    def close(self):pass
    def status(self):return {'available':True,'playing':bool(self.calls)}


class AntennaTests(unittest.TestCase):
    def device(self,root):
        device=Path(root)/'dev'/ 'adapter0'
        device.mkdir(parents=True)
        (device/'frontend0').touch()
        (device/'dvr0').touch()
        return device.parent

    def test_parse_channel_names_globo_sbt_and_ignore_bad(self):
        found,clean=parse_zap(SAMPLE)
        self.assertEqual([x['name'] for x in found],['TV Globo HD','SBT HD'])
        self.assertNotIn('http',clean)
        extra='-evil:'+SAMPLE.split(':',1)[1]
        channels,_=parse_zap(SAMPLE+extra+'https://example.org:12\n')
        self.assertEqual(len(channels),2)
        with self.assertRaises(AntennaError):parse_zap('X'*280000)

    def test_scan_tuner_uses_country_br_and_local_tools_not_shell(self):
        with tempfile.TemporaryDirectory() as root:
            devices=self.device(root)
            calls=[]
            def fake_popen(args,**kw):
                calls.append((args,kw))
                if args[0]=='w_scan':
                    kw['stdout'].write(SAMPLE.encode('utf-8'))
                    kw['stdout'].flush()
                return MockProc()
            tv=AntennaTV(Path(root)/'state',device_root=devices,
                   scanner='w_scan',zapper='dvbv5-zap',popen=fake_popen,
                   wait=lambda seconds:None)
            self.assertEqual(tv.status()['scan_state'],'idle')
            self.assertTrue(tv.start_scan()['tuner_found'])
            for _ in range(150):
                if tv.status()['scan_state']!='running':break
                time.sleep(.02)
            status=tv.status()
            self.assertEqual(status['scan_state'],'ready',status['scan_error'])
            self.assertEqual(len(status['channels']),2)
            self.assertEqual(calls[0][0],['w_scan','-ft','-c','BR','-X','-E','0','-a','0'])
            self.assertNotIn('shell',calls[0][1])
            self.assertEqual((Path(root)/'state'/'antenna_channels.conf').is_file(),True)
            tv._refresh_file()
            player=FakePlayer()
            data=tv.play(1,player)
            self.assertTrue(data['playing'])
            self.assertEqual(player.calls,[(str(devices/'adapter0'/'dvr0'),'SBT HD')])
            self.assertEqual(calls[1][0],
                ['dvbv5-zap','-a','0','-c',str(Path(root)/'state'/'antenna_channels.conf'),
                 '-I','zap','-r','SBT HD'])
            tv.close()

    def test_unavailable_tuner_does_not_start_commands(self):
        with tempfile.TemporaryDirectory() as root:
            tv=AntennaTV(Path(root),device_root=Path(root)/'missing',
                   scanner='w_scan',zapper='dvbv5-zap')
            self.assertFalse(tv.status()['available'])
            with self.assertRaises(AntennaError):tv.start_scan()
            with self.assertRaises(AntennaError):tv.play(0,FakePlayer())

    def test_api_requires_local_json_and_valid_index(self):
        with tempfile.TemporaryDirectory() as root:
            devices=self.device(root)
            commands=[]
            def spawn(args,**opts):
                commands.append(args)
                if args[0]=='w_scan':
                    opts['stdout'].write(SAMPLE.encode())
                    opts['stdout'].flush()
                return MockProc()
            tuner=AntennaTV(Path(root)/'state',device_root=devices,
                             scanner='w_scan',zapper='dvbv5-zap',popen=spawn,
                             wait=lambda _:None)
            player=FakePlayer()
            server=KTVOSServer(port=0,state_dir=Path(root)/'state',
                               antenna=tuner,player=player)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(route,body,origin=None):
                headers={'Content-Type':'application/json'}
                if origin:headers['Origin']=origin
                req=Request(base+route,method='POST',data=json.dumps(body).encode(),
                            headers=headers)
                return urlopen(req,timeout=4)
            try:
                with urlopen(base+'/api/tv/antenna',timeout=4) as r:
                    self.assertEqual(json.load(r)['antenna']['channels'],[])
                with self.assertRaises(HTTPError) as bad:
                    post('/api/tv/antenna/scan',{},origin='https://untrusted.test')
                self.assertEqual(bad.exception.code,403)
                with post('/api/tv/antenna/scan',{}) as r:
                    self.assertEqual(r.status,202)
                for _ in range(120):
                    if tuner.status()['scan_state']=='ready':break
                    time.sleep(.02)
                self.assertEqual(tuner.status()['scan_state'],'ready')
                with post('/api/player/play',{'kind':'antenna','index':0}) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertEqual(player.calls[-1][1],'TV Globo HD')
                for bad_index in (-1,2,True,'0'):
                    with self.assertRaises(HTTPError) as err:
                        post('/api/player/play',{'kind':'antenna','index':bad_index})
                    self.assertEqual(err.exception.code,400)
                with post('/api/player/stop',{}) as r:
                    self.assertTrue(json.load(r)['ok'])
                self.assertFalse(tuner.status()['playing'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=4)

    def test_iso_dependencies_and_tv_ui(self):
        build=(ROOT/'linux-live'/'build-iso.sh').read_text()
        packages=(ROOT/'linux-live'/'packages.list.chroot').read_text()
        ui=(ROOT/'app'/'app.js').read_text()
        page=(ROOT/'app'/'index.html').read_text()
        self.assertIn('antenna_tv.py',build)
        self.assertIn('w-scan\n',packages)
        self.assertIn('dvb-tools\n',packages)
        self.assertIn("'/api/tv/antenna'",ui)
        self.assertIn("kind:'antenna'",ui)
        self.assertIn('id="antenna-scan"',page)
        self.assertIn('ALPHA 0.19',page)


if __name__=='__main__':
    unittest.main()
