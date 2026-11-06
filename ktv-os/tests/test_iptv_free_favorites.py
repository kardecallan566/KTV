import sys
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from iptv_free_favorites import IPTVFreeFavorites, IPTVFreeFavoritesError


class IPTVFreeFavoritesTests(unittest.TestCase):
    def test_toggle_persists_and_removes(self):
        with tempfile.TemporaryDirectory() as d:
            store=IPTVFreeFavorites(d)
            self.assertEqual(store.load(),[])
            self.assertEqual(store.toggle("espn"),["espn"])
            self.assertEqual(store.load(),["espn"])
            self.assertEqual(store.toggle("espn"),[])
            self.assertEqual(store.load(),[])

    def test_rejects_invalid_id(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(IPTVFreeFavoritesError):
                IPTVFreeFavorites(d).toggle("../espn")


if __name__=="__main__":
    unittest.main()
