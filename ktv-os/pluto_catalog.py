"""Read-only, on-demand Pluto TV catalog from the user's community M3U source.

Never embed expiring playback JWTs in source code, browser responses or logs.
Only direct, HTTPS Pluto TV channel-master links are eligible for playback.
No playlist proxies, transcoding, DRM workarounds or background polling.
"""
import re
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCE_URL = 'https://raw.githubusercontent.com/BuddyChewChew/pluto/refs/heads/main/pluto_br.m3u'
MAX_BYTES = 2 * 1024 * 1024
MAX_CHANNELS = 400
CACHE_SECONDS = 300
CHANNEL_ID = re.compile(r'^[a-f0-9]{24}$')
STREAM_PATH = re.compile(
    r'^/api/tn/video/playout/v2/stitch/hls/channel/([a-f0-9]{24})/master\.m3u8$'
)
GROUP = re.compile(r'group-title="([^"]{1,96})"')


class PlutoError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _download():
    # Fixed HTTPS URL and no redirects: untrusted M3U never controls the fetch.
    req = Request(SOURCE_URL, headers={'User-Agent': 'KTV-OS/0.9 (M3U catalog reader)',
                                       'Accept': 'text/plain'})
    opener = build_opener(_NoRedirect())
    with opener.open(req, timeout=8) as response:
        if response.status != 200:
            raise PlutoError('Fonte de canais indisponivel')
        if int(response.headers.get('Content-Length', '0')) > MAX_BYTES:
            raise PlutoError('Playlist maior que o limite permitido')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PlutoError('Playlist maior que o limite permitido')
        return raw.decode('utf-8-sig')


def _safe_label(value, limit):
    return (value if isinstance(value, str) and
            0 < len(value.strip()) <= limit and
            all(32 <= ord(char) != 127 for char in value) else None)


def _stream_id(url):
    if not isinstance(url, str) or len(url) > 6000 or any(char.isspace() for char in url):
        return None
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname != 'ipv4.pluto.tv' or
                parts.username is not None or parts.password is not None or
                parts.port not in (None, 443) or parts.fragment):
            return None
        match = STREAM_PATH.fullmatch(parts.path)
        if not match or not parts.query or 'jwt=' not in parts.query:
            return None
        return match.group(1)
    except ValueError:
        return None


def parse_playlist(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise PlutoError('Playlist invalida ou muito grande')
    if not text.lstrip('\ufeff').startswith('#EXTM3U'):
        raise PlutoError('Formato M3U invalido')
    channels = {}
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            name = _safe_label(line.rsplit(',', 1)[-1], 96)
            group_match = GROUP.search(line)
            group = _safe_label(group_match.group(1), 96) if group_match else None
            pending = (name.strip(), group.strip() if group else 'Outros') if name else None
        elif line.startswith('#') or not line:
            continue
        else:
            if pending:
                ident = _stream_id(line)
                if ident and ident not in channels and len(channels) < MAX_CHANNELS:
                    name, category = pending
                    channels[ident] = {
                        'id': ident, 'name': name, 'category': category,
                        'provider': 'Pluto TV', 'source': 'Lista comunitaria BuddyChewChew',
                        '_stream_url': line
                    }
            pending = None
    if not channels:
        raise PlutoError('Nenhum canal Pluto TV valido na lista')
    return channels


class PlutoCatalog:
    def __init__(self, fetcher=None, clock=None):
        self.fetcher = fetcher or _download
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()
        self.channels = {}
        self.updated = 0
        self.loaded = False

    def _load(self, force_refresh=False):
        with self.lock:
            now = self.clock()
            if not force_refresh and self.loaded and now - self.updated < CACHE_SECONDS:
                return
            try:
                channels = parse_playlist(self.fetcher())
            except (OSError, ValueError, UnicodeError, PlutoError) as exc:
                # Do not fall back to potentially expired access credentials.
                raise PlutoError('Nao foi possivel atualizar a lista Pluto TV') from exc
            self.channels = channels
            self.updated = self.clock()
            self.loaded = True

    def listing(self):
        self._load()
        with self.lock:
            return [
                {k: v for k, v in channel.items() if not k.startswith('_')}
                for channel in self.channels.values()
            ]

    def play_url(self, ident, force_refresh=False):
        if not isinstance(ident, str) or not CHANNEL_ID.fullmatch(ident):
            raise ValueError('Canal Pluto TV invalido')
        self._load(force_refresh=force_refresh)
        with self.lock:
            channel = self.channels.get(ident)
            if not channel:
                raise ValueError('Canal Pluto TV nao encontrado')
            # Raw signed link remains server-side, never included in API JSON.
            return channel['_stream_url'], channel['name']
