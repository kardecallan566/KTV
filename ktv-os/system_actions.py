"""Explicit local power controls; never power off a developer's host by default.

Available only inside the booted Linux Live kiosk session (KTV_OS_LIVE=1).
No shell or sudo; logind/polkit decide whether the unprivileged user may shut
down. Actual shutdown is deferred so the browser can receive the HTTP response.
"""
import os
import shutil
import subprocess
import threading
import time

class SystemActionError(ValueError):
    pass

class SystemActions:
    def __init__(self, enabled=None, runner=None, sleep=None, which=None):
        self.enabled = (os.environ.get('KTV_OS_LIVE') == '1') if enabled is None else enabled
        self.runner = runner or subprocess.run
        self.sleep = sleep or time.sleep
        self.which = which or shutil.which
        self.lock = threading.RLock()
        self.pending = False
        self.last_error = ''

    def status(self):
        return {'poweroff_available': bool(self.enabled and self.which('systemctl')),
                'poweroff_pending': self.pending, 'error': self.last_error}

    def poweroff(self):
        with self.lock:
            if not self.enabled:
                raise SystemActionError('Desligamento disponível somente na sessão KTV OS Linux Live')
            if not self.which('systemctl'):
                raise SystemActionError('systemctl não encontrado')
            if self.pending:
                raise SystemActionError('Desligamento já solicitado')
            self.pending = True
            self.last_error = ''
            threading.Thread(target=self._execute_poweroff, daemon=True).start()
            return {'message': 'Solicitação de desligamento enviada ao Linux'}

    def _execute_poweroff(self):
        self.sleep(0.7)
        try:
            result=self.runner(['systemctl','poweroff'],capture_output=True,text=True,
                               timeout=12,check=False)
            if result.returncode != 0:
                self.last_error = 'O Linux não autorizou o desligamento; confira a sessão logind/polkit.'
        except (OSError,subprocess.TimeoutExpired):
            self.last_error = 'Não foi possível solicitar desligamento ao Linux.'
        finally:
            self.pending = False
