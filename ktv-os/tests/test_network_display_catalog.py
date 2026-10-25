"""KTV OS 0.8: networking, HDMI mirror and institutional catalog tests."""
import importlib.util
import subprocess
import tempfile
from pathlib import Path
import threading
import json
import unittest
from urllib.request import urlopen,Request
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

network=load('ktv_network08','network.py')
display=load('ktv_display08','display_layout.py')
channels=load('ktv_public08','public_channels.py')
servermod=load('ktv_launcher08','launcher.py')

class MockRunner:
    def __init__(self):
        self.calls=[]
    def __call__(self,args,**kwargs):
        self.calls.append((args,kwargs))
        cmd=' '.join(args)
        if 'device status' in cmd:
            return subprocess.CompletedProcess(args,0,'wlp2s0:wifi:connected:MinhaRede\neth0:ethernet:disconnected:--\n','')
        if 'radio wifi' in cmd:
            return subprocess.CompletedProcess(args,0,'enabled\n','')
        if 'device wifi list' in cmd:
            return subprocess.CompletedProcess(args,0,'*:MinhaRede:89:WPA2\n:Casa\\:Piso1:75:WPA2\n:Aberta:60:--\n','')
        return subprocess.CompletedProcess(args,0,'','')

class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.runner=MockRunner()
        self.net=network.NetworkManager(runner=self.runner,which=lambda _: '/usr/bin/nmcli')
    def test_status_ethernet_and_wifi(self):
        status=self.net.status()
        self.assertTrue(status['available'])
        self.assertEqual(status['devices'][0]['connection'],'MinhaRede')
        self.assertEqual(status['devices'][1]['kind'],'ethernet')
        self.assertTrue(status['wifi_enabled'])
    def test_scan_and_escape(self):
        result=self.net.scan()['networks']
        self.assertEqual(len(result),3)
        self.assertEqual(result[0]['ssid'],'MinhaRede')
        self.assertTrue(result[0]['connected'])
        self.assertIn('Casa:Piso1',[x['ssid'] for x in result])
        self.assertFalse(next(x for x in result if x['ssid']=='Aberta')['secure'])
    def test_password_not_in_command_arguments(self):
        secret='SenhaForte!2026'
        self.net.connect('Casa:Piso1',secret)
        args,kwargs=self.runner.calls[-1]
        self.assertNotIn(secret,' '.join(args))
        self.assertEqual(kwargs['input'],secret+'\n')
        self.assertEqual(kwargs['timeout'],35)
    def test_invalid_network_parameters(self):
        for ssid in ('', 'x'*33,'line\nbreak'):
            with self.assertRaises(network.NetworkError):self.net.connect(ssid,'something')
        for pw in (None,'bad\npass','x'*129):
            with self.assertRaises(network.NetworkError):self.net.connect('Casa',pw)
        with self.assertRaises(network.NetworkError):self.net.set_wifi('off')
    def test_nmcli_unavailable(self):
        n=network.NetworkManager(which=lambda _:None)
        self.assertFalse(n.status()['available'])
        with self.assertRaises(network.NetworkError):n.scan()

class DisplayTests(unittest.TestCase):
    def test_mirror_same_resolution(self):
        calls=[]
        raw=('Screen 0: minimum 320 x 200\n'
             'eDP-1 connected primary 1920x1080+0+0\n'
             '   1920x1080 60.00*+\n   1280x720 60.00\n'
             'HDMI-1 connected 1920x1080+1920+0\n'
             '   1920x1080 60.00*+\n   1280x720 60.00\n')
        def runner(args,**kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args,0,raw if '--query' in args else '','')
        response=display.mirror(runner=runner,which=lambda _:'/usr/bin/xrandr')
        self.assertIn('Espelhamento',response)
        self.assertIn('--same-as',calls[-1])
        self.assertEqual(calls[-1][calls[-1].index('--same-as')+1],'HDMI-1')
        self.assertIn('1920x1080',calls[-1])
    def test_no_hdmi_does_not_turn_off_internal_display(self):
        def runner(args,**kwargs):
            return subprocess.CompletedProcess(args,0,'eDP-1 connected primary 1280x720+0+0\n   1280x720 60.0*','')
        message=display.mirror(runner=runner,which=lambda _:'xrandr')
        self.assertIn('Sem HDMI',message)
    def test_no_common_mode_does_not_change_layout(self):
        invoked=[]
        def runner(args,**kwargs):
            invoked.append(args)
            return subprocess.CompletedProcess(args,0,
                 'eDP-1 connected 1024x768+0+0\n   1024x768 60.00\n'
                 'HDMI-1 connected 1920x1080+1024+0\n   1920x1080 60.00\n','')
        msg=display.mirror(runner=runner,which=lambda _:'xrandr')
        self.assertIn('Sem resolucao comum',msg)
        self.assertEqual(len(invoked),1)

class CatalogTests(unittest.TestCase):
    def test_official_https_hosts_and_fixed_selection(self):
        saved=channels.validated_catalog()
        self.assertGreaterEqual(len(saved),3)
        for item in saved:
            self.assertTrue(item['url'].startswith('https://'))
            self.assertTrue(item['url'].endswith('.m3u8'))
            self.assertIn(item['url'].split('/')[2],channels.ALLOWED_HOSTS)
            self.assertIsNotNone(channels.public_channel(item['id']))
        self.assertIsNone(channels.public_channel('http://evil.invalid/x.m3u8'))

class DummyPlayer:
    def __init__(self):self.calls=[]
    def status(self):return {'available':True,'playing':False,'name':None}
    def play(self,url,name):
        self.calls.append((url,name));return self.status()
    def close(self):pass
    def stop(self):pass
class DummyHardware:
    def close(self):pass
class DummyCEC:
    def close(self):pass
class ApiTests(unittest.TestCase):
    def test_catalog_play_security_and_wifi_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            player=DummyPlayer()
            net=NetworkTests().net if False else network.NetworkManager(runner=MockRunner(),which=lambda _:'nmcli')
            srv=servermod.KTVOSServer(port=0,state_dir=directory,player=player,hardware=DummyHardware(),cec=DummyCEC(),network=net)
            thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
            host='http://127.0.0.1:{}'.format(srv.server_address[1])
            def post(path,payload,headers=None):
                h={'Content-Type':'application/json'};h.update(headers or {})
                r=Request(host+path,data=json.dumps(payload).encode(),method='POST',headers=h)
                with urlopen(r,timeout=5) as response:return json.loads(response.read())
            try:
                with urlopen(host+'/api/public-channels',timeout=4) as resp:
                    catalog=json.loads(resp.read())['channels']
                result=post('/api/player/play',{'kind':'public','id':catalog[0]['id']})
                self.assertTrue(result['ok'])
                self.assertEqual(player.calls[-1][0],catalog[0]['url'])
                with self.assertRaises(HTTPError) as blocked:
                    post('/api/player/play',{'kind':'public','id':'http://localhost/secrets.m3u8'})
                self.assertEqual(blocked.exception.code,400)
                with self.assertRaises(HTTPError) as blocked:
                    post('/api/network/connect',{'ssid':'X','password':'secret'},headers={'Origin':'https://evil.invalid'})
                self.assertEqual(blocked.exception.code,403)
                result=post('/api/network/connect',{'ssid':'X','password':'secret'})
                self.assertTrue(result['ok'])
                self.assertNotIn('secret',json.dumps(result))
            finally:
                srv.shutdown();srv.server_close();thread.join(timeout=3)

if __name__=='__main__':
    unittest.main()
