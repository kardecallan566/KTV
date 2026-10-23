"""KTV OS 0.6 hardware integration tests: no real HDMI/audio changes."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
import json
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
hw=load('ktv_hardware_tests','hardware.py')
api=load('ktv_os_api_tests','launcher.py')


class FakeTimer:
    def __init__(self,delay,callback):
        self.delay=delay;self.callback=callback;self.started=False;self.cancelled=False
    def start(self):self.started=True
    def cancel(self):self.cancelled=True
    def fire(self):
        if not self.cancelled:self.callback()


class FakeRunner:
    def __init__(self):
        self.mode='1920x1080'
        self.sink='alsa_output.pci-0000_00_1f.3.analog-stereo'
        self.volume=55;self.muted=False;self.calls=[]
    def __call__(self,args,**kwargs):
        self.calls.append(args)
        if args==['xrandr','--query']:
            result='Screen 0: minimum 8 x 8, current 1920 x 1080\n'
            result+='HDMI-1 connected primary '+self.mode+'+0+0\n'
            result+='  1920x1080 60.00{}+\n'.format('*' if self.mode=='1920x1080' else '')
            result+='  1280x720 60.00{}\n'.format('*' if self.mode=='1280x720' else '')
            result+='eDP-1 disconnected\n'
        elif args[:3]==['xrandr','--output','HDMI-1'] and args[3]=='--mode':
            self.mode=args[4];result=''
        elif args==['pactl','list','short','sinks']:
            result=('0\talsa_output.pci-0000_00_1f.3.analog-stereo\tmodule\tS16LE 2ch 44100Hz\tRUNNING\n'
                    '1\talsa_output.pci-0000_01_00.1.hdmi-stereo\tmodule\tS16LE 2ch 48000Hz\tSUSPENDED\n')
        elif args==['pactl','info']:
            result='Server String: /run/user/1000/pulse/native\nDefault Sink: '+self.sink+'\n'
        elif args==['pactl','get-sink-volume','@DEFAULT_SINK@']:
            result='Volume: front-left: 36100 / {}% / 0.00 dB\n'.format(self.volume)
        elif args==['pactl','get-sink-mute','@DEFAULT_SINK@']:
            result='Mute: '+('yes' if self.muted else 'no')+'\n'
        elif args[:2]==['pactl','set-default-sink']:
            self.sink=args[2];result=''
        elif args[:3]==['pactl','set-sink-volume','@DEFAULT_SINK@']:
            self.volume=int(args[3][:-1]);result=''
        elif args==['pactl','set-sink-mute','@DEFAULT_SINK@','toggle']:
            self.muted=not self.muted;result=''
        else:
            return subprocess.CompletedProcess(args,1,'','Command unavailable')
        return subprocess.CompletedProcess(args,0,result,'')


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.runner=FakeRunner();self.timers=[]
        def make_timer(delay,callback):
            t=FakeTimer(delay,callback);self.timers.append(t);return t
        self.manager=hw.HardwareManager(runner=self.runner,timer_factory=make_timer)
        self.patch=mock.patch.object(hw.shutil,'which',return_value='/usr/bin/fake')
        self.patch.start()
    def tearDown(self):
        self.manager.close();self.patch.stop()

    def test_discover_hdmi_resolution_audio(self):
        state=self.manager.status()
        self.assertTrue(state['display']['available'])
        self.assertEqual(state['display']['outputs'][0]['current'],'1920x1080')
        self.assertEqual(state['display']['outputs'][0]['modes'],['1920x1080','1280x720'])
        self.assertTrue(state['audio']['available'])
        self.assertEqual(len(state['audio']['sinks']),2)
        self.assertEqual(state['audio']['volume'],55)

    def test_temporary_video_mode_automatic_rollback(self):
        response=self.manager.preview('HDMI-1','1280x720')
        self.assertTrue(response['pending'])
        self.assertEqual(self.runner.mode,'1280x720')
        self.assertEqual(self.timers[0].delay,20)
        self.assertTrue(self.timers[0].started)
        self.timers[0].fire()
        self.assertEqual(self.runner.mode,'1920x1080')
        self.assertFalse(self.manager.status()['display']['pending'])

    def test_video_confirmation_and_invalid_modes(self):
        response=self.manager.preview('HDMI-1','1280x720')
        with self.assertRaises(hw.HardwareError):
            self.manager.confirm('invalid-token')
        with self.assertRaises(hw.HardwareError):
            self.manager.preview('HDMI-1','1280x720')
        self.manager.confirm(response['token'])
        self.assertTrue(self.timers[0].cancelled)
        self.assertEqual(self.runner.mode,'1280x720')
        with self.assertRaises(hw.HardwareError):
            self.manager.preview('eDP-1','1920x1080')
        with self.assertRaises(hw.HardwareError):
            self.manager.preview('HDMI-1','8000x8000')
        self.assertEqual(self.runner.mode,'1280x720')

    def test_audio_sink_validation_and_volume(self):
        name='alsa_output.pci-0000_01_00.1.hdmi-stereo'
        self.manager.choose_audio(name)
        self.assertEqual(self.runner.sink,name)
        self.manager.set_volume(35)
        self.assertEqual(self.runner.volume,35)
        self.manager.toggle_mute()
        self.assertTrue(self.runner.muted)
        with self.assertRaises(hw.HardwareError):
            self.manager.choose_audio('--exec=bad')
        for volume in (-1,101,True,'55'):
            with self.assertRaises(hw.HardwareError):
                self.manager.set_volume(volume)

    def test_missing_tools_are_graceful(self):
        with mock.patch.object(hw.shutil,'which',return_value=None):
            state=self.manager.status()
            self.assertFalse(state['display']['available'])
            self.assertFalse(state['audio']['available'])
            with self.assertRaises(hw.HardwareError):
                self.manager.preview('HDMI-1','1920x1080')


class StubPlayer:
    def status(self):return {'available':False,'playing':False,'name':None}
    def close(self):pass
    def stop(self):pass


class HardwareAPITests(unittest.TestCase):
    def test_api_commands_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as dirname:
            class Stub:
                def __init__(self):self.mode=None;self.sink=None
                def status(self):return {'display':{'available':False},'audio':{'available':False}}
                def preview(self,output,mode):
                    self.mode=(output,mode);return {'pending':False,'message':'ok'}
                def set_volume(self,volume):
                    if type(volume) is not int:raise hw.HardwareError('volume invalid')
                    return {'message':'ok'}
                def close(self):pass
            stub=Stub()
            server=api.KTVOSServer(port=0,state_dir=dirname,player=StubPlayer(),hardware=stub)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            host='http://127.0.0.1:{}'.format(server.server_address[1])
            try:
                with urlopen(host+'/api/hardware',timeout=4) as r:
                    self.assertEqual(json.loads(r.read())['hardware']['display']['available'],False)
                def request(path,data,origin=None):
                    headers={'Content-Type':'application/json'}
                    if origin:headers['Origin']=origin
                    q=Request(host+path,data=json.dumps(data).encode(),headers=headers,method='POST')
                    with urlopen(q,timeout=4) as r:return json.loads(r.read())
                data=request('/api/hardware/video/preview',{'output':'HDMI-1','mode':'1920x1080'})
                self.assertTrue(data['ok'])
                self.assertEqual(stub.mode,('HDMI-1','1920x1080'))
                with self.assertRaises(HTTPError) as e:
                    request('/api/hardware/audio/volume',{'volume':'loud'})
                self.assertEqual(e.exception.code,400)
                with self.assertRaises(HTTPError) as e:
                    request('/api/hardware/video/preview',{'output':'HDMI-1','mode':'1280x720'},origin='https://attacker.invalid')
                self.assertEqual(e.exception.code,403)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
