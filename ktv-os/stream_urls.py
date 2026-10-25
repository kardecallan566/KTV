"""Validate manually supplied direct media URLs before saving or playback.

No DNS requests or fetching during validation. Defense against common local
network URLs is best-effort: DNS and redirects can still change destination.
The HTTP server is loopback-only and a user action is required to add a link.
"""
import ipaddress
import re
from urllib.parse import urlsplit

# HLS, MPEG-DASH, transport streams and conventional direct media files.
DIRECT_EXTENSIONS = ('.m3u8', '.mpd', '.ts', '.mp4', '.m4v', '.webm', '.flv')
MAX_URL_LENGTH = 1800
ALLOWED_PORTS = frozenset((80, 443, 8080, 8443))
DENIED_SUFFIXES = ('.localhost', '.local', '.lan', '.internal', '.home',
                   '.home.arpa', '.arpa', '.onion', '.invalid', '.test')
HOST_RE = re.compile(r'^[a-z0-9-]+(?:\.[a-z0-9-]+)+$')


class StreamURLError(ValueError):
    pass


def validate_stream_url(url):
    if (not isinstance(url, str) or not 1 <= len(url) <= MAX_URL_LENGTH
            or any(ord(char) <= 32 or ord(char) == 127 for char in url)):
        raise StreamURLError('Endereco de transmissao invalido')
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if (parts.scheme not in ('http', 'https') or not host or
                parts.username is not None or parts.password is not None or
                parts.fragment or parts.port not in (None, *ALLOWED_PORTS)):
            raise StreamURLError('Use URL HTTP(S) direta em porta web autorizada')
        if not parts.path.lower().endswith(DIRECT_EXTENSIONS):
            raise StreamURLError('Formatos aceitos: HLS .m3u8, DASH .mpd, TS .ts, MP4, M4V, WebM e FLV')
        host = host.lower()
        if host == 'localhost' or any(host.endswith(s) for s in DENIED_SUFFIXES):
            raise StreamURLError('Transmissoes para redes locais nao permitidas')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # Reject single-label names, odd numeric IPv4 forms, DNS injection
            # labels and disguised hosts (including percent encoded hosts).
            if not HOST_RE.fullmatch(host) or host.rsplit('.', 1)[-1].isdigit():
                raise StreamURLError('Dominio de transmissao invalido')
        else:
            if not address.is_global:
                raise StreamURLError('Endereco IP privado/reservado nao permitido')
    except ValueError as exc:
        if isinstance(exc, StreamURLError):
            raise
        raise StreamURLError('Endereco de transmissao invalido') from exc
    return url
