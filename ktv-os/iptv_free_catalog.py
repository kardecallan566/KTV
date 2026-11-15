"""M3U playlist importer for the Windows external IPTV catalogue.

The source playlist is downloaded by the app. Stream URLs are retained only in
its private local state file and are never returned by the HTTP API/browser.
"""
from __future__ import annotations
import json
import os
import re
import tempfile
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from stream_urls import validate_stream_url, StreamURLError

BUNDLED_CATALOG_PATH = Path(__file__).with_name("iptv_free_catalog.json")
DEFAULT_STATE_DIR = Path(os.environ.get("KTV_STATE_DIR", str(Path.home() / ".config" / "ktv-os"))).expanduser()
STATE_CATALOG_PATH = DEFAULT_STATE_DIR / "iptv_free_catalog.json"
SOURCE_URL = os.environ.get("KTV_EXTERNAL_PLAYLIST_URL", "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u")
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_CHANNELS = 5000
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


class IPTVFreeCatalogError(ValueError):
    pass


def _clean_label(value):
    value = re.sub(r"\s*\[(?:M3U8|TS)\]\s*$", "", str(value or ""), flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def _channel_id(key):
    normalized = "".join(ch for ch in unicodedata.normalize("NFKD", key.lower()) if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:48] or "canal"
    value = 2166136261
    for byte in key.encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return (slug + "-" + format(value, "08x"))[:79]


def _validate_source_url(source_url):
    try:
        parts = urlsplit(source_url)
        if (parts.scheme != "https" or parts.hostname != "raw.githubusercontent.com"
                or parts.port not in (None, 443) or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValueError
    except (TypeError, ValueError):
        raise IPTVFreeCatalogError("A fonte deve ser HTTPS no raw.githubusercontent.com")
    return source_url


def parse_m3u_playlist(content):
    """Parse EXTINF records and pair each channel with its following media URL."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise IPTVFreeCatalogError("Arquivo M3U invalido ou maior que 8 MB")
    lines = content.lstrip("\ufeff").splitlines()
    channels = {}
    pending = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            header, separator, display_name = line.partition(",")
            attrs = dict(ATTR_RE.findall(header))
            name = _clean_label(display_name if separator else attrs.get("tvg-name", ""))
            if not name:
                pending = None
                continue
            category = _clean_label(attrs.get("group-title", "Outros")) or "Outros"
            tvg_id = attrs.get("tvg-id", "").strip()
            key = (tvg_id.lower() + "|" + name.lower()) if tvg_id else name.lower()
            item = channels.get(key)
            if item is None:
                item = {"id": _channel_id(key), "name": name[:100],
                        "category": category[:60], "categories": [],
                        "tvg_id": tvg_id[:160] or None, "logo": None, "streams": []}
                channels[key] = item
            if category[:60] not in item["categories"]:
                item["categories"].append(category[:60])
            logo = attrs.get("tvg-logo", "").strip()
            if item["logo"] is None and logo:
                try:
                    parts = urlsplit(logo)
                    if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password and len(logo) <= 1200:
                        item["logo"] = logo
                except ValueError:
                    pass
            pending = item
            if len(channels) > MAX_CHANNELS:
                raise IPTVFreeCatalogError("A playlist excede 5.000 canais")
            continue
        if line.startswith("#"):
            continue
        if pending is None:
            continue
        try:
            stream_url = validate_stream_url(line)
        except StreamURLError:
            pending = None
            continue
        path = urlsplit(stream_url).path.lower()
        stream_format = "hls" if path.endswith(".m3u8") else "ts" if path.endswith(".ts") else path.rsplit(".", 1)[-1]
        if not any(entry["url"] == stream_url for entry in pending["streams"]):
            pending["streams"].append({"format": stream_format, "url": stream_url})
        pending = None

    result = []
    for item in channels.values():
        item["streams"].sort(key=lambda entry: (entry["format"] != "hls", entry["format"]))
        item["playable"] = bool(item["streams"])
        result.append(item)
    return sorted(result, key=lambda item: (item["category"].casefold(), item["name"].casefold()))


def parse_m3u_metadata(content):
    """Compatibility helper returning only public metadata, never stream URLs."""
    result = []
    for item in parse_m3u_playlist(content):
        result.append({key: item[key] for key in ("id", "name", "category", "categories", "tvg_id", "playable")})
    return result


def load_catalog(path=None):
    target = Path(path) if path is not None else (STATE_CATALOG_PATH if STATE_CATALOG_PATH.is_file() else BUNDLED_CATALOG_PATH)
    if path is not None and not target.is_file():
        target = BUNDLED_CATALOG_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IPTVFreeCatalogError("Catalogo IPTV indisponivel ou invalido") from exc
    if not isinstance(data, dict) or data.get("schema") not in ("ktv-iptv-metadata-v2", "ktv-iptv-playlist-v3"):
        raise IPTVFreeCatalogError("Formato do catalogo IPTV incompativel")
    raw = data.get("channels")
    if not isinstance(raw, list) or len(raw) > MAX_CHANNELS:
        raise IPTVFreeCatalogError("Catalogo IPTV excede o limite")
    result, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        ident, name, category = item.get("id"), item.get("name"), item.get("category")
        categories = item.get("categories", [category])
        if (not isinstance(ident, str) or not ID_RE.fullmatch(ident) or ident in seen
                or not isinstance(name, str) or not 1 <= len(name.strip()) <= 100
                or not isinstance(category, str) or not 1 <= len(category.strip()) <= 60
                or not isinstance(categories, list) or not categories
                or any(not isinstance(v, str) or not v.strip() or len(v) > 60 for v in categories)):
            continue
        streams = []
        if data.get("schema") == "ktv-iptv-playlist-v3":
            for stream in item.get("streams", []) if isinstance(item.get("streams"), list) else []:
                if not isinstance(stream, dict) or not isinstance(stream.get("url"), str):
                    continue
                try:
                    url = validate_stream_url(stream["url"])
                except StreamURLError:
                    continue
                fmt = stream.get("format")
                if fmt not in ("hls", "ts", "mpd", "mp4", "m4v", "webm", "flv"):
                    continue
                streams.append({"format": fmt, "url": url})
        logo = item.get("logo")
        if not isinstance(logo, str) or len(logo) > 1200:
            logo = None
        else:
            try:
                parts = urlsplit(logo)
                if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
                    logo = None
            except ValueError:
                logo = None
        tvg_id = item.get("tvg_id")
        if tvg_id is not None and (not isinstance(tvg_id, str) or len(tvg_id) > 160):
            tvg_id = None
        seen.add(ident)
        result.append({"id": ident, "name": name.strip(), "category": category.strip(),
                       "categories": list(dict.fromkeys(categories)), "tvg_id": tvg_id,
                       "logo": logo, "streams": streams, "playable": bool(streams)})
    return result


def refresh_catalog(path=None, source_url=None):
    """Download the configured playlist and atomically replace the private local catalogue."""
    source_url = _validate_source_url(source_url or SOURCE_URL)
    request = Request(source_url, headers={"User-Agent": "KTV-Windows-Playlist/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            final_url = _validate_source_url(response.geturl())
            if urlsplit(final_url).hostname != urlsplit(source_url).hostname:
                raise IPTVFreeCatalogError("Redirecionamento de fonte nao permitido")
            payload = response.read(MAX_SOURCE_BYTES + 1)
        if len(payload) > MAX_SOURCE_BYTES:
            raise IPTVFreeCatalogError("Arquivo M3U excede 8 MB")
        content = payload.decode("utf-8-sig")
    except IPTVFreeCatalogError:
        raise
    except Exception as exc:
        raise IPTVFreeCatalogError("Nao foi possivel atualizar a playlist M3U") from exc
    channels = parse_m3u_playlist(content)
    if not channels or not any(item["streams"] for item in channels):
        raise IPTVFreeCatalogError("A fonte M3U nao contem canais com transmissoes validas")
    target = Path(path) if path is not None else STATE_CATALOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": "ktv-iptv-playlist-v3", "source": "GitHub M3U",
            "updated_at": int(time.time()), "channels": channels}
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                         prefix=".iptv-playlist-", delete=False) as handle:
            temp_name = handle.name
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        raise IPTVFreeCatalogError("Nao foi possivel salvar a playlist atualizada") from exc
    return load_catalog(target)


def validated_catalog(path=None):
    return load_catalog(path)


def iptv_free_channel(identifier, path=None):
    if not isinstance(identifier, str):
        return None
    return next((item for item in load_catalog(path) if item["id"] == identifier), None)
