"""Best-effort, on-demand reachability preflight for curated TV streams.

Reachability does NOT guarantee decoding, rights, live video, or stable playback.
Only server-reviewed public/Pluto/community channels are probed, not arbitrary
user-entered URLs, to avoid SSRF via private DNS hosts.
"""
import threading
import time
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class StreamCheck:
    def __init__(self, probe=None, clock=None):
        self.probe=probe or self._probe
        self.clock=clock or time.monotonic
        self.lock=threading.RLock()
        self.cache={}

    @staticmethod
    def _probe(url):
        opener=build_opener(NoRedirect())
        # No downloading manifests/segments: small HEAD only.
        try:
            with opener.open(Request(url, method='HEAD',
                                     headers={'User-Agent':'KTV-OS/0.15'}),
                             timeout=4) as response:
                code=response.status
        except HTTPError as exc:
            code=exc.code
        except (OSError, ValueError, URLError):
            return {'status':'unverified','message':'Não foi possível testar agora; a reprodução ainda pode funcionar.'}
        if code in (404,410):
            return {'status':'unavailable','message':'O servidor respondeu que este stream não está disponível.'}
        if code in (401,403):
            return {'status':'restricted','message':'O servidor exigiu autorização ou bloqueou a sondagem; a reprodução pode funcionar.'}
        if 200<=code<300:
            return {'status':'reachable','message':'Servidor respondeu ao teste. Imagem, áudio e estabilidade não são garantidos.'}
        return {'status':'unverified','message':'O servidor não confirmou a disponibilidade do vídeo.'}

    def check(self,kind,ident,lookup):
        if kind not in ('public','pluto','community') or not isinstance(ident,str) or len(ident)>80:
            raise ValueError('Canal desconhecido')
        key=(kind,ident)
        with self.lock:
            entry=self.cache.get(key)
            if entry and self.clock()-entry[0]<90:return entry[1]
        # lookup is a trusted server-side catalogue lookup. No client URL.
        url, _=lookup()
        outcome=self.probe(url)
        with self.lock:
            self.cache[key]=(self.clock(),outcome)
        return outcome
