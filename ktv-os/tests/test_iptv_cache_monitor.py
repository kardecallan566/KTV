import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('iptv_cache_monitor',ROOT/'iptv_cache_monitor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakePlayer:
    def status(self):
        return {'playing':True,'video':{'buffer_seconds':2.0}}

class IPTVCacheMonitorTests(unittest.TestCase):
    def test_activation_and_deactivation_are_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor=m.IPTVCacheMonitor(FakePlayer(),Path(directory)/'catalog.json')
            try:
                monitor.activate('channel-1','Canal de teste')
                state=monitor.status()
                self.assertTrue(state['active'])
                self.assertEqual(state['channel']['id'],'channel-1')
                self.assertTrue(state['preserves_playback'])
                monitor.deactivate()
                self.assertFalse(monitor.status()['active'])
                self.assertEqual(monitor.status()['state'],'idle')
            finally:
                monitor.close()

    def test_stagnant_low_cache_refreshes_catalog_without_player_play(self):
        with tempfile.TemporaryDirectory() as directory:
            player=FakePlayer()
            monitor=m.IPTVCacheMonitor(player,Path(directory)/'catalog.json')
            monitor.SAMPLE_SECONDS=0.02
            monitor.STALL_SECONDS=0
            monitor.LOW_BUFFER_SECONDS=8
            monitor.REFRESH_COOLDOWN=1
            try:
                with mock.patch.object(m,'refresh_catalog') as refresh:
                    monitor.activate('channel-1','Canal')
                    deadline=time.monotonic()+0.5
                    while not refresh.called and time.monotonic()<deadline:
                        time.sleep(0.01)
                    self.assertTrue(refresh.called)
                    self.assertEqual(monitor.status()['state'],'refreshed')
                    self.assertEqual(monitor.status()['refresh_count'],1)
                    # Monitor calls status only; it never invokes player.play/replaces session.
            finally:
                monitor.close()

if __name__=='__main__':
    unittest.main()
