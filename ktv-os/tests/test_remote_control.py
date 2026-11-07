import threading
import time
import unittest

from remote_control import RemoteControl


class RemoteLongPollTests(unittest.TestCase):
    def setUp(self):
        self.remote = RemoteControl()
        self.token = self.remote.pair(self.remote.pin, '127.0.0.1')

    def test_waiting_receiver_is_woken_immediately_by_navigation(self):
        result = {}
        started = time.monotonic()

        def receive():
            result.update(self.remote.events_since(0, wait=5))

        worker = threading.Thread(target=receive)
        worker.start()
        time.sleep(0.05)
        self.remote.command(self.token, 'ArrowRight')
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive(), 'long poll should wake without waiting for timeout')
        self.assertEqual([event['action'] for event in result['events']], ['ArrowRight'])
        self.assertLess(time.monotonic() - started, 1)

    def test_long_poll_returns_existing_events_without_waiting(self):
        self.remote.command(self.token, 'accept')
        started = time.monotonic()
        result = self.remote.events_since(0, wait=5)
        self.assertEqual(result['events'][0]['action'], 'accept')
        self.assertLess(time.monotonic() - started, 0.2)

    def test_long_poll_timeout_is_bounded(self):
        started = time.monotonic()
        result = self.remote.events_since(0, wait=0.05)
        self.assertEqual(result['events'], [])
        self.assertLess(time.monotonic() - started, 0.5)


    def test_multimedia_actions_are_allowlisted_and_session_protected(self):
        for action in ('volume_up', 'volume_down', 'mute'):
            result = self.remote.command(self.token, action)
            self.assertTrue(result['ok'])\n            self.assertEqual(self.remote.events_since(0)['events'][-1]['action'], action)
        with self.assertRaises(ValueError):
            self.remote.command(self.token, 'arbitrary_key')
        with self.assertRaises(ValueError):
            self.remote.command('invalid-token', 'mute')

if __name__ == '__main__':
    unittest.main()
