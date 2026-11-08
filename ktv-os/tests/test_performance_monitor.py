import importlib.util
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ktv_performance_monitor', ROOT/'performance_monitor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PerformanceMonitorTests(unittest.TestCase):
    def test_status_is_safe_when_raspberry_sensors_are_missing(self):
        monitor = m.PerformanceMonitor(clock=lambda: 100)
        with mock.patch.object(m.shutil, 'which', return_value=None), \
             mock.patch.object(Path, 'read_text', side_effect=OSError):
            result = monitor.status()
        self.assertIsNone(result['temperature_c'])
        self.assertEqual(result['temperature_state'], 'unknown')
        self.assertIsNone(result['memory'])
        self.assertFalse(result['throttling']['available'])

    def test_cpu_delta_and_thermal_threshold(self):
        monitor = m.PerformanceMonitor(clock=lambda: 100)
        cpu_lines = iter([
            'cpu 100 0 50 850 0 0 0 0',
            'cpu 200 0 100 900 0 0 0 0',
        ])
        def read(path):
            path = str(path)
            if path == '/proc/stat':
                return next(cpu_lines)
            if path == '/sys/class/thermal/thermal_zone0/temp':
                return '82000'
            raise OSError
        with mock.patch.object(Path, 'read_text', side_effect=read), \
             mock.patch.object(m.shutil, 'which', return_value=None):
            self.assertIsNone(monitor._cpu_percent())
            self.assertEqual(monitor._cpu_percent(), 66.7)
            result = monitor.status()
        self.assertEqual(result['temperature_c'], 82.0)
        self.assertEqual(result['temperature_state'], 'critical')


if __name__ == '__main__':
    unittest.main()
