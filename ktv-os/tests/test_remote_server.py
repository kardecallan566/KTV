"""Unit tests for KTV Local Remote security helpers."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock

MODULE = pathlib.Path(__file__).resolve().parents[1] / "remote_server.py"
SPEC = importlib.util.spec_from_file_location("ktv_remote_server", MODULE)
remote = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(remote)


class RemoteSecurityTests(unittest.TestCase):
    def test_only_private_or_loopback_addresses(self):
        self.assertTrue(remote.private_lan("192.168.1.20"))
        self.assertTrue(remote.private_lan("10.0.0.8"))
        self.assertTrue(remote.private_lan("127.0.0.1"))
        self.assertTrue(remote.private_lan("::1"))
        self.assertFalse(remote.private_lan("8.8.8.8"))
        self.assertFalse(remote.private_lan("invalid"))

    def test_pairing_config_is_persistent_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp)
            config = state / "remote.json"
            with mock.patch.object(remote, "STATE", state), mock.patch.object(remote, "CONFIG", config):
                first = remote.load_config()
                second = remote.load_config()
                self.assertEqual(first, second)
                self.assertEqual(len(first["pin"]), 6)
                self.assertGreaterEqual(int(first["pin"]), 100000)
                self.assertEqual(len(first["token"]), 43)
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_keymap_contains_navigation_and_alphanumeric_keys(self):
        for key in ("Enter", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "a", "z", "0", "9"):
            self.assertIn(key, remote.KEY_MAP)


if __name__ == "__main__":
    unittest.main()
