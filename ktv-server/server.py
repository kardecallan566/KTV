#!/usr/bin/env python3
"""KTV Server: entrega canais IPTV HLS ao aplicativo Samsung KTV Orsay."""
import argparse
import json
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

VERSION = "0.2.0"
DEFAULT_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u"
FALLBACK_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/e0aee5e6649fd227fd5fc250249e5a222240d510/main.m3u"
MIN_CHANNELS = 100
REFRESH_SECONDS = 300


def parse_m3u(content, base_url=DEFAULT_PLAYLIST, hls_only=True):
    channels = []
    meta = None
    for raw in content.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            attrs = dict((k.lower(), v) for k, v in re.findall(r'([\w-]+)="([^"]*)"', line))
            name = line.rsplit(",", 1)[-1].strip() if "," in line else attrs.get("tvg-name", "Canal")
            meta = {"name": name or attrs.get("tvg-name", "Canal"),
                    "category": attrs.get("group-title", "Outros"),
                    "logo": attrs.get("tvg-logo", ""),
                    "tvg_id": attrs.get("tvg-id", "")}
        elif not line.startswith("#") and meta:
            url = urljoin(base_url, line)
            path = urlsplit(url).path.lower()
            if not (url.startswith("http://") or url.startswith("https://")):
                meta = None
                continue
            if hls_only and not (".m3u8" in path or "m3u8" in url.lower()):
                meta = None
                continue
            channel = dict(meta)
            channel.update({"type": "hls", "url": url, "duration": 0})
            channels.append(channel)
            meta = None
    # URLs repetidas são removidas sem alterar a ordem da playlist.
    seen = set()
    unique = []
    for item in channels:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def download_playlist(url):
    request = Request(url, headers={"User-Agent": "KTV-Server/{}".format(VERSION),
                                    "Accept": "application/x-mpegURL,audio/x-mpegurl,*/*"})
    with urlopen(request, timeout=25) as response:
        data = response.read(25 * 1024 * 1024 + 1)
    if len(data) > 25 * 1024 * 1024:
        raise ValueError("Playlist excede 25 MB")
    return data.decode("utf-8-sig", errors="replace")


class KTVServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, playlist_url, fallback_url):
        super().__init__(address, Handler)
        self.playlist_url = playlist_url
        self.fallback_url = fallback_url
        self.lock = threading.RLock()
        self.channels = []
        self.version = 1
        self.last_refresh = 0
        self.last_error = ""
        self.source = ""
        self.clients = {}
        self.events = {}
        self.refresh_playlist()
        self.refresh_thread = threading.Thread(target=self.refresh_loop, daemon=True)
        self.refresh_thread.start()

    def refresh_playlist(self):
        errors = []
        candidates = [(self.playlist_url, "principal")]
        if self.fallback_url:
            candidates.append((self.fallback_url, "reserva"))
        best_channels = []
        best_source = ""
        for url, label in candidates:
            try:
                content = download_playlist(url)
                channels = parse_m3u(content, base_url=url)
                if len(channels) > len(best_channels):
                    best_channels, best_source = channels, url
                if label == "principal" and len(channels) >= MIN_CHANNELS:
                    break
            except Exception as exc:
                errors.append("{}: {}".format(label, exc))
        if not best_channels:
            message = "; ".join(errors) or "Nenhum canal HLS válido encontrado"
            with self.lock:
                self.last_error = message
                self.last_refresh = time.time()
            print("[KTV] Falha ao carregar playlists: {}".format(message), flush=True)
            return False
        with self.lock:
            if [x["url"] for x in best_channels] != [x["url"] for x in self.channels]:
                self.channels = best_channels
                self.version += 1
            self.source = best_source
            self.last_refresh = time.time()
            self.last_error = "; ".join(errors)
        print("[KTV] Playlist carregada: {} canais HLS".format(len(best_channels)), flush=True)
        return True

    def refresh_loop(self):
        while True:
            time.sleep(REFRESH_SECONDS)
            self.refresh_playlist()


class Handler(BaseHTTPRequestHandler):
    server_version = "KTV-IPTV/{}".format(VERSION)

    def log_message(self, fmt, *args):
        print("[KTV] " + (fmt % args), flush=True)

    def respond(self, status, body, mime="application/json; charset=utf-8"):
        encoded = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json(self, status, data):
        return self.respond(status, json.dumps(data, ensure_ascii=False))

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/api/health":
            with self.server.lock:
                return self.json(200, {"app": "KTV Server IPTV", "version": VERSION,
                    "status": "ok", "channels": len(self.server.channels),
                    "source": self.server.source, "last_error": self.server.last_error})
        if path == "/api/state":
            from urllib.parse import parse_qs
            client = parse_qs(parsed.query).get("client", ["samsung"])[0][:40]
            with self.server.lock:
                self.server.clients[client] = {"ip": self.client_address[0], "seen": time.time()}
                channels = [dict(item) for item in self.server.channels]
                version = self.server.version
            return self.json(200, {"version": version, "items": channels, "index": 0, "playing": True})
        if path == "/api/channels":
            with self.server.lock:
                return self.json(200, {"count": len(self.server.channels), "items": self.server.channels})
        if path == "/playlist.m3u":
            with self.server.lock:
                items = list(self.server.channels)
            lines = ["#EXTM3U"]
            for item in items:
                attrs = ' tvg-logo="{}" group-title="{}"'.format(
                    item["logo"].replace('"', ""), item["category"].replace('"', ""))
                lines.append("#EXTINF:-1{} ,{}".format(attrs, item["name"].replace(",", " ")))
                lines.append(item["url"])
            return self.respond(200, "\n".join(lines) + "\n", "audio/x-mpegurl; charset=utf-8")
        if path == "/api/event":
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)
            client = params.get("client", ["samsung"])[0][:40]
            event = params.get("event", ["unknown"])[0][:80]
            self.server.events[client] = {"event": event, "ip": self.client_address[0], "seen": time.time()}
            return self.json(200, {"ok": True})
        return self.json(404, {"error": "Rota não encontrada"})


def main():
    parser = argparse.ArgumentParser(description="Servidor IPTV HLS para Samsung KTV Orsay")
    parser.add_argument("--host", default="0.0.0.0", help="Interface de rede")
    parser.add_argument("--port", type=int, default=80, help="Porta HTTP (padrão 80)")
    parser.add_argument("--ip", default="", help="IP do computador exibido para configurar na TV")
    parser.add_argument("--playlist", default=DEFAULT_PLAYLIST, help="URL da playlist M3U")
    parser.add_argument("--no-fallback", action="store_true", help="Desativa playlist reserva")
    args = parser.parse_args()
    ip = args.ip
    if not ip:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 80))
            ip = probe.getsockname()[0]
        except OSError:
            ip = "127.0.0.1"
        finally:
            probe.close()
    fallback = "" if args.no_fallback else FALLBACK_PLAYLIST
    server = KTVServer((args.host, args.port), args.playlist, fallback)
    print("\n=== KTV SERVER IPTV v{} ===".format(VERSION))
    print("Servidor:      http://{}:{}/".format(ip, args.port))
    print("API Samsung:   http://{}:{}/api/state".format(ip, args.port))
    print("Playlist M3U:  http://{}:{}/playlist.m3u".format(ip, args.port))
    print("Canais HLS:    {}".format(len(server.channels)))
    print("Origem:        {}".format(server.source or args.playlist))
    print("Configure o endereço base do servidor no KTV instalado na Samsung.")
    print("TV e computador devem estar na mesma rede. CTRL+C encerra.\n", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nEncerrando KTV Server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
