import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from iptv_free_catalog import (
    IPTVFreeCatalogError, load_catalog, parse_m3u_metadata, parse_m3u_playlist,
    iptv_free_channel, validated_catalog, refresh_catalog, SOURCE_URL,
)


class IPTVFreeCatalogTests(unittest.TestCase):
    def test_bundled_snapshot_remains_a_valid_offline_fallback(self):
        channels = validated_catalog()
        self.assertGreater(len(channels), 1800)
        self.assertEqual(len({item["id"] for item in channels}), len(channels))
        self.assertTrue(all("streams" in item for item in channels))

    def test_parser_pairs_hls_and_ts_variants_without_exposing_urls_in_metadata(self):
        sample = """#EXTM3U
#EXTINF:-1 tvg-id="news.br" tvg-logo="https://logo.example/a.png" group-title="Notícias [M3U8]",Canal Notícias [M3U8]
https://stream.example.org/live.m3u8
#EXTINF:-1 tvg-id="news.br" group-title="Notícias [TS]",Canal Notícias [TS]
https://stream.example.org/live.ts
"""
        channels = parse_m3u_playlist(sample)
        self.assertEqual(len(channels), 1)
        item = channels[0]
        self.assertEqual(item["name"], "Canal Notícias")
        self.assertEqual(item["categories"], ["Notícias"])
        self.assertEqual([entry["format"] for entry in item["streams"]], ["hls", "ts"])
        self.assertTrue(item["playable"])
        metadata = parse_m3u_metadata(sample)[0]
        self.assertNotIn("url", metadata)
        self.assertNotIn("streams", metadata)
        self.assertNotIn("logo", json.dumps(metadata))

    def test_parser_ignores_invalid_stream_and_untrusted_header_metadata(self):
        sample = """#EXTM3U x-tvg-url="http://guide.example.org/xmltv.php?token=private"
#EXTINF:-1 tvg-id="demo" group-title="Teste",Canal Demo
http://localhost/private.m3u8
"""
        channels = parse_m3u_playlist(sample)
        self.assertEqual(len(channels), 1)
        self.assertFalse(channels[0]["playable"])
        self.assertEqual(channels[0]["streams"], [])

    def test_refresh_persists_stream_urls_only_in_private_catalog(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return SOURCE_URL
            def read(self, limit):
                return b'#EXTM3U\n#EXTINF:-1 tvg-id="demo.br" group-title="Teste",Canal Demo\nhttps://stream.example.org/live.m3u8\n'

        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state" / "iptv_free_catalog.json"
            with mock.patch("iptv_free_catalog.urlopen", return_value=FakeResponse()):
                channels = refresh_catalog(target, SOURCE_URL)
            self.assertEqual(channels[0]["name"], "Canal Demo")
            self.assertTrue(channels[0]["playable"])
            stored = target.read_text(encoding="utf-8")
            self.assertIn("https://stream.example.org/live.m3u8", stored)
            self.assertEqual(iptv_free_channel(channels[0]["id"], target)["streams"][0]["format"], "hls")

    def test_catalog_rejects_legacy_unknown_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_text(json.dumps({"schema": "ktv-iptv-source-v1", "channels": []}), encoding="utf-8")
            with self.assertRaises(IPTVFreeCatalogError):
                load_catalog(path)

    def test_channel_lookup_keeps_streams_server_side(self):
        item = iptv_free_channel(validated_catalog()[0]["id"])
        self.assertIsNotNone(item)
        self.assertIsInstance(item["streams"], list)
        self.assertNotIn("url", item)


if __name__ == "__main__":
    unittest.main()
