"""Local Pluto TV favorites: channel IDs only, never expiring signed URLs."""
import json
from pathlib import Path
import re
import threading

from channel_store import atomic_write, ChannelError

FORMAT = 'ktv-pluto-favorites-v1'
MAX_FAVORITES = 200
MAX_BYTES = 16 * 1024
ID = re.compile(r'^[0-9a-f]{24}$')


class PlutoFavoritesError(ValueError):
    pass


def valid_ids(value):
    if not isinstance(value, list) or len(value) > MAX_FAVORITES:
        raise PlutoFavoritesError('Lista de favoritos invalida')
    seen = set()
    result = []
    for item in value:
        if not isinstance(item, str) or not ID.fullmatch(item) or item in seen:
            raise PlutoFavoritesError('Identificador de favorito invalido')
        result.append(item)
        seen.add(item)
    return result


class PlutoFavorites:
    def __init__(self, state_dir):
        self.path = Path(state_dir) / 'pluto_favorites.json'
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            if not self.path.exists() and not self.path.is_symlink():
                return []
            if self.path.is_symlink() or not self.path.is_file():
                raise PlutoFavoritesError('Arquivo de favoritos inseguro')
            if self.path.stat().st_size > MAX_BYTES:
                raise PlutoFavoritesError('Favoritos excedem o tamanho permitido')
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError, ValueError, UnicodeError) as exc:
                raise PlutoFavoritesError('Favoritos corrompidos') from exc
            if not isinstance(data, dict) or data.get('format') != FORMAT:
                raise PlutoFavoritesError('Formato de favoritos invalido')
            return valid_ids(data.get('ids'))

    def save(self, ids):
        with self.lock:
            ids = valid_ids(ids)
            try:
                atomic_write(self.path, {'format': FORMAT, 'ids': ids})
            except (OSError, ChannelError) as exc:
                raise PlutoFavoritesError('Nao foi possivel salvar favoritos') from exc
            return ids

    def toggle(self, ident):
        if not isinstance(ident, str) or not ID.fullmatch(ident):
            raise PlutoFavoritesError('Identificador invalido')
        with self.lock:
            ids = self.load()
            if ident in ids:
                ids.remove(ident)
            else:
                if len(ids) >= MAX_FAVORITES:
                    raise PlutoFavoritesError('Limite de favoritos atingido')
                ids.append(ident)
            return self.save(ids)
