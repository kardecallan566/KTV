import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from iptv_free_catalog import (
    IPTVFreeCatalogError, load_catalog, parse_m3u_metadata, iptv_free_channel,
    validated_catalog, refresh_catalog, SOURCE_URL,
)


class IPTVFreeCatalogTests(unittest.TestCase):
    def test_snapshot_contains_metadata_only_catalog(self):
        channels = validated_catalog()
        self.assertGreater(len(channels), 1800)
        self.assertEqual(len({item["id"] for item in channels}), len(channels))
        self.assertTrue(all(item["playable"] is False for item in channels))
        self.assertTrue(all("url" not in item and "logo" not in item for item in channels))
        self.assertTrue(any(len(item["categories"]) > 1 for item in channels))

    def test_parser_discards_stream_and_logo_urls(self):
        sample = """#EXTM3U
#EXTINF:-1 tvg-id="news.br" tvg-logo="https://logo.example/a.png" group-title="Notícias [M3U8]",Canal Notícias [M3U8]
https://user:secret@example.invalid/live.m3u8
#EXTINF:-1 tvg-id="news.br" group-title="Notícias [TS]",Canal Notícias [TS]
https://example.invalid/live.ts
"""
        channels = parse_m3u_metadata(sample)
        self.assertEqual(len(channels), 1)
        item = channels[0]
        self.assertEqual(item["name"], "Canal Notícias")
        self.assertEqual(item["categories"], ["Notícias"])
        self.assertFalse(item["playable"])
        self.assertNotIn("url", item)
        self.assertNotIn("logo", item)
        self.assertNotIn("secret", json.dumps(item))

    def test_refresh_saves_only_metadata_to_the_supplied_state_path(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return SOURCE_URL
            def read(self, limit):
                return b'#EXTM3U\n#EXTINF:-1 tvg-id="demo.br" group-title="Teste",Canal Demo\nhttps://user:secret@example.invalid/live.m3u8\n'

        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state" / "iptv_free_catalog.json"
            with mock.patch("iptv_free_catalog.urlopen", return_value=FakeResponse()):
                channels = refresh_catalog(target, SOURCE_URL)
            self.assertEqual(channels[0]["name"], "Canal Demo")
            stored = target.read_text(encoding="utf-8")
            self.assertNotIn("example.invalid", stored)
            self.assertNotIn("secret", stored)
            self.assertNotIn('"url"', stored)

    def test_catalog_rejects_legacy_stream_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_text(json.dumps({"schema": "ktv-iptv-source-v1", "channels": []}), encoding="utf-8")
            with self.assertRaises(IPTVFreeCatalogError):
                load_catalog(path)

    def test_channel_lookup_returns_metadata_without_playback_source(self):
        item = iptv_free_channel(validated_catalog()[0]["id"])
        self.assertIsNotNone(item)
        self.assertFalse(item["playable"])
        self.assertNotIn("url", item)


if __name__ == "__main__":
    unittest.main()
