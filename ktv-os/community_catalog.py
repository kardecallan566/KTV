"""Curated free/community IPTV feeds: read only, no arbitrary remote URLs.

The sources are third-party indexes, NOT proof that every stream is licensed or
reachable. Only explicitly reviewed HTTPS streaming origin hosts may be used.
No remote code, DRM, token extraction, or playlist proxying.
"""
import hashlib
import ipaddress
import re
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCES = (
    ('Public IPTV', 'https://raw.githubusercontent.com/freecasthub/public-iptv/main/playlist.m3u'),
    ('Free-TV', 'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8'),
)
ALLOWED_HOSTS = frozenset((
    "dwamdstream102.akamaized.net",
    "dwamdstream103.akamaized.net",
    "dwamdstream104.akamaized.net",
    "live.france24.com",
    "abcnews-streams.akamaized.net",
    "voa-ingest.akamaized.net",
    "mbn-ingest-worldsafe.akamaized.net",
    "live-hls-web-aje.getaj.net",
    "live-hls-web-aja.getaj.net",
    "nhk.lls.pbs.org",
    "abc-news-dmd-streams-1.akamaized.net",
    "mediacorp-videosbclive.akamaized.net",
    "directes-tv-int.3catdirectes.cat",
    "cdn-euronews.akamaized.net",
    "247wlive.foxweather.com",
    "streaming.meteonews.net",
    "newssimul-stream.nhk.jp",
    "canaleducacao-stream.ebc.com.br",
    "cdn-live.dltv.ac.th",
    "ebsonair.ebs.co.kr",
    "livestream.pbskids.org",
    "create.lls.pbs.org",
    "world.lls.pbs.org",
    "cloudflare.tv",
    "kan23.media.kan.org.il",
    "tv-e-okul00.medya.trt.com.tr",
    "tv-e-okul02.medya.trt.com.tr",
    "live.knou.ac.kr",
    "hls.savoir.media",
    "streaming-live.rtp.pt",
    "rtvelivestream.rtve.es",
    "mediapolis.rai.it",
    "ott-balancer.tvri.go.id",
    "rtatv.akamaized.net",
    "live3.tdm.com.mo",
    "sportsgrid-tribal.amagi.tv",
    "edgesports-sportstribal.amagi.tv",
    "mainstreammedia-worldoffreesportsintl-rakuten.amagi.tv",
    "amg01074-fueltv-fueltvemeaen-rakuten-b6j62.amagi.tv",
    "amg00405-rakutentv-cgtn-rakuten-i9tar.amagi.tv",
    "amg00106-france24-france24-samsunguk-qvpp8.amagi.tv",
    "distro001-gb-hls1-prd.delivery.skycdp.com",
    "classicarts.akamaized.net",
    "hls.weathertv.cn",
    "brlive-lh.akamaihd.net",
    "cdn4.skygo.mn",
    "shd-gcp-live.edgenextcdn.net",
    "tvbrasil-stream.ebc.com.br",
))
MAX_BYTES = 1250 * 1024
MAX_CHANNELS = 500
CACHE_SECONDS = 1800
ID_RE = re.compile(r'^[0-9a-f]{20}$')
GROUP_RE = re.compile(r'group-title="([^"]{1,65})"')


class CommunityCatalogError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def download(url):
    # URL can only be a declared source, never user-provided.
    if url not in (source for _, source in SOURCES):
        raise CommunityCatalogError('Fonte nao permitida')
    opener = build_opener(_NoRedirect())
    request = Request(url, headers={'User-Agent': 'KTV-OS/0.13 (Free-TV catalog)',
                                     'Accept': 'text/plain'})
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise CommunityCatalogError('Playlist indisponivel')
            if int(response.headers.get('Content-Length', '0')) > MAX_BYTES:
                raise CommunityCatalogError('Playlist muito grande')
            raw = response.read(MAX_BYTES + 1)
    except OSError as exc:
        raise CommunityCatalogError('Falha ao carregar catalogo comunitario') from exc
    if len(raw) > MAX_BYTES:
        raise CommunityCatalogError('Playlist muito grande')
    return raw.decode('utf-8-sig')


def _clean(value, maximum):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value.strip()


def allowed_stream(url):
    if not isinstance(url, str) or len(url) > 1700 or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname not in ALLOWED_HOSTS or
                parts.username is not None or parts.password is not None or
                parts.port not in (None, 443) or parts.fragment or
                not parts.path.lower().endswith('.m3u8')):
            return False
        # Signed sessions and personal credentials are intentionally excluded.
        query = parts.query.lower()
        if any(k in query for k in ('jwt=', 'token=', 'key=', 'password=', 'auth=')):
            return False
        return True
    except ValueError:
        return False


def parse_m3u(text, provider):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise CommunityCatalogError('Playlist invalida')
    if not text.lstrip('\ufeff').startswith('#EXTM3U'):
        raise CommunityCatalogError('Playlist sem cabecalho M3U')
    channels = {}
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            name = _clean(line.partition(',')[2], 90)
            match = GROUP_RE.search(line.partition(',')[0])
            group = _clean(match.group(1), 65) if match else 'Outros'
            pending = (name, group or 'Outros') if name else None
        elif line.startswith('#') or not line:
            continue
        else:
            if pending and allowed_stream(line):
                name, category = pending
                ident = hashlib.sha256(line.encode('utf-8')).hexdigest()[:20]
                if ident not in channels and len(channels) < MAX_CHANNELS:
                    channels[ident] = {
                        'id': ident, 'name': name, 'category': category,
                        'provider': provider, '_url': line
                    }
            pending = None
    return channels


class CommunityCatalog:
    def __init__(self, fetcher=None, clock=None):
        self.fetcher = fetcher or download
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()
        self.channels = {}
        self.updated = 0
        self.loaded = False

    def _load(self):
        with self.lock:
            now = self.clock()
            if self.loaded and now - self.updated < CACHE_SECONDS:
                return
            combined, failures = {}, 0
            for provider, url in SOURCES:
                try:
                    results = parse_m3u(self.fetcher(url), provider)
                except (CommunityCatalogError, ValueError, UnicodeError, OSError):
                    failures += 1
                    continue
                for ident, entry in results.items():
                    if ident not in combined and len(combined) < MAX_CHANNELS:
                        combined[ident] = entry
            if not combined:
                raise CommunityCatalogError('Fontes indisponiveis; tente atualizar depois')
            self.channels = combined
            self.loaded = True
            self.updated = self.clock()
            self.failures = failures

    def listing(self):
        self._load()
        with self.lock:
            return {
                'channels': [{k: v for k, v in c.items() if k != '_url'}
                             for c in self.channels.values()],
                'sources': [s[0] for s in SOURCES],
                'partial': bool(self.failures)
            }

    def play_url(self, ident):
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise ValueError('Identificador de canal invalido')
        self._load()
        with self.lock:
            channel = self.channels.get(ident)
            if not channel:
                raise ValueError('Canal nao encontrado')
            return channel['_url'], channel['name']
