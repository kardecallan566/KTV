import argparse
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platforms.linux.arm64 import runtime


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeServer:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.server_address = (kwargs["host"], kwargs["port"])
        self.closed = False
        self.shutdown_called = False

    def serve_forever(self):
        return None

    def shutdown(self):
        self.shutdown_called = True

    def server_close(self):
        self.closed = True


class FakeBrowserProcess:
    def __init__(self, code=0):
        self.code = code
        self.terminated = False

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


class Arm64RuntimeTests(unittest.TestCase):
    def test_runtime_resolves_ktv_os_project_root(self):
        self.assertEqual(runtime.PROJECT_ROOT.name, "ktv-os")
        self.assertTrue((runtime.PROJECT_ROOT / "launcher.py").is_file())

    def test_architecture_and_browser_detection(self):
        self.assertTrue(runtime.is_arm64("aarch64"))
        self.assertTrue(runtime.is_arm64("arm64"))
        self.assertFalse(runtime.is_arm64("x86_64"))
        self.assertEqual(
            runtime.find_chromium(lambda name: "/usr/bin/chromium" if name == "chromium" else None),
            "/usr/bin/chromium",
        )

    def test_browser_keeps_gpu_enabled_unless_safe_mode_is_requested(self):
        normal = runtime.build_browser_command("/usr/bin/chromium", "http://127.0.0.1:8787/")
        self.assertIn("--kiosk", normal)
        self.assertFalse(any("disable-gpu" in arg for arg in normal))

        safe = runtime.build_browser_command(
            "/usr/bin/chromium",
            "http://127.0.0.1:8787/",
            safe_browser=True,
        )
        self.assertIn("--disable-gpu", safe)
        self.assertIn("--disable-gpu-compositing", safe)

    def test_wait_for_server_uses_local_healthcheck(self):
        self.assertTrue(
            runtime.wait_for_server(
                "http://127.0.0.1:8787/api/status",
                attempts=1,
                opener=lambda *_args, **_kwargs: FakeResponse(),
                sleeper=lambda _delay: None,
            )
        )
        self.assertFalse(
            runtime.wait_for_server(
                "http://127.0.0.1:8787/api/status",
                attempts=2,
                opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
                sleeper=lambda _delay: None,
            )
        )

    def test_run_starts_local_server_and_kiosk_browser(self):
        created = {}
        commands = []
        server = FakeServer(host="127.0.0.1", port=8787)

        def server_factory(**kwargs):
            created.update(kwargs)
            return server

        process = FakeBrowserProcess()

        def popen(command, **kwargs):
            commands.append((command, kwargs))
            return process

        args = argparse.Namespace(
            port=8787,
            media_dir=None,
            state_dir=None,
            safe_browser=False,
        )
        result = runtime.run(
            args,
            machine="aarch64",
            which=lambda name: "/usr/bin/chromium" if name == "chromium" else None,
            popen=popen,
            server_factory=server_factory,
            opener=lambda *_args, **_kwargs: FakeResponse(),
            sleeper=lambda _delay: None,
            printer=lambda _message: None,
        )
        self.assertEqual(result, 0)
        self.assertEqual(created["host"], "127.0.0.1")
        self.assertIn("--kiosk", commands[0][0])
        self.assertEqual(commands[0][1]["stdin"], runtime.subprocess.DEVNULL)
        self.assertTrue(server.closed)

    def test_non_arm_host_does_not_start_server(self):
        args = argparse.Namespace(
            port=8787,
            media_dir=None,
            state_dir=None,
            safe_browser=False,
        )
        result = runtime.run(
            args,
            machine="x86_64",
            printer=lambda _message: None,
        )
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
