#!/usr/bin/env python3
"""KTV Server: prepara IPTV para Samsung Orsay usando FFmpeg no computador."""
import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

VERSION = "0.3.1"
DEFAULT_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u"
FALLBACK_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/e0aee5e6649fd227fd5fc250249e5a222240d510/main.m3u"
MIN_CHANNELS = 100
REFRESH_SECONDS = 300
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HLS_CACHE = DATA / "hls"


def parse_m3u(content, base_url=DEFAULT_PLAYLIST):
    channels, meta = [], None
    for raw in content.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            attrs = dict((k.lower(), v) for k, v in re.findall(r'([\w-]+)="([^"]*)"', line))
            name = line.rsplit(",", 1)[-1].strip() if "," in line else attrs.get("tvg-name", "Canal")
            meta = {"name": name or attrs.get("tvg-name", "Canal"),
                    "category": attrs.get("group-title", "Outros"),
                    "logo": attrs.get("tvg-logo", ""), "tvg_id": attrs.get("tvg-id", "")}
        elif not line.startswith("#") and meta:
            url = urljoin(base_url, line)
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not (".m3u8" in parsed.path.lower() or "m3u8" in url.lower()):
                meta = None
                continue
            item = dict(meta)
            item.update({"type": "hls", "source_url": url, "duration": 0})
            item["id"] = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            channels.append(item)
            meta = None
    seen, unique = set(), []
    for item in channels:
        if item["source_url"] not in seen:
            seen.add(item["source_url"])
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

    def __init__(self, address, base_url, playlist_url, fallback_url, ffmpeg, mode):
        super().__init__(address, Handler)
        self.base_url = base_url.rstrip("/")
        self.playlist_url, self.fallback_url = playlist_url, fallback_url
        self.ffmpeg, self.mode = ffmpeg, mode
        self.transcode = bool(ffmpeg) and mode != "direct"
        self.lock = threading.RLock()
        self.channels, self.version = [], 1
        self.last_refresh, self.last_error, self.source = 0, "", ""
        self.processes = {}
        DATA.mkdir(parents=True, exist_ok=True)
        HLS_CACHE.mkdir(parents=True, exist_ok=True)
        self.refresh_playlist()
        self.refresh_thread = threading.Thread(target=self.refresh_loop, daemon=True)
        self.refresh_thread.start()

    def refresh_playlist(self):
        errors, best, source = [], [], ""
        candidates = [(self.playlist_url, "principal")]
        if self.fallback_url:
            candidates.append((self.fallback_url, "reserva"))
        for url, label in candidates:
            try:
                items = parse_m3u(download_playlist(url), base_url=url)
                if len(items) > len(best):
                    best, source = items, url
                if label == "principal" and len(items) >= MIN_CHANNELS:
                    break
            except Exception as exc:
                errors.append("{}: {}".format(label, exc))
        if not best:
            with self.lock:
                self.last_error = "; ".join(errors) or "Nenhum canal HLS válido encontrado"
                self.last_refresh = time.time()
            print("[KTV] Falha ao carregar playlist: " + self.last_error, flush=True)
            return False
        with self.lock:
            old = [x["id"] for x in self.channels]
            new = [x["id"] for x in best]
            if old != new:
                self.channels = best
                self.version += 1
            self.source, self.last_error = source, "; ".join(errors)
            self.last_refresh = time.time()
        print("[KTV] Catálogo: {} canais HLS".format(len(best)), flush=True)
        return True

    def refresh_loop(self):
        while True:
            time.sleep(REFRESH_SECONDS)
            self.refresh_playlist()

    def channel(self, identity):
        with self.lock:
            return next((dict(x) for x in self.channels if x["id"] == identity), None)

    def start_transcode(self, item):
        identity = item["id"]
        with self.lock:
            existing = self.processes.get(identity)
            if existing and existing.poll() is None:
                return True
            # A TV Orsay normalmente reproduz um canal por vez: não desperdice CPU
            # transcodificando canais que não estão sendo assistidos.
            for other_id, proc in list(self.processes.items()):
                if other_id != identity:
                    if proc.poll() is None:
                        proc.terminate()
                    self.processes.pop(other_id, None)
            folder = HLS_CACHE / identity
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*"):
                if old.is_file():
                    try:
                        old.unlink()
                    except OSError:
                        pass
            output = str(folder / "index.m3u8")
            segment = str(folder / "segment_%05d.ts")
            command = [
                self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
                "-y", "-fflags", "+genpts+discardcorrupt",
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-rw_timeout", "15000000", "-user_agent", "KTV-Server/{}".format(VERSION),
                "-i", item["source_url"], "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", "scale='min(1280,iw)':-2", "-r", "25",
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                "-profile:v", "main", "-level", "3.1", "-pix_fmt", "yuv420p",
                "-b:v", "2500k", "-maxrate", "2800k", "-bufsize", "5000k",
                "-g", "50", "-keyint_min", "50", "-sc_threshold", "0",
                "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
                "-f", "hls", "-hls_time", "4", "-hls_list_size", "8",
                "-hls_flags", "delete_segments+independent_segments+omit_endlist",
                "-hls_segment_filename", segment, output
            ]
            try:
                proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.processes[identity] = proc
                return True
            except OSError as exc:
                self.last_error = "Não foi possível iniciar FFmpeg: {}".format(exc)
                return False

    def stop_all(self):
        with self.lock:
            for proc in self.processes.values():
                if proc.poll() is None:
                    proc.terminate()
            self.processes.clear()


