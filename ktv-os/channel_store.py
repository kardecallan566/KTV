"""Local channel management and explicit USB backup for KTV OS.

No remote network listener, arbitrary path input, or automatic USB writes.
The Linux Live session is ephemeral: users explicitly export/restore backups.
"""
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlsplit
import uuid
from stream_urls import validate_stream_url, StreamURLError

LIMIT = 250
MAX_IMPORT_M3U = 96 * 1024
FORMAT = 'ktv-os-channels-v1'
BACKUP_NAME = 'KTVOS-channels-backup.json'
ID_PATTERN = re.compile(r'^[0-9a-f]{32}$')
MAX_BACKUP = 256 * 1024


class ChannelError(ValueError):
    pass


def validate_channel(value, require_id=False):
    if not isinstance(value, dict):
        raise ChannelError('Canal invalido')
    name = value.get('name')
    url = value.get('url')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
        raise ChannelError('Nome deve conter entre 1 e 80 caracteres')
    try:
        validate_stream_url(url)
    except StreamURLError as exc:
        raise ChannelError(str(exc)) from exc
    category = value.get('category', '')
    if not isinstance(category, str) or len(category) > 50 or any(ord(c) < 32 for c in category):
        raise ChannelError('Categoria invalida')
    favorite = value.get('favorite', False)
    if not isinstance(favorite, bool):
        raise ChannelError('Favorito invalido')
    ident = value.get('id')
    if not ident and not require_id:
        ident = uuid.uuid5(uuid.NAMESPACE_URL, name.strip() + '\x00' + url).hex
    if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
        raise ChannelError('Identificador invalido')
    return {
        'id': ident, 'name': name.strip(), 'url': url,
        'category': category.strip(), 'favorite': favorite
    }


