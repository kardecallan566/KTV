"""Unit tests for optional HDMI-CEC input (no physical Samsung or adaptor required)."""
import importlib.util
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import json

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

cec=load('ktv_cec_test','cec_bridge.py')
api=load('ktv_launcher_cec_test','launcher.py')


class FakeProcess:
    def __init__(self, lines):
        self.stdout=io.StringIO(lines)
        self.stdin=io.StringIO()
        self.returncode=None
    def poll(self):return self.returncode
    def terminate(self):self.returncode=0
    def wait(self,timeout=2):return 0
    def kill(self):self.returncode=-9


class CECTests(unittest.TestCase):
    def test_only_whitelisted_key_press(self):
        valid={
            'DEBUG: key pressed: up (1)':'ArrowUp',
            'key pressed: down (2, 0)':'ArrowDown',
            'DEBUG: key pressed: left (3)':'ArrowLeft',
            'key pressed: right (4)':'ArrowRight',
            'DEBUG: key pressed: select (0, 0)':'Enter',
            'key pressed: exit (d)':'Escape',
            'key pressed: root menu (9)':'Home',
        }
        for message,key in valid.items():
            self.assertEqual(cec.decode_key(message),key)
        for message in ['key released: select (0)','power on (0)',
                        'standby (36)','key pressed: power (40)',
                        'key pressed: source (34)',
                        'authentication token', 'key pressed: up (xyz)']:
            self.assertIsNone(cec.decode_key(message))
        self.assertIsNone(cec.decode_key('A'*3000))

    def test_cec_unavailable_requires_explicit_action(self):
        bridge=cec.CECBridge(which=lambda _:None)
        self.assertFalse(bridge.status()['enabled'])
        self.assertFalse(bridge.status()['supported'])
        with self.assertRaisesRegex(cec.CECError,'cec-client indisponivel'):
            bridge.enable()
        self.assertFalse(bridge.status()['running'])
        bridge.close()

    def test_start_args_input_order_and_shutdown(self):
        calls=[]
        proc=FakeProcess('key pressed: select (0)\nkey pressed: power (40)\nkey pressed: up (1)\n')
        def spawn(argv,**kwargs):
            calls.append((argv,kwargs))
            return proc
        times=iter([1.0,1.1,1.9])
        bridge=cec.CECBridge(popen=spawn,which=lambda _: '/usr/bin/cec-client',clock=lambda:next(times))
        bridge.enable()
        self.assertEqual(calls[0][0],['/usr/bin/cec-client','-t','p','-d','8'])
        self.assertNotIn('shell',calls[0][1])
        self.assertEqual(calls[0][1]['stdin'].__class__,__import__('subprocess').PIPE.__class__)
        bridge.reader.join(timeout=2)
        ev=bridge.events_since(0)
        self.assertEqual([x['key'] for x in ev['events']],['Enter','ArrowUp'])
        self.assertFalse(bridge.status()['running'])
        bridge.disable()
        self.assertEqual(bridge.events_since(0)['events'],[])

    def test_deduplicates_keypress_and_limits_event_buffer(self):
        times=iter([1.0,1.05,1.3])
        b=cec.CECBridge(which=lambda _:None,clock=lambda:next(times,2.0))
        b._deliver('ArrowRight')
        b._deliver('ArrowRight')
        b._deliver('ArrowRight')
        self.assertEqual(len(b.events_since(0)['events']),2)
        for i in range(200):
            b.last_at=-10.0
            b._deliver('ArrowDown' if i%2 else 'ArrowUp')
        result=b.events_since(0)
        self.assertLessEqual(len(result['events']),cec.MAX_EVENTS)
        self.assertEqual(result['last'],b.serial)
        with self.assertRaises(cec.CECError):b.events_since(-1)
        with self.assertRaises(cec.CECError):b.events_since(True)

class DummyPlayer:
    def status(self):return {'available':False,'playing':False,'name':None}
    def close(self):return
class DummyHardware:
    def close(self):return
class StubCEC:
    def __init__(self):self.running=False;self.closed=False
    def status(self):return {'supported':True,'enabled':self.running,'running':self.running,'error':'','last_key':''}
    def enable(self):self.running=True;return self.status()
    def disable(self):self.running=False;return self.status()
    def events_since(self,since):
        if since<0:raise cec.CECError('Invalid')
        return {'last':1,'events':[{'id':1,'key':'Enter'}] if since<1 else []}
    def close(self):self.closed=True

class CECAPITests(unittest.TestCase):
    def test_http_api_and_origin(self):
        with tempfile.TemporaryDirectory() as dirname:
            c=StubCEC()
            server=api.KTVOSServer(port=0,state_dir=dirname,player=DummyPlayer(),hardware=DummyHardware(),cec=c)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            host='http://127.0.0.1:{}'.format(server.server_address[1])
            try:
                def post(url,headers=None):
                    h={'Content-Type':'application/json'}
                    h.update(headers or {})
                    req=Request(host+url,data=b'{}',headers=h,method='POST')
                    with urlopen(req,timeout=5) as response:return json.loads(response.read())
                with urlopen(host+'/api/cec/status',timeout=5) as resp:
                    self.assertFalse(json.loads(resp.read())['cec']['running'])
                self.assertTrue(post('/api/cec/enable')['cec']['enabled'])
                with urlopen(host+'/api/cec/events?after=0',timeout=5) as resp:
                    self.assertEqual(json.loads(resp.read())['events'][0]['key'],'Enter')
                with self.assertRaises(HTTPError) as blocked:
                    post('/api/cec/enable',{'Origin':'https://untrusted.example'})
                self.assertEqual(blocked.exception.code,403)
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(host+'/api/cec/events?after=not-int',timeout=5)
                self.assertEqual(blocked.exception.code,400)
                self.assertFalse(post('/api/cec/disable')['cec']['enabled'])
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)
                self.assertTrue(c.closed)

if __name__=='__main__':unittest.main()