class Handler(BaseHTTPRequestHandler):
    server_version = "KTV-Server/{}".format(VERSION)

    def log_message(self, fmt, *args):
        print("[KTV] " + (fmt % args), flush=True)

    def respond(self, status, body, mime="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json(self, status, data):
        return self.respond(status, json.dumps(data, ensure_ascii=False))

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path in ("/", "/tv-info", "/tv-info/"):
            with self.server.lock:
                channels = len(self.server.channels)
                mode = "FFmpeg H.264/AAC" if self.server.transcode else "Direto"
                source = self.server.source or "Não carregada"
                error = self.server.last_error or "Nenhum"
            title = "Diagnóstico KTV Server" if path.startswith("/tv-info") else "KTV Server IPTV"
            html = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>{title}</title><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font:16px Arial;background:#101827;color:#f5f7fa;padding:28px">
<h1>{title}</h1><p>Status: <b style="color:#35c98a">ONLINE</b></p>
<p>Versão: {version}</p><p>Canais HLS: {channels}</p><p>Processamento: {mode}</p>
<p>Origem: {source}</p><p>Último erro: {error}</p>
<p><a style="color:#78baff" href="/api/health">API de saúde</a> ·
<a style="color:#78baff" href="/api/state">Catálogo JSON</a> ·
<a style="color:#78baff" href="/playlist.m3u">Playlist M3U</a></p></body></html>""".format(
                title=title, version=VERSION, channels=channels, mode=mode,
                source=source, error=error)
            return self.respond(200, html, "text/html; charset=utf-8")
        if path == "/api/health":
            with self.server.lock:
                return self.json(200, {"app": "KTV Server IPTV", "version": VERSION,
                    "status": "ok", "channels": len(self.server.channels),
                    "processing": "ffmpeg-h264-aac" if self.server.transcode else "direct",
                    "ffmpeg": bool(self.server.ffmpeg), "source": self.server.source,
                    "last_error": self.server.last_error})
        if path in ("/api/state", "/state"):
            client = parse_qs(urlsplit(self.path).query).get("client", ["samsung"])[0][:40]
            with self.server.lock:
                items = []
                for channel in self.server.channels:
                    item = {k: v for k, v in channel.items() if k != "source_url"}
                    item["url"] = (self.server.base_url + "/live/" + channel["id"] + "/index.m3u8"
                                   if self.server.transcode else channel["source_url"])
                    items.append(item)
                version = self.server.version
            return self.json(200, {"version": version, "items": items, "index": 0, "playing": True})
        if path == "/api/channels":
            with self.server.lock:
                return self.json(200, {"count": len(self.server.channels),
                    "items": [{k:v for k,v in x.items() if k != "source_url"} for x in self.server.channels]})
        if path == "/playlist.m3u":
            with self.server.lock:
                items = list(self.server.channels)
            lines = ["#EXTM3U"]
            for item in items:
                lines.append('#EXTINF:-1 tvg-logo="{}" group-title="{}",{}'.format(
                    item["logo"].replace('"', ""), item["category"].replace('"', ""),
                    item["name"].replace(",", " ")))
                url = (self.server.base_url + "/live/" + item["id"] + "/index.m3u8"
                       if self.server.transcode else item["source_url"])
                lines.append(url)
            return self.respond(200, "\n".join(lines) + "\n", "audio/x-mpegurl; charset=utf-8")
        if path.startswith("/live/"):
            parts = path.strip("/").split("/")
            if len(parts) != 3 or not re.fullmatch(r"[a-f0-9]{16}", parts[1]):
                return self.json(404, {"error": "Canal ou caminho inválido"})
            identity, filename = parts[1], parts[2]
            if filename != "index.m3u8" and not re.fullmatch(r"segment_\d{5}\.ts", filename):
                return self.json(404, {"error": "Segmento inválido"})
            item = self.server.channel(identity)
            if not item:
                return self.json(404, {"error": "Canal não encontrado"})
            if filename == "index.m3u8" and not self.server.start_transcode(item):
                return self.json(503, {"error": self.server.last_error})
            file = HLS_CACHE / identity / filename
            if not file.is_file():
                return self.respond(503, json.dumps({"error": "Preparando fluxo HLS; tente novamente"}),
                                extra={"Retry-After": "2"})
            mime = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
            try:
                return self.respond(200, file.read_bytes(), mime)
            except OSError:
                return self.json(503, {"error": "Segmento ainda não disponível"})
        if path == "/api/event":
            params = parse_qs(urlsplit(self.path).query)
            client = params.get("client", ["samsung"])[0][:40]
            event = params.get("event", ["unknown"])[0][:80]
            return self.json(200, {"ok": True, "client": client, "event": event})
        return self.json(404, {"error": "Rota não encontrada"})


def main():
    parser = argparse.ArgumentParser(description="KTV Server: transcodificação IPTV para Samsung")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--ip", default="")
    parser.add_argument("--playlist", default=DEFAULT_PLAYLIST)
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--mode", choices=("auto", "transcode", "direct"), default="auto",
                        help="auto usa FFmpeg quando instalado; transcode exige FFmpeg; direct não converte")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Caminho do executável FFmpeg")
    args = parser.parse_args()
    ffmpeg = shutil.which(args.ffmpeg)
    if args.mode == "transcode" and not ffmpeg:
        parser.error("FFmpeg não encontrado. Instale FFmpeg ou informe --ffmpeg C:\\caminho\\ffmpeg.exe")
    if args.mode == "direct":
        ffmpeg = None
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
    base = "http://{}:{}".format(ip, args.port)
    server = KTVServer((args.host, args.port), base, args.playlist,
                       "" if args.no_fallback else FALLBACK_PLAYLIST, ffmpeg, args.mode)
    print("\n=== KTV SERVER v{} ===".format(VERSION))
    print("Servidor:      {}".format(base))
    print("API Samsung:   {}/api/state".format(base))
    print("Playlist M3U:  {}/playlist.m3u".format(base))
    print("Canais HLS:    {}".format(len(server.channels)))
    print("Processamento: {}".format("FFmpeg H.264/AAC no servidor" if server.transcode else "direto (sem transcodificação)"))
    if server.transcode:
        print("FFmpeg:        {}".format(ffmpeg))
    print("TV e computador devem estar na mesma rede. CTRL+C encerra.\n", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nEncerrando KTV Server...")
    finally:
        server.stop_all()
        server.server_close()


if __name__ == "__main__":
    main()
