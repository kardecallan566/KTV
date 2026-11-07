"""Unit tests for the isolated KTV Buffer Engine policy."""
import time
import unittest

from ktv_buffer_engine import KTVBufferEngine, BufferEngineError


class BufferEngineTests(unittest.TestCase):
    def test_start_and_buffering_state(self):
        engine = KTVBufferEngine(lambda: True)
        self.assertEqual(engine.start()['state'], 'healthy')
        self.assertEqual(engine.update_buffering(35)['state'], 'buffering')
        self.assertEqual(engine.update_buffering(100)['state'], 'healthy')
        engine.stop()
        self.assertEqual(engine.status()['state'], 'idle')

    def test_recovery_is_bounded(self):
        calls = []
        engine = KTVBufferEngine(lambda: calls.append(True) or True,
                                 max_retries=1, base_delay=0.1, max_delay=0.1)
        engine.start()
        self.assertTrue(engine.request_recovery('test'))
        self.assertFalse(engine.request_recovery('second'))
        deadline = time.monotonic() + 2
        while not calls and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(calls), 1)
        self.assertEqual(engine.status()['state'], 'healthy')
        engine.stop()

    def test_inactive_recovery_is_ignored(self):
        engine = KTVBufferEngine(lambda: True)
        self.assertFalse(engine.request_recovery())
        self.assertFalse(engine.status()['active'])

    def test_invalid_buffer_percentage(self):
        engine = KTVBufferEngine(lambda: True)
        with self.assertRaises(BufferEngineError):
            engine.update_buffering(101)


if __name__ == '__main__':
    unittest.main()
