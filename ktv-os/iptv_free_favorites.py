"""Persistent favorites for the separately sourced IPTV Free catalog."""
from __future__ import annotations
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

MAX_FAVORITES = 155
ID_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


class IPTVFreeFavoritesError(ValueError):
    pass


class IPTVFreeFavorites:
    def __init__(self, state_dir):
        self.path = Path(state_dir) / "iptv_free_favorites.json"

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IPTVFreeFavoritesError("Favoritos IPTV externos invalidos") from exc
        ids = data.get("ids") if isinstance(data, dict) else None
        if not isinstance(ids, list) or len(ids) > MAX_FAVORITES:
            raise IPTVFreeFavoritesError("Formato de favoritos IPTV externo invalido")
        clean, seen = [], set()
        for ident in ids:
            if isinstance(ident, str) and ID_RE.fullmatch(ident) and ident not in seen:
                clean.append(ident); seen.add(ident)
        return clean

    def toggle(self, ident):
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise IPTVFreeFavoritesError("Identificador de canal invalido")
        ids = self.load()
        if ident in ids:
            ids.remove(ident)
        else:
            if len(ids) >= MAX_FAVORITES:
                raise IPTVFreeFavoritesError("Limite de favoritos atingido")
            ids.append(ident)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                   prefix=".iptv-fav-", delete=False) as handle:
                temp = handle.name
                json.dump({"schema":"ktv-iptv-favorites-v1","ids":ids}, handle)
                handle.write("\n")
            os.replace(temp, self.path)
        except OSError as exc:
            if temp:
                try: os.unlink(temp)
                except OSError: pass
            raise IPTVFreeFavoritesError("Nao foi possivel salvar favoritos IPTV") from exc
        return ids
