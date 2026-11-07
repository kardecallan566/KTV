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

    def mouse(self, action, dx=0, dy=0):
        """Move/click the X11 pointer using fixed xdotool operations only."""
        executable = shutil.which('xdotool')
        if not executable:
            raise RuntimeError('Mouse remoto requer xdotool (sudo apt install xdotool)')
        if action == 'move':
            if type(dx) is not int or type(dy) is not int or abs(dx) > 1000 or abs(dy) > 1000:
                raise ValueError('Movimento do mouse invalido')
            if dx == 0 and dy == 0:
                return {'moved': True}
            args = [executable, 'mousemove_relative', '--', str(dx), str(dy)]
        elif action in ('left', 'right'):
            args = [executable, 'click', '1' if action == 'left' else '3']
        elif action in ('scroll_up', 'scroll_down'):
            args = [executable, 'click', '4' if action == 'scroll_up' else '5']
        else:
            raise ValueError('Acao de mouse invalida')
        try:
            subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=0.35, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError('Nao foi possivel controlar o mouse X11') from exc
        return {'moved': True}

    def media_key(self, action):
        """Execute only fixed multimedia keys; never accept a shell/key string."""
        keys = {
            'volume_up': 'XF86AudioRaiseVolume',
            'volume_down': 'XF86AudioLowerVolume',
            'mute': 'XF86AudioMute',
        }
        key = keys.get(action)
        executable = shutil.which('xdotool')
        if not key or not executable:
            raise RuntimeError('Teclas de volume requerem xdotool')
        try:
            subprocess.run([executable, 'key', key], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=0.35, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError('Nao foi possivel executar tecla multimidia') from exc
        return {'sent': True, 'action': action}

    def close(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self.process = None
