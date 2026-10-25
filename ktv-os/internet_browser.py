"""Open a real Chromium web window from the local KTV OS kiosk.

No proxy, scraping, shell commands, browser automation or remote execution.
Only a locally initiated search; Chromium provides navigation/address bar.
"""
import os
import shutil
import subprocess
from urllib.parse import quote

MAX_SEARCH = 180


class BrowserError(ValueError):
    pass


class InternetBrowser:
    def __init__(self, executable=None, popen=None, safe=None):
        self.executable = (executable if executable is not None else
                           shutil.which('chromium') or shutil.which('chromium-browser'))
        self.popen = popen or subprocess.Popen
        self.safe = (os.environ.get('KTV_OS_BROWSER_SAFE') == '1') if safe is None else bool(safe)

    def status(self):
        return {'available': bool(self.executable)}

    def open_search(self, query):
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_SEARCH
                or any(ord(char) < 32 or ord(char) == 127 for char in query)):
            raise BrowserError('Digite uma busca com ate 180 caracteres')
        if not self.executable:
            raise RuntimeError('Chromium indisponivel neste dispositivo')
        # Search is encoded as data. Browser navigation is handled by Chromium.
        target = 'https://duckduckgo.com/?q=' + quote(query.strip(), safe='')
        args = [self.executable, '--no-first-run', '--new-window', '--start-fullscreen']
        if self.safe:
            args.extend(('--disable-gpu', '--disable-gpu-compositing'))
        args.append(target)
        try:
            self.popen(args, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       start_new_session=True)
        except OSError as exc:
            raise RuntimeError('Falha ao iniciar o navegador') from exc
        return {'opened': True, 'instructions': 'Alt+F4 fecha a janela; use Alt+Tab para voltar ao KTV OS.'}
