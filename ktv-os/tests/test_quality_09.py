"""Alpha 0.9: quality profiles and player diagnostic safety."""
import importlib.util
from pathlib import Path
import socket
import tempfile
import threading
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ktv_quality_player',ROOT/'player.py')
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class Process:
    def __init__(self):self.running=True
    def poll(self):return None if self.running else 0
    def terminate(self):self.running=False
    def wait(self,timeout=3):return 0
    def kill(self):self.running=False

class QualityTests(unittest.TestCase):
    def test_quality_options_apply_only_to_hls(self):
        calls=[]
        def launch(args,**kw):
            calls.append(args)
            return Process()
        player=p.NativePlayer(executable='mpv',popen=launch)
        for profile,bitrate in [('economy','min'),('balanced','4000000'),('best','max')]:
            player.play('https://example.org/live.m3u8','TV',quality=profile)
            self.assertIn('--hls-bitrate='+bitrate,calls[-1])
            self.assertEqual(calls[-1][-2:],[ '--','https://example.org/live.m3u8'])
            self.assertEqual(player.status()['quality'],profile)
        player.play('/tmp/clip.mp4','Clip',quality='best')
        self.assertFalse(any(x.startswith('--hls-bitrate=') for x in calls[-1]))
        player.close()

    def test_invalid_profile_cannot_inject_flags(self):
        player=p.NativePlayer(executable='mpv',popen=lambda *a,**k:Process())
        for v in ('--vf=evil',None,{},True,'experimental'):
            with self.assertRaises(ValueError):player.play('https://example.org/x.m3u8','TV',quality=v)

    def test_invalid_telemetry_values_are_suppressed(self):
        self.assertIsNone(p._number(float('nan'),200))
        self.assertIsNone(p._number(-1,200))
        self.assertIsNone(p._number(300,200))
        self.assertIsNone(p._number(True,200))
        self.assertEqual(p._number(23.456,200),23.46)

    @unittest.skipUnless(hasattr(socket,'AF_UNIX'),'Unix sockets needed')
    def test_private_ipc_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            address=str(Path(tmp)/'mpv.sock')
            ready=threading.Event()
            def fake_server():
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as srv:
                    srv.bind(address)
                    srv.listen(1)
                    ready.set()
                    client,_=srv.accept()
                    with client:
                        payload=b''
                        while payload.count(b'\n') < len(p.VIDEO_PROPERTIES):
                            payload+=client.recv(8192)
                        props={'video-params':{'w':1280,'h':720},
                               'video-codec':'h264','container-fps':30,
                               'frame-drop-count':3,'demuxer-cache-duration':4.5,
                               'hwdec-current':'no'}
                        for line in payload.split(b'\n'):
                            if not line:continue
                            request=json.loads(line)
                            name=request['command'][1]
                            if name not in props:continue
                            response={'request_id':request['request_id'],
                                      'error':'success','data':props[name]}
                            client.sendall((json.dumps(response)+'\n').encode())
            worker=threading.Thread(target=fake_server,daemon=True)
            worker.start()
            self.assertTrue(ready.wait(2))
            player=p.NativePlayer(executable='mpv')
            player.ipc_path=address
            state=player._read_video_state()
            self.assertEqual((state['width'],state['height']),(1280,720))
            self.assertEqual(state['dropped_frames'],3)
            self.assertEqual(state['buffer_seconds'],4.5)
            worker.join(timeout=2)

if __name__=='__main__':unittest.main()
