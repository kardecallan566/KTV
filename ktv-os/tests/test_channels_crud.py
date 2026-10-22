"""Channel CRUD, favorites, ordering, USB backup and local API regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen, Request

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktv_channels', HERE/'channel_store.py')
channels_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(channels_mod)
spec2 = importlib.util.spec_from_file_location('ktv_channels_launcher', HERE/'launcher.py')
launch = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(launch)

class FakePlayer:
    def status(self): return {'available':False,'playing':False,'name':None}
    def stop(self): return False
    def close(self): pass

class ChannelCrudTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root/'state'
        self.usb = self.root/'usb'
        self.usb.mkdir()
        self.store = channels_mod.ChannelStore(self.state)
        self.server = launch.KTVOSServer(port=0, state_dir=self.state, player=FakePlayer())
        self.url = 'http://127.0.0.1:{}'.format(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def post(self, url, payload, headers=None):
        meta = {'Content-Type':'application/json'}
        if headers: meta.update(headers)
        req=Request(self.url+url, data=json.dumps(payload).encode('utf-8'),headers=meta,method='POST')
        with urlopen(req,timeout=4) as resp:
            return json.loads(resp.read())

    def test_crud_favorites_order(self):
        first=self.post('/api/channels/change',{'action':'add','name':'Canal A','url':'https://example.org/a.m3u8','category':'Educação'})['channels']
        self.assertEqual(len(first),1)
        a=first[0]['id']
        second=self.post('/api/channels/change',{'action':'add','name':'Canal B','url':'https://example.org/b.mp4'})['channels']
        b=second[-1]['id']
        favored=self.post('/api/channels/change',{'action':'favorite','id':b})['channels']
        self.assertTrue(favored[1]['favorite'])
        moved=self.post('/api/channels/change',{'action':'up','id':b})['channels']
        self.assertEqual(moved[0]['id'],b)
        updated=self.post('/api/channels/change',{'action':'edit','id':a,'name':'Canal editado','url':'https://example.org/c.m3u8','category':'Teste'})['channels']
        self.assertEqual(updated[1]['name'],'Canal editado')
        result=self.post('/api/channels/change',{'action':'delete','id':a})['channels']
        self.assertEqual(len(result),1)
        self.assertEqual(self.store.load()[0]['id'],b)

    def test_reject_invalid_and_keep_previous_data(self):
        self.store.change('add',{'name':'Bom', 'url':'https://example.org/valid.m3u8'})
        before=self.store.path.read_bytes()
        for payload in [
            {'action':'add','name':'Ruim','url':'file:///etc/passwd'},
            {'action':'add','name':'Ruim','url':'https://user:pass@example.org/live.m3u8'},
            {'action':'add','name':'Ruim','url':'javascript:alert(1)'},
            {'action':'delete','id':'not-found'},
            {'action':'unsupported','id':'nope'}
        ]:
            with self.assertRaises(HTTPError) as e: self.post('/api/channels/change',payload)
            self.assertEqual(e.exception.code,400)
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_usb_backup_restore_and_explicit_confirmation_api(self):
        self.store.change('add',{'name':'Original', 'url':'https://example.org/a.m3u8'})
        with mock.patch.object(launch,'usb_mounts',return_value={'usb-42':(self.usb,'USB seguro')}):
            backup=self.post('/api/channels/usb-backup',{'device':'usb-42'})
            self.assertTrue(backup['ok'])
            path=self.usb/channels_mod.BACKUP_NAME
            self.assertTrue(path.exists())
            contents=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(contents['format'],channels_mod.FORMAT)
            self.store.change('add',{'name':'Segundo', 'url':'https://example.org/b.mp4'})
            restored=self.post('/api/channels/usb-restore',{'device':'usb-42'})
            self.assertEqual(len(restored['channels']),1)
            with self.assertRaises(HTTPError) as ex:self.post('/api/channels/usb-backup',{'device':'/etc'})
            self.assertEqual(ex.exception.code,404)

    def test_usb_bad_backup_does_not_erase_channels(self):
        self.store.change('add',{'name':'Original', 'url':'https://example.org/a.m3u8'})
        (self.usb/channels_mod.BACKUP_NAME).write_text('{"format":"ktv-os-channels-v1","channels":[{"url":"file:///etc/passwd","name":"Injected"}]}')
        with mock.patch.object(launch,'usb_mounts',return_value={'usb-x':(self.usb,'USB seguro')}):
            with self.assertRaises(HTTPError) as ex:self.post('/api/channels/usb-restore',{'device':'usb-x'})
            self.assertEqual(ex.exception.code,400)
        self.assertEqual(self.store.load()[0]['name'],'Original')

    def test_legacy_json_remains_compatible(self):
        self.state.mkdir(exist_ok=True)
        self.store.path.write_text(json.dumps({'channels':[{'name':'Velho','url':'http://example.org/stream.m3u8','category':'TV'}]}))
        legacy=self.store.load()
        self.assertEqual(legacy[0]['name'],'Velho')
        self.assertRegex(legacy[0]['id'],r'^[0-9a-f]{32}$')
        self.store.change('favorite',{'id':legacy[0]['id']})
        self.assertTrue(self.store.load()[0]['favorite'])

    def test_usb_symlink_is_not_overwritten(self):
        other=self.root/'other.json'
        other.write_text('untouched')
        (self.usb/channels_mod.BACKUP_NAME).symlink_to(other)
        with self.assertRaises(channels_mod.ChannelError):
            self.store.export_to_usb(self.usb)
        self.assertEqual(other.read_text(),'untouched')

if __name__ == '__main__':
    unittest.main()
