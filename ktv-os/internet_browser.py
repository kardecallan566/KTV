"""Open a real Chromium web window from the local KTV OS kiosk.

No proxy, scraping, shell commands, browser automation or remote execution.
Only a locally initiated search; Chromium provides navigation/address bar.
"""
import os
import shutil
import subprocess
from urllib.parse import quote, urlsplit

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

    def open_home(self, address):
        """Open the local green portal in a full Chromium window."""
        try:
            parts = urlsplit(address)
            if (parts.scheme != 'http' or parts.hostname != '127.0.0.1'
                    or parts.username is not None or parts.password is not None
                    or parts.path != '/browser.html' or parts.query or parts.fragment
                    or parts.port is None):
                raise BrowserError('Endereco do navegador invalido')
        except ValueError as exc:
            raise BrowserError('Endereco do navegador invalido') from exc
        if not self.executable:
            raise RuntimeError('Chromium indisponivel neste dispositivo')
        args = [self.executable, '--no-first-run', '--new-window',
                '--start-fullscreen', address]
        if self.safe:
            args[4:4] = ['--disable-gpu', '--disable-gpu-compositing']
        try:
            self.popen(args, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       start_new_session=True)
        except OSError as exc:
            raise RuntimeError('Falha ao iniciar o navegador verde') from exc
        return {'opened': True}

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
