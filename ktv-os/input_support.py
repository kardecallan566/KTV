"""X11 on-screen keyboard and best-effort physical keyboard detection.

No root, no device mutation, no shell. Detection is advisory: the manual
keyboard toggle always remains available for USB/Bluetooth detection delays.
"""
import os
import shutil
import subprocess
import threading


class InputController:
    def __init__(self, executable=None, popen=None, device_reader=None):
        self.executable = executable if executable is not None else shutil.which('matchbox-keyboard')
        self.popen = popen or subprocess.Popen
        self.device_reader = device_reader or self._devices
        self.process = None
        self.lock = threading.RLock()

    @staticmethod
    def _devices():
        try:
            with open('/proc/bus/input/devices', encoding='utf-8') as source:
                return source.read(32768)
        except OSError:
            return ''

    def has_physical_keyboard(self):
        raw = self.device_reader()
        if not isinstance(raw, str) or not raw:
            return None  # Unknown: never claim no keyboard on other platforms.
        for device in raw.split('\n\n'):
            if 'kbd' not in device.lower():
                continue
            name = ''
            for line in device.splitlines():
                if line.startswith('N: Name='):
                    name = line.lower()
            if 'keyboard' in name or 'teclado' in name or 'at translated set' in name:
                return True
        return False

    def status(self):
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            if not running:
                self.process = None
            return {
                'keyboard_detected': self.has_physical_keyboard(),
                'virtual_available': bool(self.executable),
                'virtual_open': running,
            }

    def toggle(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                self.process = None
                return self.status()
            self.process = None
            if not self.executable:
                raise RuntimeError('Teclado virtual do sistema nao instalado')
            try:
                self.process = self.popen(
                    [self.executable], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True)
            except OSError as exc:
                raise RuntimeError('Nao foi possivel abrir teclado virtual') from exc
            return self.status()

    def close(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self.process = None
