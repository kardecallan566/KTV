import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from player import NativePlayer


class FakeProcess:
    def poll(self):
        return None

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0


class NativePlayerStreamTests(unittest.TestCase):
    def _launch_args(self, url, quality="economy"):
        captured = []
        player = NativePlayer(executable="/usr/bin/mpv", popen=lambda args, **kwargs: (captured.extend(args) or FakeProcess()))
        player._read_video_state = lambda: None
        try:
            player.play(url, "Canal teste", quality=quality)
            return captured
        finally:
            player.stop()

    def test_direct_ts_uses_reconnect_and_quality_cache_without_hls_options(self):
        args = self._launch_args("https://cdn.example.org/live/channel.ts", "best")
        self.assertIn("--stream-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_delay_max=10", args)
        self.assertIn("--demuxer-max-bytes=64MiB", args)
        self.assertIn("--demuxer-max-back-bytes=16MiB", args)
        self.assertFalse(any(arg.startswith("--hls-bitrate=") for arg in args))
        self.assertFalse(any("reconnect_at_eof" in arg for arg in args))

    def test_hls_keeps_hls_bitrate_and_eof_reconnect(self):
        args = self._launch_args("https://cdn.example.org/live/channel.m3u8", "balanced")
        self.assertIn("--hls-bitrate=4000000", args)
        self.assertIn("--stream-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_delay_max=10,reconnect_at_eof=1", args)
        self.assertIn("--demuxer-max-bytes=32MiB", args)


if __name__ == "__main__":
    unittest.main()
