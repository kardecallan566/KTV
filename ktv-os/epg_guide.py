"""Small on-demand XMLTV 'now/next' cache. Never infer programme titles.

Only two fixed HTTPS XMLTV sources, no redirects or user-supplied fetch URLs.
Gzip inflation and programme counts are bounded for Raspberry Pi memory.
"""
from datetime import datetime, timedelta, timezone
import gzip
import io
import re
import threading
import time
import unicodedata
from urllib.request import Request, HTTPRedirectHandler, build_opener
import xml.etree.ElementTree as ET

SOURCES = {
    'br': 'https://iptv-epg.org/files/epg-br.xml.gz',
    'pluto': 'https://i.mjh.nz/PlutoTV/br.xml.gz',
}
MAX_DOWNLOAD = 4 * 1024 * 1024
MAX_XML = 28 * 1024 * 1024
CACHE_SECONDS = 300
MAX_PROGRAMS = 70000


class EPGError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch_guide(kind):
    url = SOURCES.get(kind)
    if not url:
        raise EPGError('Fonte EPG invalida')
    opener = build_opener(NoRedirect())
    request = Request(url, headers={'User-Agent': 'KTV-OS/0.15 EPG',
                                     'Accept': 'application/gzip, application/xml'})
    try:
        with opener.open(request, timeout=9) as response:
            if response.status != 200:
                raise EPGError('Guia indisponivel')
            if int(response.headers.get('Content-Length', '0')) > MAX_DOWNLOAD:
                raise EPGError('Guia muito grande')
            raw = response.read(MAX_DOWNLOAD+1)
    except (OSError, ValueError) as exc:
        raise EPGError('Nao foi possivel baixar guia de programacao') from exc
    if len(raw) > MAX_DOWNLOAD:
        raise EPGError('Guia muito grande')
    if raw.startswith(b'\x1f\x8b'):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:
                raw = source.read(MAX_XML+1)
        except (OSError, EOFError) as exc:
            raise EPGError('Guia compactado invalido') from exc
    if len(raw) > MAX_XML or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise EPGError('Guia XML invalido ou muito grande')
    return raw


def _name(value):
    if not isinstance(value, str):
        return ''
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if c.isalnum() and not unicodedata.combining(c))[:110]


def _date(value):
    if not isinstance(value, str) or len(value) < 14 or len(value) > 26:
        return None
    try:
        if len(value) >= 20 and re.fullmatch(r'[+-]\d{4}', value[-5:]):
            return datetime.strptime(value[:14]+' '+value[-5:], '%Y%m%d%H%M%S %z').astimezone(timezone.utc)
        return datetime.strptime(value[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_xmltv(data, now=None):
    if not isinstance(data, bytes) or len(data) > MAX_XML:
        raise EPGError('XMLTV invalido')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise EPGError('Entidades XML nao permitidas')
    now = now or datetime.now(timezone.utc)
    names, programs = {}, {}
    count = 0
    try:
        for event, el in ET.iterparse(io.BytesIO(data), events=('end',)):
            if el.tag == 'channel':
                ident = el.attrib.get('id', '')[:130]
                if ident:
                    display = [x.text for x in el.findall('display-name') if x.text]
                    names[ident] = display[:5]
                el.clear()
            elif el.tag == 'programme':
                count += 1
                if count > MAX_PROGRAMS:
                    raise EPGError('Guia excede limite de programas')
                ident = el.attrib.get('channel', '')[:130]
                start = _date(el.attrib.get('start', ''))
                end = _date(el.attrib.get('stop', ''))
                if (ident and start and end and start < end and
                        end >= now and start <= now+timedelta(hours=12)):
                    title = el.findtext('title')
                    if isinstance(title,str) and title.strip():
                        item = {'title': title.strip()[:160],
                                'start': start.isoformat(), 'end': end.isoformat()}
                        programs.setdefault(ident,[]).append((start,end,item))
                el.clear()
    except (ET.ParseError, UnicodeError) as exc:
        raise EPGError('Guia XMLTV malformado') from exc
    results = {}
    for ident, entries in programs.items():
        entries.sort(key=lambda x:x[0])
        current = next((entry[2] for entry in entries if entry[0] <= now < entry[1]), None)
        future = next((entry[2] for entry in entries if entry[0] > now), None)
        result={'now':current,'next':future}
        results[_name(ident)] = result
        for label in names.get(ident,[]):
            results.setdefault(_name(label),result)
    return results


class EPGGuide:
    def __init__(self, fetcher=None, clock=None, utcnow=None):
        self.fetcher = fetcher or fetch_guide
        self.clock = clock or time.monotonic
        self.utcnow = utcnow or (lambda:datetime.now(timezone.utc))
        self.lock=threading.RLock()
        self.cache={}

    def listing(self, kind):
        if kind not in SOURCES:raise ValueError('Guia invalido')
        # Triggers a single bounded download on the first request.
        self.now_next(kind)
        with self.lock:
            entries=self.cache[kind][1]
            return {'source':kind,'programmes':dict(list(entries.items())[:800])}

    def now_next(self, kind, ident=None, name=None):
        if kind not in SOURCES:
            raise ValueError('Guia invalido')
        if (ident is not None and
                (not isinstance(ident,str) or len(ident)>130)):
            raise ValueError('ID de canal invalido')
        if (name is not None and
                (not isinstance(name,str) or len(name)>130)):
            raise ValueError('Nome de canal invalido')
        with self.lock:
            now=self.clock()
            cached=self.cache.get(kind)
            if cached is None or now-cached[0]>CACHE_SECONDS:
                xml=self.fetcher(kind)
                data=parse_xmltv(xml,self.utcnow())
                self.cache[kind]=(self.clock(),data)
            else:
                data=cached[1]
            found=(data.get(_name(ident)) if ident else None) or (data.get(_name(name)) if name else None)
            return {'available':bool(found),
                    'now':found['now'] if found else None,
                    'next':found['next'] if found else None,
                    'source':kind}
