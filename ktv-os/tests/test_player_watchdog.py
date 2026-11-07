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
        clock.value += 61
        status = monitor.tick()
        self.assertEqual(status["state"], "stalled")
        self.assertGreaterEqual(status["stall_seconds"], 60)
        monitor.close()

    def test_recovery_is_bounded_and_replays_registered_session(self):
        clock, player = Clock(), FakePlayer()
        calls = []
        monitor = PlayerWatchdog(player, clock=clock, threaded=False,
                                 recover=lambda session: calls.append(session) or True)
        monitor.set_session("https://example.com/live.m3u8", "Canal", "balanced",
                            "default", recoverable=True)
        monitor.reset()
        clock.value += 36
        monitor.tick()
        clock.value += 61
        self.assertEqual(monitor.tick()["state"], "stalled")
        monitor._recover_session()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "Canal")
        self.assertEqual(monitor.status()["state"], "recovering")
        self.assertEqual(monitor.status()["recovery_attempts"], 1)
        monitor.close()

    def test_unregistered_source_is_not_recoverable(self):
        clock, player = Clock(), FakePlayer()
        calls = []
        monitor = PlayerWatchdog(player, clock=clock, threaded=False,
                                 recover=lambda session: calls.append(session) or True)
        monitor.set_session("https://example.com/live.m3u8", "Canal", "balanced",
                            "default", recoverable=False)
        self.assertFalse(monitor.status()["recovery_available"])
        monitor._recover_session()
        self.assertEqual(calls, [])
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
