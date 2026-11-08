"""Lightweight Raspberry Pi/Linux resource telemetry for KTV OS.

Reads procfs/sysfs only; vcgencmd is optional and cached to avoid polling overhead.
"""
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time


class PerformanceMonitor:
    def __init__(self, clock=None, runner=None):
        self.clock = clock or time.monotonic
        self.runner = runner or subprocess.run
        self.lock = threading.Lock()
        self._previous_cpu = None
        self._last_throttle_check = 0.0
        self._throttle = None

    @staticmethod
    def _read_cpu():
        try:
            fields = Path('/proc/stat').read_text().splitlines()[0].split()[1:]
            values = [int(value) for value in fields[:8]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            return sum(values), idle
        except (OSError, ValueError, IndexError):
            return None

    def _cpu_percent(self):
        current = self._read_cpu()
        if current is None:
            return None
        previous = self._previous_cpu
        self._previous_cpu = current
        if previous is None:
            return None
        total_delta = current[0] - previous[0]
        idle_delta = current[1] - previous[1]
        if total_delta <= 0 or idle_delta < 0:
            return None
        return round(max(0.0, min(100.0, 100 * (total_delta - idle_delta) / total_delta)), 1)

    @staticmethod
    def _temperature():
        for path in ('/sys/class/thermal/thermal_zone0/temp',
                     '/sys/devices/virtual/thermal/thermal_zone0/temp'):
            try:
                value = int(Path(path).read_text().strip())
                if 1000 <= value <= 150000:
                    return round(value / 1000, 1)
            except (OSError, ValueError):
                continue
        return None

    @staticmethod
    def _memory():
        values = {}
        try:
            for line in Path('/proc/meminfo').read_text().splitlines():
                key, raw = line.split(':', 1)
                values[key] = int(raw.strip().split()[0]) * 1024
            total = values.get('MemTotal')
            available = values.get('MemAvailable')
            if total and available is not None:
                used = max(0, total - available)
                return {'total_mb': round(total / 1048576),
                        'used_mb': round(used / 1048576),
                        'available_mb': round(available / 1048576),
                        'used_percent': round(100 * used / total, 1)}
        except (OSError, ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _frequency_mhz():
        for path in ('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq',
                     '/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq'):
            try:
                value = int(Path(path).read_text().strip())
                if 10000 <= value <= 5000000:
                    return round(value / 1000)
            except (OSError, ValueError):
                continue
        return None

    def _throttling(self):
        now = self.clock()
        if self._throttle is not None and now - self._last_throttle_check < 15:
            return self._throttle
        self._last_throttle_check = now
        executable = shutil.which('vcgencmd')
        if not executable:
            self._throttle = {'available': False, 'raw': None, 'flags': [],
                              'message': 'vcgencmd indisponível neste sistema'}
            return self._throttle
        try:
            result = self.runner([executable, 'get_throttled'], capture_output=True,
                                text=True, timeout=0.6, check=False)
            output = (result.stdout or '').strip()
            raw = output.split('=', 1)[1] if '=' in output else ''
            value = int(raw, 0)
            names = ('subtensão atual', 'frequência limitada atualmente',
                     'throttling atual', 'limite térmico suave atual',
                     'subtensão registrada', 'frequência limitada registrada',
                     'throttling registrado', 'limite térmico suave registrado')
            flags = [name for bit, name in enumerate(names) if value & (1 << bit)]
            self._throttle = {'available': True, 'raw': raw, 'flags': flags,
                              'message': 'Sem flags de throttling' if not flags else ', '.join(flags)}
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            self._throttle = {'available': False, 'raw': None, 'flags': [],
                              'message': 'Não foi possível consultar vcgencmd'}
        return self._throttle

    def status(self):
        with self.lock:
            temperature = self._temperature()
            return {
                'cpu_percent': self._cpu_percent(),
                'temperature_c': temperature,
                'temperature_state': ('critical' if temperature is not None and temperature >= 80
                                    else 'hot' if temperature is not None and temperature >= 75
                                    else 'normal' if temperature is not None else 'unknown'),
                'cpu_frequency_mhz': self._frequency_mhz(),
                'memory': self._memory(),
                'throttling': self._throttling(),
                'sampled_at': round(self.clock(), 2),
            }
