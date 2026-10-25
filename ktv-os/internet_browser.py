"""Open a real Chromium web window from the local KTV OS kiosk.

No proxy, scraping, shell commands, browser automation or remote execution.
Only a locally initiated search; Chromium provides navigation/address bar.
"""
import os
import shutil
import subprocess
from urllib.parse import quote, urlsplit

MAX_SEARCH = 180


# Official access pages. Provider controls login, ads, DRM and regional rights.
BROADCASTERS = {
    'sbt': {'name':'SBT', 'url':'https://sbt.com.br/ao-vivo'},
    'globo': {'name':'TV Globo (Globoplay)', 'url':'https://globoplay.globo.com/agora-na-tv/'},
    'record': {'name':'Record (RecordPlus)', 'url':'https://www.playplus.com/'},
    'band': {'name':'Band', 'url':'https://www.band.com.br/ao-vivo'},
    'cultura': {'name':'TV Cultura', 'url':'https://cultura.uol.com.br/aovivo/'},
    'tvbrasil': {'name':'TV Brasil', 'url':'https://tvbrasil.ebc.com.br/'},
    'redevida': {'name':'Rede Vida', 'url':'https://redevida.com.br/ao-vivo/'},
}


class BrowserError(ValueError):
    pass


class InternetBrowser:
    def __init__(self, executable=None, popen=None, safe=None, official_executable=None):
        self.executable = (executable if executable is not None else
                           shutil.which('chromium') or shutil.which('chromium-browser'))
        # Chrome is optional: never download proprietary components or Widevine.
        # On Debian Live the existing Chromium remains a safe fallback.
        self.official_executable = (official_executable if official_executable is not None
                                    else shutil.which('google-chrome-stable')
                                    or shutil.which('google-chrome')
                                    or self.executable)
        self.popen = popen or subprocess.Popen
        self.safe = (os.environ.get('KTV_OS_BROWSER_SAFE') == '1') if safe is None else bool(safe)

    def status(self):
        return {'available': bool(self.executable),
                'official_available': bool(self.official_executable),
                'official_browser': ('Chrome' if self.official_executable and
                                     'chrome' in os.path.basename(self.official_executable) and
                                     'chromium' not in os.path.basename(self.official_executable)
                                     else 'Chromium' if self.official_executable else None),
                'drm_verified': False}

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

    def open_official(self, destination):
        """Open a single allowlisted HTTPS provider site: never user URLs."""
        from smart_player import OFFICIAL_DESTINATIONS
        if type(destination) is not str or destination not in OFFICIAL_DESTINATIONS:
            raise BrowserError('Destino oficial nao reconhecido')
        if not self.official_executable:
            raise RuntimeError('Navegador compativel nao instalado')
        args=[self.official_executable, '--no-first-run', '--new-window', '--start-fullscreen']
        if self.safe:
            args.extend(('--disable-gpu', '--disable-gpu-compositing'))
        args.append(OFFICIAL_DESTINATIONS[destination]['url'])
        try:
            self.popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise RuntimeError('Nao foi possivel abrir o site oficial') from exc
        return {'opened': True, 'name': OFFICIAL_DESTINATIONS[destination]['name'],
                'browser': self.status()['official_browser'],
                'drm_verified': False}

    def open_broadcaster(self, ident):
        if not isinstance(ident,str) or ident not in BROADCASTERS:
            raise BrowserError('Emissora desconhecida')
        if not self.executable:
            raise RuntimeError('Chromium indisponivel neste dispositivo')
        args=[self.executable,'--no-first-run','--new-window','--start-fullscreen']
        if self.safe:
            args.extend(('--disable-gpu','--disable-gpu-compositing'))
        args.append(BROADCASTERS[ident]['url'])
        try:
            self.popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,start_new_session=True)
        except OSError as exc:
            raise RuntimeError('Falha ao abrir site oficial') from exc
        return {'opened':True,'name':BROADCASTERS[ident]['name']}

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
