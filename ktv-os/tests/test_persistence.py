"""KTV OS 0.5 removable USB persistence and restore security."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

channels = load('ktv_channels05', 'channel_store.py')
persist = load('ktv_persistence05', 'persistence.py')
launcher = load('ktv_launcher05', 'launcher.py')

class FakePlayer:
    def status(self): return {'available': False, 'playing': False, 'name': None}
    def stop(self): return False
    def close(self): return None

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.usb = self.root / 'external_usb'
        self.usb.mkdir()
        self.mounts = {'usb-test': (self.usb, 'Pendrive do usuario')}
        self.store = channels.ChannelStore(self.root / 'live-session')
        self.manager = persist.PersistenceManager(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, name='Canal A'):
        return self.store.change('add', {
            'name': name, 'url': 'https://example.org/channel.m3u8'})

    def test_enroll_and_automatic_restore_after_restart(self):
        self.add()
        result = self.manager.enroll(self.mounts, 'usb-test')
        self.assertTrue(result['enabled'])
        self.assertTrue(result['connected'])
        snapshot = self.usb / persist.FOLDER / persist.SNAPSHOT
        self.assertTrue(snapshot.exists())
        self.store.change('add', {'name': 'Canal B', 'url': 'https://example.org/b.mp4'})
        self.manager.sync(self.mounts)
        restored_store = channels.ChannelStore(self.root / 'new-session')
        restored = persist.PersistenceManager(restored_store)
        state = restored.poll(self.mounts)
        self.assertTrue(state['enabled'])
        self.assertEqual(len(restored_store.load()), 2)
        self.assertEqual(json.loads(snapshot.read_text())['format'], persist.FORMAT)

    def test_disconnected_usb_defers_changes_then_flushes(self):
        self.add()
        self.manager.enroll(self.mounts, 'usb-test')
        self.add('Canal offline')
        missing = self.manager.sync({})
        self.assertTrue(missing['pending'])
        self.assertFalse(missing['connected'])
        self.assertEqual(len(json.loads((self.usb/persist.FOLDER/persist.SNAPSHOT).read_text())['channels']), 1)
        connected = self.manager.poll(self.mounts)
        self.assertFalse(connected['pending'])
        self.assertEqual(len(json.loads((self.usb/persist.FOLDER/persist.SNAPSHOT).read_text())['channels']), 2)

    def test_disable_is_effective_after_reboot(self):
        self.add()
        self.manager.enroll(self.mounts, 'usb-test')
        with self.assertRaises(persist.PersistenceError):
            self.manager.disable({})
        self.assertTrue(self.manager.disable(self.mounts)['enabled'] is False)
        self.assertFalse((self.usb/persist.FOLDER/persist.MARKER).exists())
        self.assertTrue((self.usb/persist.FOLDER/persist.SNAPSHOT).exists())
        restored = persist.PersistenceManager(channels.ChannelStore(self.root/'next-boot'))
        self.assertFalse(restored.poll(self.mounts)['enabled'])

    def test_existing_local_list_is_never_overwritten(self):
        self.add('Persistido')
        self.manager.enroll(self.mounts, 'usb-test')
        other = channels.ChannelStore(self.root/'another-session')
        other.change('add', {'name': 'Edicoes locais', 'url': 'https://example.org/other.mp4'})
        fresh = persist.PersistenceManager(other)
        result = fresh.poll(self.mounts)
        self.assertFalse(result['enabled'])
        self.assertEqual(other.load()[0]['name'], 'Edicoes locais')

    def test_two_markers_prevent_ambiguous_auto_restore(self):
        self.add()
        self.manager.enroll(self.mounts, 'usb-test')
        second = self.root/'second_usb'
        second.mkdir()
        other_store=channels.ChannelStore(self.root/'third-session')
        other_store.change('add',{'name':'Segundo','url':'https://example.org/b.mp4'})
        persist.PersistenceManager(other_store).enroll({'usb-other':(second,'USB 2')},'usb-other')
        new_store=channels.ChannelStore(self.root/'no-local-state')
        manager=persist.PersistenceManager(new_store)
        result=manager.poll({'usb-test':(self.usb,'USB 1'),'usb-other':(second,'USB 2')})
        self.assertFalse(result['enabled'])
        self.assertIn('Mais de um',result['error'])
        self.assertFalse(new_store.path.exists())

    def test_malformed_snapshot_and_symlink_rejected(self):
        self.add()
        self.manager.enroll(self.mounts, 'usb-test')
        snapshot = self.usb/persist.FOLDER/persist.SNAPSHOT
        snapshot.write_text('{"format":"ktv-os-persistence-v1","channels":[{"name":"Bad","url":"file:///etc/passwd"}]}')
        fresh = persist.PersistenceManager(channels.ChannelStore(self.root/'empty'))
        self.assertFalse(fresh.poll(self.mounts)['enabled'])
        self.assertFalse(fresh.store.path.exists())
        other = self.root/'sensitive.txt'
        other.write_text('untouched')
        snapshot.unlink()
        snapshot.symlink_to(other)
        with self.assertRaises(channels.ChannelError):
            self.manager.sync(self.mounts) if False else channels.atomic_write(snapshot, {'channels':[]})
        self.assertEqual(other.read_text(), 'untouched')

    def test_api_enable_save_and_disable(self):
        self.add()
        with mock.patch.object(launcher, 'usb_mounts', return_value=self.mounts):
            server=launcher.KTVOSServer(port=0, state_dir=self.store.path.parent, player=FakePlayer())
            url='http://127.0.0.1:{}'.format(server.server_address[1])
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def post(path,payload):
                    req=Request(url+path,data=json.dumps(payload).encode(),
                                headers={'Content-Type':'application/json'},method='POST')
                    with urlopen(req,timeout=4) as resp:return json.loads(resp.read())
                self.assertTrue(post('/api/persistence/enable',{'device':'usb-test'})['persistence']['enabled'])
                post('/api/channels/change',{'action':'add','name':'Canal via API','url':'https://example.org/c.mp4'})
                self.assertEqual(len(json.loads((self.usb/persist.FOLDER/persist.SNAPSHOT).read_text())['channels']),2)
                with self.assertRaises(HTTPError):
                    post('/api/persistence/enable',{'device':'/dev/sda'})
                self.assertFalse(post('/api/persistence/disable',{})['persistence']['enabled'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

if __name__ == '__main__':
    unittest.main()
