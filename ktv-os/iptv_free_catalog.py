"""Metadata-only M3U catalog for the Windows external-playlist section.

Only EXTINF metadata is retained. Stream URI lines, logo URLs and request headers
are intentionally discarded and are never passed to the player.
"""
from __future__ import annotations
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CATALOG_PATH = Path(__file__).with_name("iptv_free_catalog.json")
# M3U document URL only; channel playback URLs are never stored.
SOURCE_URL = os.environ.get("KTV_EXTERNAL_PLAYLIST_METADATA_URL", "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u")
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


def parse_m3u_metadata(content):
    """Extract channel labels and groups only; never retain a stream URI."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise IPTVFreeCatalogError("Arquivo M3U invalido ou maior que 8 MB")
    channels = {}
    for line in content.splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        header, separator, display_name = line.partition(",")
        attrs = dict(ATTR_RE.findall(header))
        name = _clean_label(display_name if separator else attrs.get("tvg-name", ""))
        if not name:
            continue
        category = _clean_label(attrs.get("group-title", "Outros")) or "Outros"
        tvg_id = attrs.get("tvg-id", "").strip()
        key = tvg_id.lower() if tvg_id else name.lower()
        item = channels.get(key)
        if item is None:
            item = {"id": _channel_id(key), "name": name[:100], "category": category[:60],
                    "categories": [], "tvg_id": tvg_id[:160] or None, "playable": False}
            channels[key] = item
        if category[:60] not in item["categories"]:
            item["categories"].append(category[:60])
        if len(channels) > MAX_CHANNELS:
            raise IPTVFreeCatalogError("A playlist excede 5.000 canais")
    return sorted(channels.values(), key=lambda item: (item["category"].casefold(), item["name"].casefold()))


def _validate_source_url(source_url):
    try:
        parts = urlsplit(source_url)
        if (parts.scheme != "https" or parts.hostname != "raw.githubusercontent.com"
                or parts.port not in (None, 443) or parts.username or parts.password):
            raise ValueError
    except (TypeError, ValueError):
        raise IPTVFreeCatalogError("A fonte deve ser HTTPS no raw.githubusercontent.com")
    return source_url


def load_catalog(path=CATALOG_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IPTVFreeCatalogError("Catalogo de metadados IPTV indisponivel ou invalido") from exc
    if not isinstance(data, dict) or data.get("schema") != "ktv-iptv-metadata-v2" or data.get("playback_urls_included") is not False:
        raise IPTVFreeCatalogError("Formato do catalogo de metadados incompativel")
    raw = data.get("channels")
    if not isinstance(raw, list) or len(raw) > MAX_CHANNELS:
        raise IPTVFreeCatalogError("Catalogo de metadados excede o limite")
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
        tvg_id = item.get("tvg_id")
        if tvg_id is not None and (not isinstance(tvg_id, str) or len(tvg_id) > 160):
            tvg_id = None
        # Allowlist response fields: URLs, logos, credentials and headers are discarded.
        seen.add(ident)
        result.append({"id": ident, "name": name.strip(), "category": category.strip(),
                       "categories": list(dict.fromkeys(categories)), "tvg_id": tvg_id,
                       "playable": False})
    return result


def refresh_catalog(path=CATALOG_PATH, source_url=None):
    """Fetch an M3U document and atomically store only its EXTINF metadata."""
    source_url = _validate_source_url(source_url or SOURCE_URL)
    request = Request(source_url, headers={"User-Agent": "KTV-OS-Metadata-Importer/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
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
        raise IPTVFreeCatalogError("Nao foi possivel atualizar os metadados da playlist") from exc
    channels = parse_m3u_metadata(content)
    if not channels:
        raise IPTVFreeCatalogError("A fonte M3U nao contem canais validos")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": "ktv-iptv-metadata-v2", "generated_from": "M3U metadata only",
            "playback_urls_included": False, "channels": channels}
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                         prefix=".iptv-metadata-", delete=False) as handle:
            temp_name = handle.name
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name:
            try: os.unlink(temp_name)
            except OSError: pass
        raise IPTVFreeCatalogError("Nao foi possivel salvar o catalogo atualizado") from exc
    return load_catalog(target)


def validated_catalog():
    return load_catalog()


def iptv_free_channel(identifier):
    if not isinstance(identifier, str):
        return None
    return next((item for item in load_catalog() if item["id"] == identifier), None)
