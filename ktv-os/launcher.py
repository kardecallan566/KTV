"""KTV OS alpha: local-only browser shell for PC -> HDMI -> TV.

No firmware modification. This is an application running on an existing OS,
not a bootable Linux distribution yet. Standard library only.
"""
import argparse
import hashlib
import ctypes
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from player import NativePlayer, safe_media_path
from channel_store import ChannelStore, ChannelError
from persistence import PersistenceManager, PersistenceError
from hardware import HardwareManager, HardwareError
from threading import Event, Thread
APP = ROOT / 'app'
STATE = Path.home() / '.config' / 'ktv-os'  # writable in Linux Live and Windows
VERSION = '0.6.0'
MEDIA_EXTENSIONS = {
    '.mp4': ('video', 'video/mp4'), '.webm': ('video', 'video/webm'),
    '.mp3': ('audio', 'audio/mpeg'), '.m4a': ('audio', 'audio/mp4'),
    '.jpg': ('image', 'image/jpeg'), '.jpeg': ('image', 'image/jpeg'),
    '.png': ('image', 'image/png'), '.gif': ('image', 'image/gif'),
}
STATIC = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/index.html': ('index.html', 'text/html; charset=utf-8'),
    '/style.css': ('style.css', 'text/css; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
}

def usb_mounts():
    """Return only removable volumes currently mounted on the host PC.

    No arbitrary directory / disk can be selected through an HTTP parameter.
    The paths are not exposed as network-accessible mount operations.
    """
    volumes = {}
    if sys.platform == 'win32':
        try:
            for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                volume = Path(letter + ':\\')
                if ctypes.windll.kernel32.GetDriveTypeW(str(volume)) == 2:
                    volumes['usb-' + letter.lower()] = (volume, 'USB ' + letter + ':')
        except (AttributeError, OSError):
            pass
    else:
        user = os.environ.get('USER') or 'user'
        bases = (Path('/media') / user, Path('/run/media') / user)
        for base in bases:
            if not base.is_dir():
                continue
            try:
                for item in base.iterdir():
                    if item.is_dir() and not item.is_symlink() and item.is_mount():
                        digest = hashlib.sha256(str(item).encode('utf-8')).hexdigest()[:12]
                        volumes['usb-' + digest] = (item, 'USB ' + item.name)
            except (PermissionError, OSError):
                pass
    return volumes


def detect_removable():
    return [{'id': key, 'label': label, 'type': 'removable'}
            for key, (_, label) in usb_mounts().items()]


def selected_media_root(media_dir, source='local', device=None):
    if source == 'local':
        return media_dir
    if source != 'usb' or not isinstance(device, str):
        return None
    match = usb_mounts().get(device)
    return match[0] if match else None


def read_channels(state):
    """Backward-compatible read facade (channel updates use ChannelStore)."""
    return ChannelStore(state).load()


def read_media(media_root):
    if not media_root:
        return []
    try:
        entries = sorted(media_root.iterdir(), key=lambda x: x.name.casefold())
    except (PermissionError, OSError):
        return []
    found = []
    for item in entries[:600]:
        if (not item.is_file() or item.is_symlink() or item.name.startswith('.') or item.suffix.lower() not in MEDIA_EXTENSIONS):
            continue
        try:
            type_name, _ = MEDIA_EXTENSIONS[item.suffix.lower()]
            found.append({'name': item.name, 'type': type_name, 'bytes': item.stat().st_size})
        except (OSError, ValueError):
            pass
    return found

class KTVOSServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host='127.0.0.1', port=8787, media_dir=None, state_dir=None, player=None, hardware=None):
        self.state_dir = Path(state_dir) if state_dir else STATE
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = Path(media_dir).resolve(strict=True) if media_dir else None
        if self.media_dir and not self.media_dir.is_dir():
            raise ValueError('--media-dir deve ser uma pasta existente')
        self.player = player if player is not None else NativePlayer()
        self.hardware = hardware if hardware is not None else HardwareManager()
        self.channels = ChannelStore(self.state_dir)
        self.persistence = PersistenceManager(self.channels)
        self._persistence_stop = Event()
        super().__init__((host, port), KTVOSHandler)
        # Automount can finish after the graphical session starts.
        self.persistence.poll(usb_mounts())
        self._persistence_thread = Thread(target=self._persistence_loop, daemon=True)
        self._persistence_thread.start()

    def _persistence_loop(self):
        while not self._persistence_stop.wait(3):
            self.persistence.poll(usb_mounts())

    def server_close(self):
        self._persistence_stop.set()
        self.hardware.close()
        super().server_close()

