"""KTV OS Alpha 0.19: long-lived Pluto TV HLS recovery and safety guards."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pluto_catalog import PlutoCatalog
from pluto_recovery import PlutoRecovery,USER_QUIT_CODE,STALL_SECONDS
from player import NativePlayer
from launcher import KTVOSServer

ID='5f120e94a5714d00074576a1'
BASE='https://ipv4.pluto.tv/api/tn/video/playout/v2/stitch/hls/channel/'+ID+'/master.m3u8?jwt='
def playlist(jwt):
    return '#EXTM3U\n#EXTINF:-1 group-title="Cinema",Pluto Cine\n'+BASE+jwt+'\n'


class DummyProcess:
    def __init__(self):self.code=None
    def poll(self):return self.code
    def terminate(self):self.code=-15
    def wait(self,timeout=3):return self.code
    def kill(self):self.code=-9


class FakePlayer:
    def __init__(self):self.calls=[];self.running=True;self.code=None;self.video=None
    def play(self,url,name):
        self.calls.append((url,name));self.running=True;self.code=None
        return self.status()
    def stop(self):self.running=False;self.code=None
    def close(self):self.stop()
    def status(self):
        return {'available':True,'playing':self.running,
                'video':self.video,'exit_code':None if self.running else self.code}


class RecoveryTests(unittest.TestCase):
    def test_force_refresh_updates_only_pluto_tokens(self):
        tick=[0]
        calls=[]
        def fetch():
            calls.append(1)
            return playlist('SESSION'+str(len(calls)))
        catalog=PlutoCatalog(fetcher=fetch,clock=lambda:tick[0])
        one,_=catalog.play_url(ID)
        two,_=catalog.play_url(ID)
        self.assertEqual(one,two)
        self.assertEqual(len(calls),1)
        refreshed,_=catalog.play_url(ID,force_refresh=True)
        self.assertNotEqual(refreshed,one)
        self.assertEqual(len(calls),2)
        self.assertNotIn('jwt',json.dumps(catalog.listing()))
        with self.assertRaises(ValueError):
            catalog.play_url('https://evil.example',force_refresh=True)

    def test_auto_reconnect_after_exit_and_obeys_quality(self):
        clock=[100.]
        tokens=[]
        def fetch():
            tokens.append(len(tokens))
            return playlist('JWT'+str(len(tokens)))
        catalog=PlutoCatalog(fetcher=fetch,clock=lambda:clock[0])
        first,_=catalog.play_url(ID)
        player=FakePlayer();player.play(first,'Pluto Cine')
        ctl=PlutoRecovery(catalog,player,clock=lambda:clock[0],threaded=False)
        try:
            ctl.activate(ID,'economy','compatible')
            clock[0]+=30
            ctl.tick()
            self.assertEqual(len(player.calls),1)
            player.running=False;player.code=1
            clock[0]+=1
            ctl.tick()
            self.assertEqual(len(player.calls),2)
            self.assertNotEqual(player.calls[0][0],player.calls[1][0])
            self.assertEqual(ctl.status()['phase'],'playing')
            self.assertEqual(ctl.session,(ID,'economy','compatible'))
            self.assertEqual(len(tokens),2)
            self.assertNotIn('jwt',json.dumps(ctl.status()))
        finally:ctl.close()

    def test_keeps_working_stream_and_stall_recovery(self):
        clock=[0.]
        catalog=PlutoCatalog(fetcher=lambda:playlist('TOKEN'),clock=lambda:clock[0])
        player=FakePlayer();player.video={'time_pos':5.0,'paused':False,'eof_reached':False}
        ctl=PlutoRecovery(catalog,player,clock=lambda:clock[0],threaded=False)
        try:
            ctl.activate(ID,'balanced','default')
            for t,p in [(5,5.0),(20,9.0),(50,25.0),(110,70.0),(160,100.0)]:
                clock[0]=t;player.video['time_pos']=p;ctl.tick()
            self.assertEqual(len(player.calls),0)  # No unnecessary restarts
            player.video['paused']=True
            clock[0]+=200
            ctl.tick()  # Never reconnect deliberately paused media
            self.assertEqual(len(player.calls),0)
            player.video['paused']=False
            player.video['time_pos']=110.0
            clock[0]+=1;ctl.tick()
            clock[0]+=STALL_SECONDS+1
            ctl.tick()
            self.assertEqual(len(player.calls),1)
            self.assertEqual(ctl.status()['phase'],'playing')
        finally:ctl.close()

    def test_user_q_cancel_prevents_background_restart(self):
        clock=[10.]
        catalog=PlutoCatalog(fetcher=lambda:playlist('VALID'),clock=lambda:clock[0])
        p=FakePlayer();ctl=PlutoRecovery(catalog,p,clock=lambda:clock[0],threaded=False)
        try:
            ctl.activate(ID,'balanced','default')
            p.running=False;p.code=USER_QUIT_CODE
            ctl.tick()
            self.assertFalse(ctl.status()['active'])
            self.assertEqual(p.calls,[])
            ctl.activate(ID,'best','default')
            ctl.cancel();p.running=False;p.code=1
            ctl.tick()
            self.assertEqual(p.calls,[])
        finally:ctl.close()

    def test_backoff_and_bounded_failures(self):
        clock=[100.]
        def failure():raise OSError('jwt expired private info!')
        catalog=PlutoCatalog(fetcher=failure,clock=lambda:clock[0])
        p=FakePlayer();p.running=False;p.code=1
        ctl=PlutoRecovery(catalog,p,clock=lambda:clock[0],threaded=False)
        try:
            ctl.activate(ID,'best','default')
            for i in range(7):
                ctl.tick()
                state=ctl.status()
                self.assertNotIn('jwt',json.dumps(state))
                if state['phase']=='attention':break
                self.assertEqual(state['phase'],'waiting')
                clock[0]+=state['retry_seconds']+1
            self.assertEqual(ctl.status()['phase'],'attention')
            self.assertEqual(ctl.status()['attempts'],7)
            clock[0]+=99999;ctl.tick()
            self.assertEqual(ctl.status()['attempts'],7)
            ctl.cancel()
            self.assertFalse(ctl.status()['active'])
        finally:ctl.close()

    def test_cancel_mid_fetch_prevents_reopening_stream(self):
        entered=threading.Event();release=threading.Event()
        def fetch():
            entered.set()
            release.wait(2)
            return playlist('REFRESHED')
        catalog=PlutoCatalog(fetcher=fetch)
        p=FakePlayer();p.running=False;p.code=1
        ctl=PlutoRecovery(catalog,p,threaded=False)
        try:
            ctl.activate(ID,'balanced','default')
            t=threading.Thread(target=ctl.tick,daemon=True)
            t.start()
            self.assertTrue(entered.wait(1))
            ctl.cancel()
            release.set();t.join(3)
            self.assertEqual(p.calls,[])
        finally:release.set();ctl.close()

    def test_pluto_mpv_has_exit_binding_keep_open_and_small_cache(self):
        calls=[]
        player=NativePlayer(executable='mpv',
                            popen=lambda cmd,**kw:(calls.append(cmd) or DummyProcess()))
        try:
            player.play(BASE+'TEST','Cine',quality='balanced')
            args=calls[-1]
            self.assertIn('--keep-open=yes',args)
            self.assertIn('--network-timeout=20',args)
            self.assertIn('--cache-secs=15',args)
            binding=next(x for x in args if x.startswith('--input-conf='))
            data=Path(binding.partition('=')[2]).read_text()
            self.assertIn('q quit 77',data)
            self.assertIn('CLOSE_WIN quit 77',data)
            self.assertNotIn('shell',str(args))
            player.stop()
            player.play('https://example.org/movie.mp4','Movie')
            self.assertNotIn('--keep-open=yes',calls[-1])
            self.assertFalse(any(x.startswith('--input-conf=') for x in calls[-1]))
        finally:player.close()

    def test_api_stop_cancels_pending_recovery_and_status_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog=PlutoCatalog(fetcher=lambda:playlist('TOKEN'))
            p=FakePlayer()
            server=KTVOSServer(port=0,state_dir=Path(folder),pluto=catalog,player=p)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            def post(path,content):
                return urlopen(Request(base+path,method='POST',
                    data=json.dumps(content).encode(),headers={'Content-Type':'application/json'}),timeout=4)
            try:
                with post('/api/player/play',{'kind':'pluto','id':ID}) as response:
                    self.assertTrue(json.load(response)['ok'])
                with urlopen(base+'/api/player/status') as response:
                    d=json.load(response)
                    self.assertTrue(d['recovery']['active'])
                    self.assertNotIn('jwt',json.dumps(d))
                with post('/api/player/stop',{}) as response:
                    self.assertTrue(json.load(response)['ok'])
                self.assertFalse(server.pluto_recovery.status()['active'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__=='__main__':unittest.main()
