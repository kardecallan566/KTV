"""KTV OS alpha: local-only browser shell for PC -> HDMI -> TV.

No firmware modification. This is an application running on an existing OS,
not a bootable Linux distribution yet. Standard library only.
"""
import argparse
import ctypes
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
STATE = Path.home() / '.config' / 'ktv-os'  # writable in Linux Live and Windows
VERSION = '0.1.0'
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

def detect_removable():
    """List *names* of likely removable drives. No automatic arbitrary file access."""
    result = []
    if sys.platform == 'win32':
        try:
            for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                volume = letter + ':\\'
                if ctypes.windll.kernel32.GetDriveTypeW(volume) == 2:
                    result.append({'label': 'Unidade USB ' + letter + ':', 'type': 'removable'})
        except (AttributeError, OSError):
            pass
    else:
        bases = (Path('/media') / (os.environ.get('USER') or ''), Path('/run/media') / (os.environ.get('USER') or ''), Path('/media'))
        seen = set()
        for base in bases:
            if not base.is_dir():
                continue
            try:
                for item in base.iterdir():
                    if item.is_dir() and not item.is_symlink() and str(item) not in seen:
                        seen.add(str(item))
                        result.append({'label': 'Unidade montada: ' + item.name, 'type': 'mounted'})
            except PermissionError:
                pass
    return result

def read_channels(state):
    file = state / 'channels.json'
    if not file.exists():
        state.mkdir(parents=True, exist_ok=True)
        file.write_text('{"channels": []}\n', encoding='utf-8')
    try:
        content = json.loads(file.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return []
    if not isinstance(content, dict) or not isinstance(content.get('channels'), list):
        return []
    channels = []
    for item in content['channels'][:100]:
        if not isinstance(item, dict):
            continue
        name, url = item.get('name'), item.get('url')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            continue
        if not isinstance(url, str) or len(url) > 1800 or any(x.isspace() for x in url):
            continue
        try:
            p = urlsplit(url)
            if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
                continue
            if not p.path.lower().endswith(('.m3u8', '.mp4')):
                continue
        except ValueError:
            continue
        category = item.get('category')
        channels.append({'name': name.strip(), 'url': url, 'category': category[:50] if isinstance(category, str) else ''})
    return channels

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

    def __init__(self, host='127.0.0.1', port=8787, media_dir=None, state_dir=None):
        self.state_dir = Path(state_dir) if state_dir else STATE
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = Path(media_dir).resolve(strict=True) if media_dir else None
        if self.media_dir and not self.media_dir.is_dir():
            raise ValueError('--media-dir deve ser uma pasta existente')
        super().__init__((host, port), KTVOSHandler)

class KTVOSHandler(BaseHTTPRequestHandler):
    server_version = 'KTV-OS/0.1'
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
        path = unquote(urlsplit(self.path).path)
        if path in STATIC:
            filename, mime = STATIC[path]
            return self.send_data(200, (APP / filename).read_bytes(), mime)
        if path == '/api/status':
            return self.send_json({'version': VERSION, 'host': self.server.server_address[0], 'usb_direct_tv': False})
        if path == '/api/devices':
            return self.send_json({'devices': detect_removable()})
        if path == '/api/channels':
            return self.send_json({'channels': read_channels(self.server.state_dir)})
        if path == '/api/media':
            return self.send_json({'items': read_media(self.server.media_dir)})
        if path.startswith('/media/'):
            return self.serve_media(path[len('/media/'):])
        return self.send_json({'error': 'Rota nao encontrada'}, 404)

    def serve_media(self, name):
        if (not self.server.media_dir or not name or '/' in name or '\\' in name or name.startswith('.') or
                Path(name).suffix.lower() not in MEDIA_EXTENSIONS):
            return self.send_json({'error': 'Midia nao autorizada'}, 404)
        file = self.server.media_dir / name
        try:
            if not file.is_file() or file.is_symlink() or file.resolve().parent != self.server.media_dir:
                return self.send_json({'error': 'Nao encontrado'}, 404)
            size = file.stat().st_size
        except OSError:
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
    print('=== KTV OS ALPHA 0.1 ===')
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
        server.server_close()

if __name__ == '__main__':
    main()
