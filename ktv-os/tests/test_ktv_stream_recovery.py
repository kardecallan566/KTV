"""Tests for the isolated KTV Stream Recovery watchdog."""
import time
import unittest

from ktv_stream_recovery import KTVStreamRecovery, StreamRecoveryError


class StreamRecoveryTests(unittest.TestCase):
    def wait_for(self, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return predicate()

    def test_stall_triggers_recovery(self):
        calls = []
        engine = KTVStreamRecovery(lambda: calls.append(1) or True,
                                   stall_timeout=3, poll_interval=0.1,
                                   max_recoveries=1, cooldown=0)
        engine.start()
        self.assertTrue(self.wait_for(lambda: len(calls) == 1, timeout=2))
        self.assertEqual(engine.status()['state'], 'watching')
        engine.stop()

    def test_progress_marker_resets_watchdog(self):
        calls = []
        engine = KTVStreamRecovery(lambda: calls.append(1) or True,
                                   stall_timeout=3, poll_interval=0.1,
                                   max_recoveries=1)
        engine.start(initial_marker=10)
        self.assertTrue(engine.report_progress(11))
        self.assertFalse(engine.report_progress(11))
        self.assertEqual(calls, [])
        engine.stop()

    def test_explicit_error_recovery_is_bounded(self):
        calls = []
        engine = KTVStreamRecovery(lambda: calls.append(1) or True,
                                   stall_timeout=30, poll_interval=0.2,
                                   max_recoveries=1, cooldown=0)
        engine.start()
        self.assertTrue(engine.report_error('decoder-error'))
        self.assertFalse(engine.report_error('another-error'))
        self.assertTrue(self.wait_for(lambda: len(calls) == 1))
        engine.stop()

    def test_pause_suppresses_watchdog_and_resume_resets_timer(self):
        calls = []
        engine = KTVStreamRecovery(lambda: calls.append(1) or True,
                                   stall_timeout=3, poll_interval=0.1,
                                   max_recoveries=1)
        engine.start()
        self.assertTrue(engine.pause())
        time.sleep(0.2)
        self.assertEqual(calls, [])
        self.assertTrue(engine.resume())
        engine.stop()

    def test_invalid_options(self):
        with self.assertRaises(StreamRecoveryError):
            KTVStreamRecovery(lambda: True, stall_timeout=1)


if __name__ == '__main__':
    unittest.main()
