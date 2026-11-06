import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from iptv_free_catalog import (
    IPTVFreeCatalogError, load_catalog, iptv_free_channel, validated_catalog,
    USER_AGENT, REFERRER,
)


class IPTVFreeCatalogTests(unittest.TestCase):
    def test_snapshot_contains_all_155_entries_and_categories(self):
        channels = validated_catalog()
        self.assertEqual(len(channels), 155)
        self.assertEqual(len({item["id"] for item in channels}), 155)
        counts = {}
        for item in channels:
            counts[item["category"]] = counts.get(item["category"], 0) + 1
        self.assertEqual(counts["Esportes"], 70)
        self.assertEqual(counts["Filmes e Séries"], 30)
        self.assertEqual(counts["Canais Abertos"], 16)
        self.assertEqual(counts["Variedades"], 17)
        self.assertEqual(counts["Notícias"], 5)
        self.assertEqual(counts["Infantil"], 10)
        self.assertEqual(counts["Religiosos"], 7)

    def test_source_headers_are_fixed_and_catalog_is_separate(self):
        item = iptv_free_channel("espn")
        self.assertIsNotNone(item)
        self.assertEqual(item["user_agent"], USER_AGENT)
        self.assertEqual(item["referrer"], REFERRER)
        self.assertEqual(item["source"], "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u")

    def test_invalid_catalog_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_text(json.dumps({"schema": "wrong", "channels": []}), encoding="utf-8")
            with self.assertRaises(IPTVFreeCatalogError):
                load_catalog(path)

    def test_untrusted_host_is_filtered(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_text(json.dumps({
                "schema": "ktv-iptv-source-v1",
                "channels": [{
                    "id": "bad", "name": "Bad", "category": "Test",
                    "url": "https://evil.example/live.m3u8",
                    "user_agent": USER_AGENT, "referrer": REFERRER,
                }],
            }), encoding="utf-8")
            self.assertEqual(load_catalog(path), [])


if __name__ == "__main__":
    unittest.main()
