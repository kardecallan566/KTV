import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from player_watchdog import PlayerWatchdog


class Clock:
    value = 100.0
    def __call__(self):
        return self.value


class FakePlayer:
    def __init__(self):
        self.info = {"playing": True, "video": {"paused": False, "time_pos": 1.0}}
    def status(self):
        return self.info


class WatchdogTests(unittest.TestCase):
    def test_progress_marks_healthy_and_pause_is_not_stall(self):
        clock, player = Clock(), FakePlayer()
        monitor = PlayerWatchdog(player, clock=clock, threaded=False)
        monitor.reset()
        clock.value += 40
        player.info["video"]["time_pos"] = 2.0
        self.assertEqual(monitor.tick()["state"], "healthy")
        player.info["video"]["paused"] = True
        clock.value += 60
        self.assertEqual(monitor.tick()["state"], "paused")
        monitor.close()

    def test_stalled_timeline_raises_diagnostic_after_grace(self):
        clock, player = Clock(), FakePlayer()
        monitor = PlayerWatchdog(player, clock=clock, threaded=False)
        monitor.reset()
        clock.value += 36
        monitor.tick()  # ends startup grace
        clock.value += 46
        status = monitor.tick()
        self.assertEqual(status["state"], "stalled")
        self.assertGreaterEqual(status["stall_seconds"], 45)
        monitor.close()

    def test_idle_player_clears_monitor(self):
        clock, player = Clock(), FakePlayer()
        monitor = PlayerWatchdog(player, clock=clock, threaded=False)
        monitor.reset()
        player.info["playing"] = False
        self.assertEqual(monitor.tick()["state"], "idle")
        monitor.close()


if __name__ == "__main__":
    unittest.main()
