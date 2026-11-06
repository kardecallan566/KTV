"""Snapshot loader for the external IPTV playlist supplied by the project owner.

The catalog is kept separate from personal channels and existing public sources.
No source URL is fetched at boot; all entries are versioned in JSON.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from stream_urls import StreamURLError, validate_stream_url

CATALOG_PATH = Path(__file__).with_name("iptv_free_catalog.json")
SOURCE_URL = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u"
STREAM_HOSTS = frozenset({
    "d1-ywppjexvlyulasvmgzjdftfjikth2210oq80soveui6lkbi2iza2zf.cdn10embed.xyz",
    "d2-ywppjexvlyulasvmgzjdftfjikth2210oq80soveui6lkbi2iza2zf.cdn10embed.xyz",
    "d3-ywppjexvlyulasvmgzjdftfjikth2210oq80soveui6lkbi2iza2zf.cdn10embed.xyz",
})
LOGO_HOSTS = frozenset({"1.embedcanaisdetv.com", "vipcanais.net"})
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
REFERRER = "https://embedcanaisdetv.xyz/"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


class IPTVFreeCatalogError(ValueError):
    pass


def _valid_logo(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.hostname not in LOGO_HOSTS or parts.port not in (None, 443):
            return None
    except ValueError:
        return None
    return value


def load_catalog(path=CATALOG_PATH):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IPTVFreeCatalogError("Catalogo IPTV externo indisponivel ou invalido") from exc
    if not isinstance(data, dict) or data.get("schema") != "ktv-iptv-source-v1":
        raise IPTVFreeCatalogError("Formato do catalogo IPTV externo incompativel")
    raw = data.get("channels")
    if not isinstance(raw, list) or len(raw) > 250:
        raise IPTVFreeCatalogError("Catalogo IPTV externo excede o limite")
    result, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        ident, name, category, url = item.get("id"), item.get("name"), item.get("category"), item.get("url")
        if (not isinstance(ident, str) or not ID_RE.fullmatch(ident) or ident in seen or
                not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or
                not isinstance(category, str) or not 1 <= len(category.strip()) <= 50):
            continue
        try:
            validate_stream_url(url)
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in STREAM_HOSTS or not parts.path.endswith(".m3u8"):
                continue
        except (StreamURLError, ValueError):
            continue
        # Only the two fixed request headers from this exact source are accepted.
        user_agent = item.get("user_agent")
        referrer = item.get("referrer")
        if user_agent != USER_AGENT or referrer != REFERRER:
            user_agent, referrer = None, None
        seen.add(ident)
        result.append({
            "id": ident,
            "name": name.strip(),
            "category": category.strip(),
            "logo": _valid_logo(item.get("logo")),
            "url": url,
            "user_agent": user_agent,
            "referrer": referrer,
            "source": SOURCE_URL,
        })
    return result


def validated_catalog():
    return load_catalog()


def iptv_free_channel(identifier):
    if not isinstance(identifier, str):
        return None
    return next((channel for channel in load_catalog() if channel["id"] == identifier), None)
