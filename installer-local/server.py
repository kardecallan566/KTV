"""KTV local-only experiment: widget installer + media server + admin UI.

Pure Python standard library. Do not port-forward or expose this development server
on the Internet. Password over HTTP is only suitable for a trusted local network.
"""
import argparse
from datetime import datetime, timezone
import hmac
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from build import RELEASE, FILENAME, build, guess_ip

MAX_UPLOAD = 100 * 1024 * 1024
MAX_JSON = 64 * 1024
ALLOWED = {'.png': ('image', 'image/png'), '.jpg': ('image', 'image/jpeg'),
           '.jpeg': ('image', 'image/jpeg'), '.gif': ('image', 'image/gif'),
           '.mp4': ('video', 'video/mp4')}


def safe_name(name):
    # Do not trust a browser-supplied filename/path (including Windows separators).
    name = name.replace('\\', '/').split('/')[-1]
    stem = Path(name).stem
    stem = re.sub(r'[^A-Za-z0-9_-]+', '_', stem)[:50].strip('_') or 'midia'
    ext = Path(name).suffix.lower()
    return stem + ext if ext in ALLOWED else None


def valid_signature(ext, head):
    if ext == '.png': return head.startswith(b'\x89PNG\r\n\x1a\n')
    if ext in ('.jpg', '.jpeg'): return head.startswith(b'\xff\xd8\xff')
    if ext == '.gif': return head.startswith((b'GIF87a', b'GIF89a'))
    if ext == '.mp4': return len(head) >= 12 and head[4:8] == b'ftyp'
    return False


class KTVServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, public_ip, workspace=None):
        self.public_ip = public_ip
        self.workspace = Path(workspace) if workspace else ROOT / '.ktv'
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.media = self.workspace / 'media'
        self.media.mkdir(exist_ok=True)
        self.token_file = self.workspace / 'admin_token'
        if not self.token_file.exists():
            # Only created on first run; survives restarts.
            fd = os.open(str(self.token_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w', encoding='ascii') as file:
                file.write(secrets.token_urlsafe(24))
        self.token = self.token_file.read_text(encoding='ascii').strip()
        self.state_file = self.workspace / 'state.json'
        self.lock = threading.Lock()
        self.last_seen = 0
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                raise RuntimeError('state.json invalido. Faça backup e corrija manualmente.')
        else:
            self.state = {'version': 1, 'items': [], 'index': 0, 'playing': True}
            self.save_state()
        super().__init__(address, KTVRequest)
        assigned_port = self.server_address[1]
        self.base_url = 'http://{}{}'.format(public_ip, '' if assigned_port == 80 else ':' + str(assigned_port))
        self.output = build(public_ip, assigned_port)

    def save_state(self):
        temp = self.state_file.with_suffix('.json.tmp')
        temp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.state_file)

    def media_items(self):
        result = []
        for path in sorted(self.media.iterdir()):
            if path.is_file() and path.suffix.lower() in ALLOWED:
                kind, mime = ALLOWED[path.suffix.lower()]
                result.append({'id': path.name, 'name': path.name.split('_', 1)[-1],
                               'type': kind, 'bytes': path.stat().st_size,
                               'url': self.base_url + '/media/' + path.name})
        return result


class KTVRequest(BaseHTTPRequestHandler):
    server_version = 'KTV-Local/0.2'

    def log_message(self, fmt, *args):
        # Log only paths/methods. Tokens live in headers, not URL.
        print('[KTV] {} {}'.format(self.address_string(), fmt % args), flush=True)

    def reply(self, code, payload=b'', mime='application/json; charset=utf-8', cors=False):
        if isinstance(payload, str): payload = payload.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cors:
            self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try: self.wfile.write(payload)
        except (ConnectionError, BrokenPipeError): pass

    def json(self, code, obj, cors=False):
        self.reply(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'), cors=cors)

    def authorized(self):
        provided = self.headers.get('X-KTV-Token', '')
        if not hmac.compare_digest(provided, self.server.token):
            self.json(401, {'error': 'Token administrativo invalido'});
            return False
        return True

    def file_response(self, path, mime):
        if not path.is_file(): return self.json(404, {'error': 'Nao encontrado'})
        length = path.stat().st_size
        # Video seek requires HTTP Range (bytes).
        start, end, status = 0, length - 1, 200
        range_header = self.headers.get('Range', '')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if not match or (not match.group(1) and not match.group(2)):
                return self.range_error(length)
            try:
                if not match.group(1):
                    suffix = int(match.group(2)); start = max(0, length - suffix)
                else:
                    start = int(match.group(1))
                    if match.group(2): end = min(length - 1, int(match.group(2)))
                if start > end or start >= length or length == 0: return self.range_error(length)
            except ValueError: return self.range_error(length)
            status = 206
        total = end - start + 1
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(total))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        if status == 206:
            self.send_header('Content-Range', 'bytes {}-{}/{}'.format(start, end, length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            with path.open('rb') as f:
                f.seek(start)
                remaining = total
                while remaining:
                    block = f.read(min(65536, remaining))
                    if not block: break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (ConnectionError, BrokenPipeError): pass

    def range_error(self, size):
        self.send_response(416)
        self.send_header('Content-Range', 'bytes */{}'.format(size))
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in ('/', '/admin', '/admin/'):
            return self.file_response(ROOT / 'admin-web' / 'index.html', 'text/html; charset=utf-8')
        if path == '/api/health':
            return self.json(200, {'app': 'KTV Local', 'status': 'ok', 'version': '0.2.0'})
        if path == '/api/state':
            self.server.last_seen = time.time()
            with self.server.lock:
                data = dict(self.server.state)
                data['items'] = [dict(item, url=self.server.base_url + '/media/' + item['id'])
                                 for item in data['items']]
            return self.json(200, data, cors=True)
        if path == '/api/media':
            if not self.authorized(): return
            return self.json(200, {'items': self.server.media_items()})
        if path == '/api/status':
            if not self.authorized(): return
            with self.server.lock: version = self.server.state['version']
            return self.json(200, {'version': version, 'last_poll_seconds':
                                    round(time.time() - self.server.last_seen) if self.server.last_seen else None,
                                    'base_url': self.server.base_url})
        if path == '/widgetlist.xml':
            return self.file_response(RELEASE / 'widgetlist.xml', 'application/xml; charset=utf-8')
        if path.startswith('/Widget/'):
            name = path[len('/Widget/'):]
            if name != FILENAME: return self.json(404, {'error':'Widget desconhecido'})
            return self.file_response(RELEASE / 'Widget' / FILENAME, 'application/zip')
        if path.startswith('/media/'):
            name = path[len('/media/'):]
            if '/' in name or '\\' in name or name.startswith('.') or not name:
                return self.json(404, {'error':'Arquivo invalido'})
            extension = Path(name).suffix.lower()
            if extension not in ALLOWED: return self.json(404, {'error': 'Formato invalido'})
            return self.file_response(self.server.media / name, ALLOWED[extension][1])
        if path == '/preview' or path == '/preview/':
            return self.file_response(ROOT / 'tv-orsay' / 'index.html', 'text/html; charset=utf-8')
        if path.startswith('/preview/'):
            name = path[len('/preview/'):]
            if name == 'js/runtime-config.js':
                return self.reply(200, 'window.KTV_CONFIG = {server: "' + self.server.base_url + '", pollMs: 4000};\n',
                                  'application/javascript; charset=utf-8')
            if name not in ('js/app.js', 'css/style.css'):
                return self.json(404, {'error': 'Nao encontrado'})
            mime = 'application/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
            return self.file_response(ROOT / 'tv-orsay' / name, mime)
        return self.json(404, {'error': 'Nao encontrado'})

    def do_POST(self):
        url = urlsplit(self.path)
        path = url.path
        if path not in ('/api/admin/upload', '/api/admin/state', '/api/admin/command'):
            return self.json(404, {'error': 'Nao encontrado'})
        if not self.authorized(): return
        try: size = int(self.headers.get('Content-Length', '-1'))
        except ValueError: return self.json(411, {'error': 'Content-Length necessario'})
        if size < 0: return self.json(411, {'error': 'Content-Length necessario'})
        if path == '/api/admin/upload':
            if size == 0 or size > MAX_UPLOAD: return self.json(413, {'error': 'Arquivo deve ter ate 100 MB'})
            name = safe_name(parse_qs(url.query).get('filename', [''])[0])
            if not name: return self.json(400, {'error': 'Extensao nao permitida'})
            extension = Path(name).suffix.lower()
            final = secrets.token_hex(6) + '_' + name
            target = self.server.media / final
            remaining = size
            first = b''
            try:
                with target.open('xb') as output:
                    while remaining:
                        chunk = self.rfile.read(min(65536, remaining))
                        if not chunk: raise OSError('Upload incompleto')
                        if not first: first = chunk[:32]
                        output.write(chunk)
                        remaining -= len(chunk)
                if not valid_signature(extension, first):
                    target.unlink(missing_ok=True)
                    return self.json(400, {'error': 'Assinatura de arquivo invalida'})
                return self.json(201, {'ok': True, 'id': final})
            except OSError:
                target.unlink(missing_ok=True)
                return self.json(400, {'error': 'Upload falhou'})
        if size > MAX_JSON: return self.json(413, {'error': 'JSON muito grande'})
        try: data = json.loads(self.rfile.read(size).decode('utf-8'))
        except (UnicodeError, ValueError): return self.json(400, {'error': 'JSON invalido'})
        if not isinstance(data, dict): return self.json(400, {'error': 'Objeto JSON esperado'})
        with self.server.lock:
            current = self.server.state
            if path == '/api/admin/state':
                ids = data.get('ids')
                if not isinstance(ids, list) or len(ids) > 200 or any(not isinstance(i, str) for i in ids):
                    return self.json(400, {'error': 'Lista de ids invalida'})
                by_id = {i['id']: i for i in self.server.media_items()}
                if any(i not in by_id for i in ids): return self.json(400, {'error': 'Midia nao encontrada'})
                items = []
                for identity in ids:
                    item = dict(by_id[identity])
                    item['duration'] = 10
                    items.append(item)
                self.server.state = {'version': current['version'] + 1, 'items': items,
                                     'index': 0, 'playing': True}
            else:
                command = data.get('command')
                if command not in ('next', 'previous', 'play', 'pause', 'clear'):
                    return self.json(400, {'error': 'Comando invalido'})
                next_state = dict(current)
                count = len(next_state['items'])
                if command == 'next' and count: next_state['index'] = (next_state['index'] + 1) % count
                if command == 'previous' and count: next_state['index'] = (next_state['index'] - 1) % count
                if command == 'play': next_state['playing'] = True
                if command == 'pause': next_state['playing'] = False
                if command == 'clear': next_state.update(items=[], index=0, playing=True)
                next_state['version'] += 1
                self.server.state = next_state
            self.server.save_state()
            response = dict(self.server.state)
        return self.json(200, response)


def main():
    parser = argparse.ArgumentParser(description='KTV local: widget Orsay + API + painel')
    parser.add_argument('--ip', default=guess_ip(), help='IPv4 do computador visto pela TV')
    parser.add_argument('--port', type=int, default=80, help='Porta HTTP. A sincronizacao Samsung usa normalmente 80.')
    parser.add_argument('--listen', default='0.0.0.0', help='Endereco de escuta (padrao: LAN)')
    args = parser.parse_args()
    try:
        server = KTVServer((args.listen, args.port), args.ip)
    except OSError as exc:
        print('Falha ao abrir servidor. Porta 80 ocupada/bloqueada? {}'.format(exc))
        sys.exit(1)
    print('\n=== KTV LOCAL v0.2 ===')
    print('IP LAN:     ', args.ip)
    print('Instalador: ', server.base_url + '/widgetlist.xml')
    print('Painel:     ', server.base_url + '/admin/')
    print('Preview:    ', server.base_url + '/preview/')
    print('TOKEN ADMIN:', server.token)
    print('USB:        ', server.output['usb'])
    print('\nATENCAO: apenas rede local confiavel. Nao encaminhe a porta para a Internet.')
    print('CTRL+C para encerrar.\n', flush=True)
    try: server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: print('\nServidor encerrado.')
    finally: server.server_close()


if __name__ == '__main__': main()
