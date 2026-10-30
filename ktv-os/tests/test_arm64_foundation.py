import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ktv_arm64_diagnostics",
    ROOT / "platforms" / "linux" / "arm64" / "diagnostics.py",
)
diagnostics_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics_module)

import sys
sys.path.insert(0, str(ROOT))
from core.contracts import (
    CONTRACTS_VERSION,
    Capability,
    DeviceInfo,
    MediaPlayer,
    MediaStatus,
    OperationResult,
)


class FakeMediaPlayer:
    def capabilities(self):
        return [Capability(name="pause", available=True, source="test")]

    def status(self):
        return MediaStatus(available=True, playing=False)

    def play(self, source, name, profile="balanced"):
        return OperationResult(ok=True, code="started")

    def pause(self):
        return OperationResult(ok=True, code="paused")

    def resume(self):
        return OperationResult(ok=True, code="resumed")

    def seek(self, position_seconds):
        return OperationResult(ok=True, code="seeked")

    def stop(self):
        return OperationResult(ok=True, code="stopped")


class MultiplatformContractTests(unittest.TestCase):
    def test_contract_models_have_safe_defaults(self):
        self.assertEqual(CONTRACTS_VERSION, "1.0")
        self.assertFalse(Capability(name="volume", available=False).available)
        self.assertEqual(OperationResult(ok=False, code="unsupported").data, {})
        self.assertFalse(MediaStatus(available=False).playing)
        info = DeviceInfo(platform="linux-arm64", architecture="aarch64")
        self.assertEqual(info.gpu_devices, ())

    def test_existing_style_player_can_satisfy_media_contract(self):
        self.assertIsInstance(FakeMediaPlayer(), MediaPlayer)


class Arm64DiagnosticsTests(unittest.TestCase):
    def make_file(self, root, path, content):
        target = Path(root) / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_collects_pi_host_facts_without_claiming_hw_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_file(root, "/proc/device-tree/model", "Raspberry Pi 4 Model B Rev 1.5\0")
            self.make_file(
                root,
                "/etc/os-release",
                'PRETTY_NAME="Raspberry Pi OS 64-bit"\nID=raspbian\nVERSION_ID="13"\n',
            )
            self.make_file(root, "/proc/meminfo", "MemTotal:        8192000 kB\n")
            self.make_file(root, "/sys/class/thermal/thermal_zone0/temp", "52000\n")
            self.make_file(root, "/sys/class/drm/card1-HDMI-A-1/status", "connected\n")
            (root / "dev/dri").mkdir(parents=True)
            (root / "dev/dri/card1").touch()
            (root / "dev/dri/renderD128").touch()
            (root / "dev/input").mkdir(parents=True)
            (root / "dev/input/event0").touch()

            installed = {"mpv", "chromium", "systemctl", "nmcli"}
            report = diagnostics_module.Arm64Diagnostics(
                root=root,
                machine="aarch64",
                which=lambda name: "/usr/bin/" + name if name in installed else None,
            ).collect()

            self.assertTrue(report["is_arm64"])
            self.assertEqual(report["platform"], "linux-arm64")
            self.assertIn("Raspberry Pi 4", report["board_model"])
            self.assertEqual(report["memory_total_mb"], 8000)
            self.assertEqual(report["cpu_temperature_c"], 52.0)
            self.assertEqual(report["gpu_devices"], ["card1", "renderD128"])
            self.assertEqual(report["display_connectors"][0]["status"], "connected")
            self.assertEqual(report["media_acceleration"]["status"], "not_verified")
            self.assertTrue(report["dependencies"]["mpv"])

    def test_non_arm_host_is_never_reported_as_pi_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            report = diagnostics_module.Arm64Diagnostics(
                root=temp,
                machine="x86_64",
                which=lambda _name: None,
            ).collect()
            self.assertFalse(report["is_arm64"])
            self.assertEqual(report["platform"], "unsupported")
            self.assertEqual(report["media_acceleration"]["status"], "not_verified")


if __name__ == "__main__":
    unittest.main()
