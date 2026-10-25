"""Pluto favorites: secure ID-only storage, API, and USB persistence."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pluto_favorites import PlutoFavorites, PlutoFavoritesError
from persistence import PersistenceManager, FOLDER, SNAPSHOT
from channel_store import ChannelStore
from launcher import KTVOSServer

IDENT='5f120e94a5714d00074576a1'
OTHER='5f120f41b7d403000783a6d6'

class FakePlayer:
    def status(self):return {'available':False,'playing':False,'name':None}
    def stop(self):return False
    def close(self):return None

class FavoriteTests(unittest.TestCase):
    def test_toggle_only_ids(self):
        with tempfile.TemporaryDirectory() as root:
            store=PlutoFavorites(root)
            self.assertEqual(store.load(),[])
            self.assertEqual(store.toggle(IDENT),[IDENT])
            self.assertEqual(store.toggle(OTHER),[IDENT,OTHER])
            self.assertEqual(store.toggle(IDENT),[OTHER])
            self.assertEqual(PlutoFavorites(root).load(),[OTHER])
            saved=(Path(root)/'pluto_favorites.json').read_text()
            self.assertNotIn('jwt',saved)
            self.assertNotIn('http',saved)

    def test_invalid_identifiers_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            store=PlutoFavorites(root)
            for value in ('../secret','https://example.org',None,True,IDENT.upper(),'x'*24):
                with self.assertRaises(PlutoFavoritesError):store.toggle(value)
            for ids in ([IDENT,IDENT],[None],['bad'],['0'*24]*201):
                with self.assertRaises(PlutoFavoritesError):store.save(ids)
            secret=Path(root)/'private.txt'
            secret.write_text('intocado')
            store.path.symlink_to(secret)
            with self.assertRaises(PlutoFavoritesError):store.save([IDENT])
            self.assertEqual(secret.read_text(),'intocado')

    def test_usb_restore_with_legacy_snapshots(self):
        with tempfile.TemporaryDirectory() as root:
            home=Path(root)
            state=home/'state'
            usb=home/'usb'
            usb.mkdir()
            mounts={'usb-1':(usb,'Pendrive')}
            favorites=PlutoFavorites(state)
            favorites.toggle(IDENT)
            manager=PersistenceManager(ChannelStore(state),favorites)
            self.assertTrue(manager.enroll(mounts,'usb-1')['enabled'])
            snapshot=usb/FOLDER/SNAPSHOT
            self.assertEqual(json.loads(snapshot.read_text())['pluto_favorites'],[IDENT])
            favorites.toggle(OTHER)
            manager.sync(mounts)
            next_state=home/'new-state'
            recovered=PersistenceManager(ChannelStore(next_state),PlutoFavorites(next_state))
            self.assertTrue(recovered.poll(mounts)['enabled'])
            self.assertEqual(PlutoFavorites(next_state).load(),[IDENT,OTHER])
            legacy=json.loads(snapshot.read_text())
            legacy.pop('pluto_favorites')
            snapshot.write_text(json.dumps(legacy))
            old_state=home/'old-state'
            old=PersistenceManager(ChannelStore(old_state),PlutoFavorites(old_state))
            self.assertTrue(old.poll(mounts)['enabled'])
            self.assertEqual(PlutoFavorites(old_state).load(),[])

    def test_local_api_toggle_and_same_origin(self):
        with tempfile.TemporaryDirectory() as root:
            server=KTVOSServer(port=0,state_dir=Path(root),player=FakePlayer())
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            url='http://127.0.0.1:'+str(server.server_address[1])
            def post(payload,headers=None):
                req=Request(url+'/api/pluto/favorites/toggle',
                            method='POST',data=json.dumps(payload).encode('utf-8'),
                            headers={'Content-Type':'application/json',**(headers or {})})
                return urlopen(req,timeout=4)
            try:
                with urlopen(url+'/api/pluto/favorites',timeout=4) as response:
                    self.assertEqual(json.load(response),{'ids':[]})
                with post({'id':IDENT}) as response:
                    data=json.load(response)
                    self.assertEqual(data['ids'],[IDENT])
                with urlopen(url+'/api/pluto/favorites',timeout=4) as response:
                    self.assertEqual(json.load(response),{'ids':[IDENT]})
                for payload in ({'id':'bad'},{'id':'http://127.0.0.1/a'},{}):
                    with self.assertRaises(HTTPError) as err:
                        post(payload)
                    self.assertEqual(err.exception.code,400)
                with self.assertRaises(HTTPError) as err:
                    post({'id':OTHER},{'Origin':'https://attacker.invalid'})
                self.assertEqual(err.exception.code,403)
                self.assertEqual(PlutoFavorites(root).load(),[IDENT])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

if __name__=='__main__':unittest.main()
