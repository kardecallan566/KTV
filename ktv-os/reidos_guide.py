"""Read-only, bounded EPG discovery from the public Rei dos Canais API.

Never ingest third-party embeds, signed URLs, logos, scripts, or paid-TV streams.
Only recognized free-to-air broadcaster metadata can enter KTV. Playback uses
existing verified KTV channel IDs or a local ISDB-Tb tuner, never source URLs.
"""
import json
import re
import threading
import time
import unicodedata
from urllib.request import Request, HTTPRedirectHandler, build_opener

SOURCE_URL = 'https://api.reidoscanais.cam/channels'
CACHE_SECONDS = 300
MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 400

# Deliberately small set: not evidence of rights to distribute their web video.
# 'play_id' is an existing, independently curated KTV stream, not an embed URL.
BROADCASTERS = {
    'band': ('Band', None),
    'globo': ('Globo', None),
    'record': ('Record', None),
    'redetv': ('RedeTV!', None),
    'sbt': ('SBT', None),
    'tv aparecida': ('TV Aparecida', None),
    'tv brasil': ('TV Brasil', 'tv-brasil'),
    'tv cultura': ('TV Cultura', 'tv-cultura'),
}
# Alternative wording must still map to an explicit free-to-air identity.
ALIASES = {'tv globo': 'globo', 'globo sp': 'globo', 'globo rj': 'globo',
           'record tv': 'record', 'rede tv': 'redetv',
           'tv aparecida hd': 'tv aparecida',
           'tv brasil hd': 'tv brasil', 'tv cultura hd': 'tv cultura'}


class DiscoveryError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def download():
    request = Request(SOURCE_URL, headers={
        'Accept': 'application/json', 'User-Agent': 'KTV-OS/0.20 public-EPG'
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=7) as response:
            if response.status != 200:
                raise DiscoveryError('Fonte de programação indisponível')
            if int(response.headers.get('Content-Length', '0')) > MAX_BYTES:
                raise DiscoveryError('Resposta muito grande')
            raw = response.read(MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise DiscoveryError('Não foi possível acessar a API pública') from exc
    if len(raw) > MAX_BYTES:
        raise DiscoveryError('Resposta muito grande')
    return raw


def normalize(text):
    if not isinstance(text, str):
        return ''
    text = unicodedata.normalize('NFKD', text.casefold())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(
        char for char in text if not unicodedata.combining(char))).strip()[:90]


def safe_title(text):
    if (not isinstance(text, str) or not 1 <= len(text.strip()) <= 120
            or any(ord(c) < 32 or ord(c) == 127 for c in text)):
        return None
    return text.strip()


def _show_program(value, now, future=False):
    if not isinstance(value, dict):
        return None
    title = safe_title(value.get('title'))
    start = value.get('start_time')
    end = value.get('end_time')
    if not title or type(start) is not int or type(end) is not int:
        return None
    if not (1600000000 <= start < end <= 2200000000):
        return None
    if future:
        if not now <= start <= now + 36*3600:
            return None
    elif not start <= now < end:
        return None
    return {'title': title, 'start': start, 'end': end}


def parse_response(raw, now=None):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise DiscoveryError('Formato inválido')
    now = int(time.time()) if now is None else int(now)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise DiscoveryError('JSON de programação inválido') from exc
    if not isinstance(payload, dict) or payload.get('success') is not True:
        raise DiscoveryError('API não confirmou a lista')
    data = payload.get('data')
    if not isinstance(data, list) or len(data) > MAX_ENTRIES:
        raise DiscoveryError('Lista de canais inválida')
    result = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        ident = normalize(entry.get('name'))
        ident = ALIASES.get(ident, ident)
        if ident not in BROADCASTERS or ident in result:
            continue
        # No trusting category/embeds. Never read or return unverified URLs.
        title, play_id = BROADCASTERS[ident]
        epg = entry.get('epg')
        epg = epg if isinstance(epg, dict) else {}
        result[ident] = {
            'id': ident.replace(' ', '-'),
            'name': title,
            'play_id': play_id,
            'now': _show_program(epg.get('current'), now),
            'next': _show_program(epg.get('next'), now, future=True)
        }
    return list(result.values())


class ReiGuide:
    def __init__(self, fetcher=None, clock=None, unix_time=None):
        self.fetcher = fetcher or download
        self.clock = clock or time.monotonic
        self.unix_time = unix_time or time.time
        self.lock = threading.RLock()
        self.data = None
        self.updated = 0

    def listing(self):
        with self.lock:
            current = self.clock()
            if self.data is None or current - self.updated >= CACHE_SECONDS:
                records = parse_response(self.fetcher(), now=int(self.unix_time()))
                self.data = records
                self.updated = self.clock()
            return {
                'channels': list(self.data),
                'source': 'Rei dos Canais · dados públicos (não streams)',
                'playback_policy': 'verified_ktv_only'
            }