def validate_collection(channels):
    if not isinstance(channels, list) or len(channels) > LIMIT:
        raise ChannelError('Limite de 250 canais')
    result, seen = [], set()
    for value in channels:
        channel = validate_channel(value)
        if channel['id'] in seen:
            raise ChannelError('Identificador duplicado no backup')
        seen.add(channel['id'])
        result.append(channel)
    return result


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ChannelError('Arquivo de configuracao inseguro')
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(encoded) > MAX_BACKUP:
        raise ChannelError('Arquivo ultrapassa 256 KB')
    fd, temporary = tempfile.mkstemp(prefix='.ktv-os-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(encoded)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_m3u(text):
    """Parse user-provided authorized M3U (not HLS segment/master playlists).

    Ignore unknown options, non-HTTP sources and unsupported extensions.
    Never fetch URLs or execute EXTVLCOPT/Kodi plugin directives.
    """
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_IMPORT_M3U:
        raise ChannelError('Lista M3U maior que 96 KB ou invalida')
    if not text.lstrip('\ufeff').lstrip().startswith('#EXTM3U'):
        raise ChannelError('Insira uma playlist M3U iniciada por #EXTM3U')
    pending = None
    entries, seen = [], set()
    ignored = 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF:'):
            header, _, display_name = line.partition(',')
            name = display_name.strip()
            group_match = re.search(r'group-title="([^"]{1,50})"', header)
            group = group_match.group(1) if group_match else 'Importado'
            pending = (name, group)
        elif not line or line.startswith('#'):
            continue
        else:
            if pending:
                name, group = pending
                try:
                    entry = validate_channel({'name': name, 'url': line,
                                              'category': group})
                    if entry['url'] in seen:
                        ignored += 1
                    elif len(entries) < LIMIT:
                        entries.append(entry)
                        seen.add(entry['url'])
                    else:
                        ignored += 1
                except ChannelError:
                    ignored += 1
            pending = None
    if not entries:
        raise ChannelError('Nenhum canal de transmissao HTTP(S) direta valido na playlist')
    return entries, ignored


class ChannelStore:
    def __init__(self, state_dir):
        self.path = Path(state_dir) / 'channels.json'
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if not self.path.exists():
                return []
            if self.path.is_symlink():
                raise ChannelError('Configuracao e link simbolico')
            try:
                raw = self.path.read_bytes()
                if len(raw) > MAX_BACKUP:
                    raise ChannelError('Configuracao muito grande')
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ChannelError('Formato de canais invalido')
                # Compatibilidade com a Alpha 0.3: entradas antigas invalidas sao
                # ignoradas individualmente, nao inutilizam a lista inteira.
                entries = value.get('channels')
                if not isinstance(entries, list):
                    raise ChannelError('Lista de canais invalida')
                result, seen = [], set()
                for raw_item in entries[:LIMIT]:
                    try:
                        item = validate_channel(raw_item)
                    except ChannelError:
                        continue
                    if item['id'] in seen:
                        continue
                    seen.add(item['id'])
                    result.append(item)
                return result
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ChannelError('Arquivo de canais corrompido: {}'.format(exc))

    def save(self, channels):
        with self.lock:
            cleaned = validate_collection(channels)
            atomic_write(self.path, {'channels': cleaned})
            return cleaned

    def change(self, action, data):
        with self.lock:
            current = self.load()
            if action == 'add':
                if len(current) >= LIMIT:
                    raise ChannelError('Limite de 250 canais')
                item = validate_channel({
                    'name': data.get('name'), 'url': data.get('url'),
                    'category': data.get('category', ''), 'favorite': False,
                    'id': uuid.uuid4().hex
                }, require_id=True)
                current.append(item)
            else:
                ident = data.get('id')
                index = next((i for i, c in enumerate(current) if c['id'] == ident), None)
                if index is None:
                    raise ChannelError('Canal nao encontrado')
                if action == 'edit':
                    previous = current[index]
                    current[index] = validate_channel({
                        'id': ident,
                        'name': data.get('name'),
                        'url': data.get('url'),
                        'category': data.get('category', ''),
                        'favorite': previous['favorite']
                    }, require_id=True)
                elif action == 'delete':
                    del current[index]
                elif action == 'favorite':
                    current[index]['favorite'] = not current[index]['favorite']
                elif action in ('up', 'down'):
                    other = index + (-1 if action == 'up' else 1)
                    if 0 <= other < len(current):
                        current[index], current[other] = current[other], current[index]
                else:
                    raise ChannelError('Acao nao autorizada')
            return self.save(current)

    def export_to_usb(self, volume):
        with self.lock:
            volume = Path(volume)
            if not volume.is_dir() or volume.is_symlink():
                raise ChannelError('Unidade nao montada')
            path = volume / BACKUP_NAME
            if path.is_symlink():
                raise ChannelError('Backup USB e link simbolico')
            atomic_write(path, {'format': FORMAT, 'channels': self.load()})
            return str(path.name)

    def import_from_usb(self, volume):
        with self.lock:
            volume = Path(volume)
            path = volume / BACKUP_NAME
            if not volume.is_dir() or volume.is_symlink() or path.is_symlink() or not path.is_file():
                raise ChannelError('Backup USB nao encontrado')
            if path.stat().st_size > MAX_BACKUP:
                raise ChannelError('Backup excede 256 KB')
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ChannelError('Backup USB invalido: {}'.format(exc))
            if not isinstance(value, dict) or value.get('format') != FORMAT:
                raise ChannelError('Formato do backup USB incompativel')
            restored = validate_collection(value.get('channels'))
            return self.save(restored)

    def import_m3u(self, content):
        """Append deduplicated streams in an atomic transaction."""
        new, ignored = parse_m3u(content)
        with self.lock:
            current = self.load()
            seen = {entry['url'] for entry in current}
            added = 0
            for entry in new:
                if entry['url'] in seen:
                    ignored += 1
                    continue
                if len(current) >= LIMIT:
                    ignored += 1
                    continue
                # Preserve existing user favorites and channel order.
                current.append(entry)
                seen.add(entry['url'])
                added += 1
            if added:
                current = self.save(current)
            return {'channels': current, 'added': added, 'ignored': ignored}
