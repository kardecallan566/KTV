"""Opt-in KTV OS state persistence on a SECOND removable USB drive.

No formatting, mounting, partitioning, shell commands or access to the
computer's internal disks. Only drives offered by the OS removable-volume
inventory can be enrolled. Marker files permit automatic restore on reboot.
"""
import json
from pathlib import Path
import threading
import uuid

from channel_store import atomic_write, validate_collection, ChannelError, MAX_BACKUP

FOLDER = '.ktv-os-persistence'
MARKER = 'device.json'
SNAPSHOT = 'channels.json'
FORMAT = 'ktv-os-persistence-v1'


class PersistenceError(ValueError):
    pass


def _folder(root, create=False):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PersistenceError('Unidade USB nao montada')
    folder = root / FOLDER
    if folder.is_symlink():
        raise PersistenceError('Diretorio de persistencia inseguro')
    if create:
        folder.mkdir(mode=0o700, exist_ok=True)
    if not folder.is_dir():
        raise PersistenceError('Persistencia nao configurada neste pendrive')
    return folder


def _read_json(file):
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_BACKUP:
        raise PersistenceError('Arquivo persistente invalido ou ausente')
    try:
        return json.loads(file.read_text(encoding='utf-8'))
    except (ValueError, UnicodeDecodeError, OSError) as exc:
        raise PersistenceError('Dados persistentes invalidos: {}'.format(exc))


def _check_marker(folder):
    marker = _read_json(folder / MARKER)
    if not isinstance(marker, dict) or marker.get('format') != FORMAT:
        raise PersistenceError('Marcador nao corresponde ao KTV OS')
    identity = marker.get('identity')
    if not isinstance(identity, str) or len(identity) != 32:
        raise PersistenceError('Identificador de persistencia invalido')
    try:
        uuid.UUID(hex=identity)
    except ValueError:
        raise PersistenceError('Identificador corrompido')
    return identity


def _snapshot(folder):
    data = _read_json(folder / SNAPSHOT)
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise PersistenceError('Backup persistente invalido')
    try:
        return validate_collection(data.get('channels'))
    except ChannelError as exc:
        raise PersistenceError(str(exc))


class PersistenceManager:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.active_id = None
        self.active_identity = None
        self.pending = False
        self.error = ''

    def status(self, mounts):
        with self.lock:
            connected = self.active_id in mounts if self.active_id else False
            return {
                'enabled': self.active_id is not None,
                'connected': connected,
                'device': self.active_id,
                'pending': self.pending,
                'error': self.error
            }

    def enroll(self, mounts, device):
        """Explicit activation. Copies current channels onto the selected USB."""
        with self.lock:
            if not isinstance(device, str) or device not in mounts:
                raise PersistenceError('Selecione um pendrive de dados montado')
            root = mounts[device][0]
            folder = _folder(root, create=True)
            marker_path = folder / MARKER
            identity = _check_marker(folder) if marker_path.exists() or marker_path.is_symlink() else uuid.uuid4().hex
            channels = self.store.load()
            atomic_write(folder / SNAPSHOT, {'format': FORMAT, 'channels': channels})
            atomic_write(marker_path, {'format': FORMAT, 'identity': identity})
            self.active_id = device
            self.active_identity = identity
            self.pending = False
            self.error = ''
            return self.status(mounts)

    def sync(self, mounts):
        """Write only to the enrolled and verified removable USB."""
        with self.lock:
            if not self.active_id:
                return self.status(mounts)
            mounted = mounts.get(self.active_id)
            if mounted is None:
                self.pending = True
                self.error = 'Pendrive removido; alteracoes ainda nao foram salvas nele'
                return self.status(mounts)
            try:
                folder = _folder(mounted[0])
                if _check_marker(folder) != self.active_identity:
                    raise PersistenceError('Pendrive diferente do dispositivo configurado')
                atomic_write(folder / SNAPSHOT, {'format': FORMAT, 'channels': self.store.load()})
                self.pending = False
                self.error = ''
            except (ChannelError, PersistenceError, OSError) as exc:
                self.pending = True
                self.error = str(exc)
            return self.status(mounts)

    def poll(self, mounts):
        """Auto-restore only with an empty local state and exactly one valid marker.

        An existing local channels.json is NEVER replaced automatically. If a
        previously-enrolled drive reconnects, flush pending local changes instead.
        """
        with self.lock:
            if self.active_id:
                if self.pending and self.active_id in mounts:
                    return self.sync(mounts)
                return self.status(mounts)
            if self.store.path.exists():
                return self.status(mounts)
            candidates = []
            for device, (root, _label) in mounts.items():
                try:
                    folder = _folder(root)
                    identity = _check_marker(folder)
                    channels = _snapshot(folder)
                    candidates.append((device, identity, channels))
                except (PersistenceError, OSError):
                    continue
            if len(candidates) > 1:
                self.error = 'Mais de um pendrive persistente encontrado; escolha manualmente'
                return self.status(mounts)
            if len(candidates) != 1:
                return self.status(mounts)
            device, identity, channels = candidates[0]
            try:
                self.store.save(channels)
            except (ChannelError, OSError) as exc:
                self.error = str(exc)
                return self.status(mounts)
            self.active_id = device
            self.active_identity = identity
            self.error = ''
            return self.status(mounts)

    def disable(self, mounts):
        """Stop automatic writing. Keep USB files untouched for future recovery."""
        with self.lock:
            self.active_id = None
            self.active_identity = None
            self.pending = False
            self.error = ''
            return self.status(mounts)
