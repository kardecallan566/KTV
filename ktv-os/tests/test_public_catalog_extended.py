"""Curated public channel additions must never enable arbitrary IPTV links."""
import importlib.util
from pathlib import Path
import unittest
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ktv_public_08_extended',ROOT/'public_channels.py')
catalog=importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

class PublicCatalogTests(unittest.TestCase):
    def test_expanded_list_with_official_provenance(self):
        entries=catalog.validated_catalog()
        ids={entry['id'] for entry in entries}
        self.assertEqual(len(entries),len(ids))
        self.assertTrue({'tv-brasil','canal-gov','tv-camara',
                         'canal-educacao','tv-cultura','sesc-tv'}.issubset(ids))
        for entry in entries:
            url=urlsplit(entry['url'])
            self.assertEqual(url.scheme,'https')
            self.assertIn(url.hostname,catalog.ALLOWED_HOSTS)
            self.assertNotIn(url.hostname,{'localhost','127.0.0.1'})
            self.assertIsNone(url.username)
            self.assertIsNone(url.password)
            self.assertTrue(url.path.endswith('.m3u8'))
            self.assertTrue(entry['source'].startswith('https://'))
            self.assertEqual(entry['status'],'experimental')
            self.assertIsInstance(entry['genres'],list)
            self.assertTrue(entry['genres'])
    def test_anime_no_fake_stream(self):
        entries=catalog.validated_catalog()
        self.assertFalse(any('Animes' in x['genres'] for x in entries))
        self.assertIsNone(catalog.public_channel('stream-de-anime-nao-verificado'))
    def test_cinema_and_animation_programming_metadata(self):
        entries={entry['id']:entry for entry in catalog.validated_catalog()}
        self.assertIn('Filmes',entries['tv-brasil']['genres'])
        self.assertIn('Desenhos',entries['tv-cultura']['genres'])
        self.assertIn('Documentários',entries['sesc-tv']['genres'])
        self.assertIn('Educação',entries['canal-educacao']['genres'])
    def test_cannot_play_unknown_stream_by_identifier(self):
        self.assertIsNone(catalog.public_channel('https://evil.test/hls/stream.m3u8'))
        self.assertIsNone(catalog.public_channel(None))

if __name__=='__main__':
    unittest.main()
