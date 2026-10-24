"""Optional libCEC remote control adapter for KTV OS Linux Live.

Reads *only* user control button events from cec-client. It does not send
CEC power, standby, source selection or volume commands to the television.
Must be explicitly enabled in the KTV OS settings and requires CEC hardware
supported by libCEC (often an external USB-CEC adapter on x86 PCs).
"""
from collections import deque
import re
import shutil
import subprocess
import threading
import time

# cec-client -d 8 debug lines include: "key pressed: up (1)"
# and "key pressed: select (0, 0)".
PRESS = re.compile(r'key pressed:\s*([a-z][a-z0-9 _-]*)\s*\((?:0x)?[0-9a-f]+(?:,\s*\d+)?\)', re.I)
KEYS = {
    'up':'ArrowUp','down':'ArrowDown','left':'ArrowLeft','right':'ArrowRight',
    'select':'Enter','enter':'Enter','ok':'Enter',
    'exit':'Escape','back':'Escape','return':'Escape',
    'root menu':'Home','home':'Home'
}
MAX_EVENTS = 64


def decode_key(line):
    if not isinstance(line, str) or len(line) > 2048:
        return None
    if 'key released:' in line.lower():
        return None
    m = PRESS.search(line)
    return KEYS.get(m.group(1).strip().lower()) if m else None


class CECError(RuntimeError):
    pass


class CECBridge:
    def __init__(self, popen=None, which=None, clock=None):
        self.popen = popen or subprocess.Popen
        self.which = which or shutil.which
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()
        self.proc = None
        self.reader = None
        self.events = deque(maxlen=MAX_EVENTS)
        self.serial = 0
        self.last_key = ''
        self.last_at = 0.0
        self.error = ''
        self.enabled = False

    def status(self):
        with self.lock:
            running = self.proc is not None and self.proc.poll() is None
            return {
                'supported': bool(self.which('cec-client')),
                'enabled': self.enabled,
                'running': running,
                'error': self.error,
                'last_key': self.last_key
            }

    def _deliver(self, key):
        if key not in KEYS.values():
            return
        with self.lock:
            now = self.clock()
            # Avoid duplicate press logging from libCEC in the same 140 ms.
            if key == self.last_key and now - self.last_at < 0.14:
                return
            self.serial += 1
            self.events.append({'id': self.serial, 'key': key})
            self.last_key = key
            self.last_at = now

    def enable(self):
        with self.lock:
            if self.enabled and self.proc is not None and self.proc.poll() is None:
                return self.status()
            executable = self.which('cec-client')
            if not executable:
                raise CECError('cec-client indisponivel: verifique o pacote cec-utils')
            try:
                # Keep stdin open, since cec-client exits when it sees EOF.
                self.proc = self.popen(
                    [executable, '-t', 'p', '-d', '8'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1
                )
            except OSError as exc:
                self.proc = None
                raise CECError('Nao foi possivel iniciar libCEC: {}'.format(exc))
            self.enabled = True
            self.error = ''
            self.reader = threading.Thread(target=self._read, args=(self.proc,),daemon=True)
            self.reader.start()
            return self.status()

    def _read(self, process):
        try:
            for line in process.stdout:
                with self.lock:
                    if not self.enabled or self.proc is not process:
                        break
                key = decode_key(line)
                if key:
                    self._deliver(key)
        except (OSError, ValueError) as exc:
            with self.lock:
                if self.proc is process and self.enabled:
                    self.error = 'Erro ao ler controle CEC: {}'.format(exc)
        finally:
            with self.lock:
                if self.proc is process and self.enabled:
                    self.enabled = False
                    self.error = 'CEC desconectado ou nenhum adaptador compativel detectado'
                    self.proc = None
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try: process.kill()
                except OSError: pass
            try:
                if process.stdin:
                    process.stdin.close()
            except OSError:
                pass

    def events_since(self, since):
        if type(since) is not int or since < 0:
            raise CECError('Sequencia de evento invalida')
        with self.lock:
            # The client should initialize with the current serial when enabled.
            return {'events':[dict(e) for e in self.events if e['id'] > since],
                    'last': self.serial}

    def disable(self):
        with self.lock:
            self.enabled = False
            proc = self.proc
            self.proc = None
            self.error = ''
            self.events.clear()
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            except OSError:
                pass
            if proc.stdin:
                try: proc.stdin.close()
                except OSError: pass
        return self.status()

    def close(self):
        self.disable()
