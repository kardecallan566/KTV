"""Checkpoint 0.8: safe shutdown, HDMI-only/mirror preview + full rollback."""
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/file)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

system=load('ktv_system_actions_test','system_actions.py')
display=load('ktv_layout_test','display_layout.py')
hardware=load('ktv_hardware_layout_test','hardware.py')
api=load('ktv_api_layout_test','launcher.py')

XRANDR='''Screen 0: minimum 8 x 8, current 3200 x 1080, maximum 32767 x 32767
eDP-1 connected primary 1280x720+0+0 (normal left inverted right x axis y axis)
   1920x1080 60.00 +
   1280x720 60.00*+
HDMI-A-0 connected 1920x1080+1280+0 (normal left inverted right x axis y axis)
   1920x1080 60.00*+
   1280x720 60.00 +
'''

class FakeTimer:
    def __init__(self,delay,action):
        self.delay=delay;self.action=action;self.daemon=False;self.cancelled=False
    def start(self):pass
    def cancel(self):self.cancelled=True
    def fire(self):
        if not self.cancelled:self.action()

class FakeXrandr:
    def __init__(self):
        self.calls=[]
    def __call__(self,args,**kwargs):
        self.calls.append(args)
        return subprocess.CompletedProcess(args,0,XRANDR if args==['xrandr','--query'] else '','')

class LayoutTests(unittest.TestCase):
    def test_detect_hdmi_a_0_and_old_extended_coordinates(self):
        screens=display.outputs(XRANDR)
        self.assertEqual(screens[0]['mode'],'1280x720')
        self.assertEqual(screens[1]['x'],1280)
        self.assertTrue(screens[1]['external'])
        self.assertTrue(screens[0]['primary'])

    def test_hdmi_only_switch_and_complete_restore(self):
        screens=display.outputs(XRANDR)
        cmd=display.layout_command(screens,'HDMI-A-0','hdmi_only')
        self.assertIn('--off',cmd)
        self.assertIn('--primary',cmd)
        self.assertIn('HDMI-A-0',cmd)
        restore=display.restore_command(screens)
        self.assertIn('1280x0',restore)
        self.assertIn('1280x720',restore)
        self.assertIn('1920x1080',restore)
        self.assertNotIn('--off',restore)

    def test_mirror_two_screens_at_same_coordinates(self):
        screens=display.outputs(XRANDR)
        cmd=display.layout_command(screens,'HDMI-A-0','mirror')
        self.assertIn('--same-as',cmd)
        self.assertEqual(cmd[cmd.index('--same-as')+1],'HDMI-A-0')
        self.assertEqual(cmd[cmd.index('--mode')+1],'1920x1080')
        self.assertNotIn('--off',cmd)
        with self.assertRaises(ValueError):
            display.layout_command(screens,'eDP-1','hdmi_only')
        with self.assertRaises(ValueError):
            display.layout_command(screens,'HDMI-A-0','unsafe-mode')

    def test_hardware_preview_and_timeout_restore(self):
        runner=FakeXrandr();timers=[]
        def timer_factory(delay,action):
            timer=FakeTimer(delay,action);timers.append(timer);return timer
        manager=hardware.HardwareManager(runner=runner,timer_factory=timer_factory)
        with mock.patch.object(hardware.shutil,'which',return_value='/usr/bin/xrandr'):
            result=manager.preview_layout('HDMI-A-0','hdmi_only')
            self.assertTrue(result['pending'])
            self.assertEqual(timers[0].delay,20)
            self.assertIn('--off',runner.calls[-1])
            with self.assertRaises(hardware.HardwareError):
                manager.preview_layout('HDMI-A-0','mirror')
            timers[0].fire()
            self.assertIn('1280x0',runner.calls[-1])
            self.assertFalse(manager.status()['display']['pending'])
            manager.close()

    def test_hardware_confirmation_keeps_change(self):
        runner=FakeXrandr();timers=[]
        def timer_factory(d,a):
            t=FakeTimer(d,a);timers.append(t);return t
        manager=hardware.HardwareManager(runner=runner,timer_factory=timer_factory)
        with mock.patch.object(hardware.shutil,'which',return_value='/usr/bin/xrandr'):
            result=manager.preview_layout('HDMI-A-0','mirror')
            manager.confirm(result['token'])
            self.assertTrue(timers[0].cancelled)
            self.assertEqual(len(runner.calls),2)
            manager.close()
            self.assertEqual(len(runner.calls),2)

class PowerTests(unittest.TestCase):
    def test_not_enabled_outside_live(self):
        power=system.SystemActions(enabled=False,which=lambda _: '/usr/bin/systemctl')
        self.assertFalse(power.status()['poweroff_available'])
        with self.assertRaises(system.SystemActionError):
            power.poweroff()

    def test_command_is_fixed_and_no_shell(self):
        event=threading.Event()
        received=[]
        def runner(args,**kwargs):
            received.append((args,kwargs));event.set()
            return subprocess.CompletedProcess(args,0,'','')
        power=system.SystemActions(enabled=True,runner=runner,
                                   sleep=lambda _ : None,which=lambda _:'/usr/bin/systemctl')
        self.assertTrue(power.poweroff()['message'])
        self.assertTrue(event.wait(2),'Shutdown worker was not called')
        self.assertEqual(received[0][0],['systemctl','poweroff'])
        self.assertFalse(received[0][1]['check'])
        self.assertNotIn('shell',received[0][1])

    def test_ui_has_power_without_fullscreen_control(self):
        html=(ROOT/'app/index.html').read_text()
        js=(ROOT/'app/app.js').read_text()
        self.assertIn('id="poweroff-button"',html)
        self.assertNotIn('data-action="fullscreen"',html)
        self.assertNotIn('requestFullscreen',js)
        self.assertIn('X-KTV-System-Action',js)
        self.assertIn('display-layout-apply',html)

class Stub:
    def close(self):pass
class StubPlayer(Stub):
    def status(self):return {'available':False,'playing':False}
class StubSystem:
    def __init__(self):self.called=0
    def status(self):return {'poweroff_available':True,'poweroff_pending':False,'error':''}
    def poweroff(self):
        self.called+=1
        return {'message':'ok'}

class SystemApiTests(unittest.TestCase):
    def test_requires_header_origin_and_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            sysactions=StubSystem()
            serv=api.KTVOSServer(port=0,state_dir=root,player=StubPlayer(),
                                 hardware=Stub(),cec=Stub(),system_actions=sysactions)
            thr=threading.Thread(target=serv.serve_forever,daemon=True);thr.start()
            url='http://127.0.0.1:{}'.format(serv.server_address[1])
            def request(headers=None):
                h={'Content-Type':'application/json'}
                h.update(headers or {})
                req=Request(url+'/api/system/poweroff',headers=h,data=b'{}',method='POST')
                with urlopen(req,timeout=3) as resp:return json.loads(resp.read())
            try:
                with urlopen(url+'/api/system/status',timeout=3) as resp:
                    self.assertTrue(json.loads(resp.read())['system']['poweroff_available'])
                for header,expected in (({},403),
                                        ({'X-KTV-System-Action':'confirmed','Origin':'https://outside.invalid'},403)):
                    with self.assertRaises(HTTPError) as blocked:request(header)
                    self.assertEqual(blocked.exception.code,expected)
                self.assertEqual(sysactions.called,0)
                value=request({'X-KTV-System-Action':'confirmed'})
                self.assertTrue(value['ok'])
                self.assertEqual(sysactions.called,1)
            finally:
                serv.shutdown();serv.server_close();thr.join(timeout=2)

if __name__=='__main__': unittest.main()
