from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platforms.linux.arm64.mpv_adapter import MpvMediaPlayerAdapter


class FakeNativePlayer:
    def __init__(self):
        self.available = True
        self.ipc_path = None
        self.play_calls = []
        self.stop_result = True
        self.state = {
            "available": True,
            "playing": True,
            "name": "Canal de teste",
            "exit_code": None,
            "video": {
                "time_pos": 15.5,
                "paused": False,
                "width": 1920,
                "height": 1080,
                "fps": 29.97,
                "codec": "h264",
                "hardware_decoder": None,
                "dropped_frames": 2,
            },
        }

    def play(self, source, name, quality="balanced"):
        self.play_calls.append((source, name, quality))
        return {"playing": True}

    def status(self):
        return self.state

    def stop(self):
        return self.stop_result


class FakeSocketClient:
    def __init__(self):
        self.sent = b""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        return None

    def connect(self, _path):
        return None

    def sendall(self, payload):
        self.sent = payload

    def recv(self, _size):
        return b'{"error":"success","request_id":1}\n'


class FakeSocketModule:
    AF_UNIX = 1
    SOCK_STREAM = 1

    def __init__(self):
        self.client = FakeSocketClient()

    def socket(self, _family, _kind):
        return self.client


class MpvAdapterTests(unittest.TestCase):
    def test_play_and_status_are_normalized(self):
        native = FakeNativePlayer()
        adapter = MpvMediaPlayerAdapter(native)
        result = adapter.play("https://example.org/live.m3u8", "Canal", "best")
        self.assertTrue(result.ok)
        self.assertEqual(native.play_calls[0][2], "best")

        status = adapter.status()
        self.assertTrue(status.available)
        self.assertTrue(status.playing)
        self.assertEqual(status.video_width, 1920)
        self.assertEqual(status.video_height, 1080)
        self.assertEqual(status.codec, "h264")
        self.assertEqual(status.hardware_decoder, None)
        self.assertEqual(status.dropped_frames, 2)

    def test_pause_uses_only_fixed_private_ipc_command(self):
        native = FakeNativePlayer()
        native.ipc_path = "/tmp/ktv-mpv/control.sock"
        socket_module = FakeSocketModule()
        adapter = MpvMediaPlayerAdapter(native, socket_module=socket_module)

        result = adapter.pause()
        self.assertTrue(result.ok)
        self.assertIn(b'"set_property", "pause", true', socket_module.client.sent)

    def test_invalid_seek_and_missing_session_are_rejected(self):
        adapter = MpvMediaPlayerAdapter(FakeNativePlayer())
        invalid = adapter.seek(float("nan"))
        self.assertFalse(invalid.ok)
        self.assertEqual(invalid.code, "invalid_argument")

        unavailable = adapter.pause()
        self.assertFalse(unavailable.ok)
        self.assertEqual(unavailable.code, "not_available")

    def test_stop_is_safe_when_already_stopped(self):
        native = FakeNativePlayer()
        native.stop_result = False
        result = MpvMediaPlayerAdapter(native).stop()
        self.assertTrue(result.ok)
        self.assertEqual(result.code, "already_stopped")


if __name__ == "__main__":
    unittest.main()
