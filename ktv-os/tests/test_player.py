import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktv_native_player', ROOT/'player.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MockProcess:
    def __init__(self):
        self.running = True
        self.terminated = False
    def poll(self):
        return None if self.running else 0
    def terminate(self):
        self.terminated = True
        self.running = False
    def wait(self, timeout=3):
        self.running = False
        return 0
    def kill(self):
        self.running = False

class NativePlayerTests(unittest.TestCase):
    def test_launch_without_shell_and_replace(self):
        calls = []
        def start(argv, **kw):
            calls.append((argv, kw))
            return MockProcess()
        player = m.NativePlayer(executable='/usr/bin/mpv', popen=start)
        result = player.play('https://example.com/test.m3u8', 'Canal Teste')
        self.assertTrue(result['playing'])
        self.assertIn('--no-config', calls[0][0])
        self.assertIn('--no-ytdl', calls[0][0])
        self.assertEqual(calls[0][0][-2], '--')
        self.assertEqual(calls[0][0][-1], 'https://example.com/test.m3u8')
        self.assertNotIn('shell', calls[0][1])
        self.assertTrue(player.stop())
        self.assertFalse(player.status()['playing'])

    def test_missing_binary_and_bad_source(self):
        player = m.NativePlayer(executable='', popen=lambda *a, **kw: None)
        with self.assertRaisesRegex(RuntimeError, 'mpv nao instalado'):
            player.play('http://example.org/live.m3u8', 'Live')
        player.executable = 'mpv'
        with self.assertRaises(ValueError):
            player.play('--input-ipc-server=/tmp/evil', 'Bad')

    def test_safe_local_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            base = Path(dirname)
            inside = base/'clip.mp4'
            inside.write_bytes(b'\x00')
            self.assertEqual(m.safe_media_path(base,'clip.mp4',{'.mp4'}),inside)
            with self.assertRaises(ValueError):
                m.safe_media_path(base,'../secret.mp4',{'.mp4'})
            with self.assertRaises(ValueError):
                m.safe_media_path(base,'hidden.sh',{'.mp4'})
            (base/'link.mp4').symlink_to(inside)
            with self.assertRaises(ValueError):
                m.safe_media_path(base,'link.mp4',{'.mp4'})

if __name__ == '__main__':
    unittest.main()