class KTVOSHandler(BaseHTTPRequestHandler):
    server_version = 'KTV-OS/0.6'
    def log_message(self, fmt, *args):
        print('[KTV OS] ' + fmt % args, flush=True)

    def send_data(self, status, body, mime):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (OSError, ConnectionError):
            pass

    def send_json(self, payload, status=200):
        self.send_data(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in STATIC:
            filename, mime = STATIC[path]
            return self.send_data(200, (APP / filename).read_bytes(), mime)
        if path == '/api/status':
            return self.send_json({'version': VERSION, 'host': self.server.server_address[0],
                                   'usb_direct_tv': False, 'player': self.server.player.status(),
                                   'persistence': self.server.persistence.status(usb_mounts())})
        if path == '/api/devices':
            return self.send_json({'devices': detect_removable()})
        if path == '/api/channels':
            try:
                return self.send_json({'channels': self.server.channels.load()})
            except (ChannelError, OSError) as exc:
                return self.send_json({'error': str(exc)}, 500)
        if path == '/api/hardware':
            return self.send_json({'hardware': self.server.hardware.status()})
        if path == '/api/persistence/status':
            return self.send_json({'persistence': self.server.persistence.status(usb_mounts())})
        if path == '/api/player/status':
            return self.send_json({'player': self.server.player.status()})
        if path == '/api/media':
            params = parse_qs(url.query)
            source = params.get('source', ['local'])[0]
            device = params.get('device', [''])[0]
            root = selected_media_root(self.server.media_dir, source, device)
            if root is None and source != 'local':
                return self.send_json({'error': 'Dispositivo nao autorizado ou desmontado'}, 404)
            return self.send_json({'items': read_media(root)})
        if path.startswith('/media/usb/'):
            parts = path[len('/media/usb/'):].split('/')
            if len(parts) != 2:
                return self.send_json({'error': 'Caminho USB invalido'}, 404)
            root = selected_media_root(self.server.media_dir, 'usb', parts[0])
            return self.serve_media(parts[1], root=root)
        if path.startswith('/media/'):
            return self.serve_media(path[len('/media/'):])
        return self.send_json({'error': 'Rota nao encontrada'}, 404)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ('/api/player/play', '/api/player/stop', '/api/channels/change', '/api/channels/usb-backup', '/api/channels/usb-restore', '/api/persistence/enable', '/api/persistence/disable',
                        '/api/hardware/video/preview', '/api/hardware/video/confirm',
                        '/api/hardware/video/cancel', '/api/hardware/audio/output',
                        '/api/hardware/audio/volume', '/api/hardware/audio/mute'):
            return self.send_json({'error': 'Rota nao encontrada'}, 404)

        # Only this machine may write to the playback controller.
        # JSON content type rejects HTML form posts from unrelated origins.
        origin = self.headers.get('Origin')
        expected = 'http://127.0.0.1:{}'.format(self.server.server_address[1])
        if origin is not None and origin != expected:
            return self.send_json({'error': 'Origem nao autorizada'}, 403)
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            return self.send_json({'error': 'JSON obrigatorio'}, 415)
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if size < 0 or size > 4096:
                return self.send_json({'error': 'Tamanho invalido'}, 413)
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('Payload deve ser objeto')
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json({'error': 'JSON invalido'}, 400)

        if path.startswith('/api/hardware/'):
            try:
                hw = self.server.hardware
                if path.endswith('/video/preview'):
                    result = hw.preview(payload.get('output'), payload.get('mode'))
                elif path.endswith('/video/confirm'):
                    result = hw.confirm(payload.get('token'))
                elif path.endswith('/video/cancel'):
                    result = hw.cancel()
                elif path.endswith('/audio/output'):
                    result = hw.choose_audio(payload.get('sink'))
                elif path.endswith('/audio/volume'):
                    result = hw.set_volume(payload.get('volume'))
                elif path.endswith('/audio/mute'):
                    result = hw.toggle_mute()
                else:
                    return self.send_json({'error': 'Comando de hardware desconhecido'}, 404)
                return self.send_json({'ok': True, 'result': result})
            except HardwareError as exc:
                return self.send_json({'error': str(exc)}, 400)
        if path in ('/api/persistence/enable', '/api/persistence/disable'):
            try:
                if path.endswith('enable'):
                    info = self.server.persistence.enroll(usb_mounts(), payload.get('device'))
                else:
                    info = self.server.persistence.disable(usb_mounts())
                return self.send_json({'ok': True, 'persistence': info})
            except (PersistenceError, ChannelError, OSError) as exc:
                return self.send_json({'error': str(exc)}, 400)

        if path == '/api/channels/change':
            action = payload.get('action')
            if action not in ('add','edit','delete','favorite','up','down'):
                return self.send_json({'error': 'Acao desconhecida'}, 400)
            try:
                result = self.server.channels.change(action, payload)
                persisted = self.server.persistence.sync(usb_mounts())
                return self.send_json({'ok': True, 'channels': result, 'persistence': persisted})
            except (ChannelError, OSError) as exc:
                return self.send_json({'error': str(exc)}, 400)

        if path in ('/api/channels/usb-backup', '/api/channels/usb-restore'):
            identifier = payload.get('device')
            if not isinstance(identifier, str):
                return self.send_json({'error': 'Selecione uma unidade USB'}, 400)
            # Look up the ID generated by the OS. The request cannot specify a path.
            matched = usb_mounts().get(identifier)
            if matched is None:
                return self.send_json({'error': 'Pendrive indisponivel'}, 404)
            try:
                if path.endswith('usb-backup'):
                    name = self.server.channels.export_to_usb(matched[0])
                    return self.send_json({'ok': True, 'message': 'Backup salvo: ' + name})
                restored = self.server.channels.import_from_usb(matched[0])
                persisted = self.server.persistence.sync(usb_mounts())
                return self.send_json({'ok': True, 'channels': restored, 'persistence': persisted})
            except (ChannelError, OSError) as exc:
                return self.send_json({'error': str(exc)}, 400)

        if path == '/api/player/stop':
            self.server.player.stop()
            return self.send_json({'ok': True, 'player': self.server.player.status()})
        kind = payload.get('kind')
        try:
            if kind == 'channel':
                idx = payload.get('index')
                channels = self.server.channels.load()
                if type(idx) is not int or idx < 0 or idx >= len(channels):
                    raise ValueError('Canal desconhecido')
                entry = channels[idx]
                source, title = entry['url'], entry['name']
            elif kind in ('media', 'usb'):
                name = payload.get('name')
                root = selected_media_root(
                    self.server.media_dir, 'usb' if kind == 'usb' else 'local',
                    payload.get('device')
                )
                if root is None:
                    raise ValueError('Unidade indisponivel')
                file = safe_media_path(root, name, MEDIA_EXTENSIONS)
                source, title = str(file), file.name
            else:
                raise ValueError('Tipo de conteudo invalido')
            info = self.server.player.play(source, title)
        except (ValueError, OSError) as exc:
            return self.send_json({'error': str(exc)}, 400)
        except RuntimeError as exc:
            return self.send_json({'error': str(exc)}, 503)
        return self.send_json({'ok': True, 'player': info})

    def serve_media(self, name, root=None):
        root = root if root is not None else self.server.media_dir
        if root is None:
            return self.send_json({'error': 'Midia nao autorizada'}, 404)
        try:
            file = safe_media_path(root, name, MEDIA_EXTENSIONS)
            size = file.stat().st_size
        except (OSError, ValueError):
            return self.send_json({'error': 'Nao encontrado'}, 404)
        start, end, code = 0, size - 1, 200
        req_range = self.headers.get('Range', '')
        if req_range:
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', req_range)
            if not m or (not m.group(1) and not m.group(2)) or size <= 0:
                return self.range_invalid(size)
            if not m.group(1):
                suffix = int(m.group(2))
                if suffix == 0:
                    return self.range_invalid(size)
                start = max(0, size - suffix)
            else:
                start = int(m.group(1))
                if m.group(2):
                    end = min(end, int(m.group(2)))
            if start >= size or start > end:
                return self.range_invalid(size)
            code = 206
        if size <= 0:
            return self.send_json({'error': 'Arquivo vazio'}, 404)
        total = end - start + 1
        self.send_response(code)
        self.send_header('Content-Type', MEDIA_EXTENSIONS[file.suffix.lower()][1])
        self.send_header('Content-Length', str(total))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        if code == 206:
            self.send_header('Content-Range', 'bytes {}-{}/{}'.format(start, end, size))
        self.end_headers()
        try:
            with file.open('rb') as stream:
                stream.seek(start)
                while total > 0:
                    chunk = stream.read(min(65536, total))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    total -= len(chunk)
        except (OSError, BrokenPipeError, ConnectionError):
            pass

    def range_invalid(self, size):
        self.send_response(416)
        self.send_header('Content-Range', 'bytes */{}'.format(size))
        self.send_header('Content-Length', '0')
        self.end_headers()

def main():
    parser = argparse.ArgumentParser(description='KTV OS alpha — interface para PC conectado a TV via HDMI')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--media-dir', help='Pasta local autorizada para exibir midias; leitura apenas')
    parser.add_argument('--open', action='store_true', help='Abrir no navegador padrao')
    args = parser.parse_args()
    server = KTVOSServer(port=args.port, media_dir=args.media_dir)
    url = 'http://127.0.0.1:{}'.format(server.server_address[1])
    print('=== KTV OS ALPHA 0.6 ===')
    print('Tela:', url)
    print('Pasta de midias:', server.media_dir or '(nenhuma: use --media-dir)')
    print('Canais:', server.state_dir / 'channels.json')
    print('PC -> HDMI -> TV (USB da Samsung NAO inicia sistemas operacionais)')
    print('Ctrl+C para encerrar')
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.player.close()
        server.server_close()

if __name__ == '__main__':
    main()
