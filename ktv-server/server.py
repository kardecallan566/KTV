#!/usr/bin/env python3
"""KTV Server: prepara IPTV para Samsung Orsay usando FFmpeg no computador."""
import argparse
import hashlib
import html as html_lib
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

VERSION = "0.9.0"
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
        self.last_access = {}
        self.last_progress = {}
        self.last_restart = {}
        self.active_items = {}
        self.last_exit = {}
        self.idle_timeout = 90
        self.stall_timeout = 35
        self.restart_cooldown = 30
        DATA.mkdir(parents=True, exist_ok=True)
        HLS_CACHE.mkdir(parents=True, exist_ok=True)
        self.refresh_playlist()
        self.refresh_thread = threading.Thread(target=self.refresh_loop, daemon=True)
        self.refresh_thread.start()
        self.idle_thread = threading.Thread(target=self.stop_idle_transcodes, daemon=True)
        self.idle_thread.start()

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

    def stop_idle_transcodes(self):
        while True:
            time.sleep(5)
            now = time.time()
            restart = []
            with self.lock:
                for identity, proc in list(self.processes.items()):
                    if proc.poll() is not None:
                        self.last_exit[identity] = proc.poll()
                        print("[KTV] FFmpeg encerrou canal {} (código {})".format(
                            identity, proc.poll()), flush=True)
                        self.processes.pop(identity, None)
                        self.last_access.pop(identity, None)
                        self.last_progress.pop(identity, None)
                        self.active_items.pop(identity, None)
                        continue
                    folder = HLS_CACHE / identity
                    segments = list(folder.glob("segment_*.ts"))
                    if segments:
                        newest = max(x.stat().st_mtime for x in segments)
                        if newest > self.last_progress.get(identity, 0):
                            self.last_progress[identity] = newest
                    last_access = self.last_access.get(identity, 0)
                    if now - last_access >= self.idle_timeout:
                        print("[KTV] Sem requisicoes de espectadores em {}s; encerrando {}".format(
                            self.idle_timeout, identity), flush=True)
                        proc.terminate()
                        self.processes.pop(identity, None)
                        self.last_access.pop(identity, None)
                        self.last_progress.pop(identity, None)
                        self.active_items.pop(identity, None)
                        continue
                    progress = self.last_progress.get(identity, self.last_restart.get(identity, now))
                    if now - progress >= self.stall_timeout and now - self.last_restart.get(identity, 0) >= self.restart_cooldown:
                        item = self.active_items.get(identity)
                        if item:
                            restart.append(dict(item))
            for item in restart:
                self.restart_transcode(item, "sem novos segmentos")

    def restart_transcode(self, item, reason="fluxo parado"):
        identity = item["id"]
        with self.lock:
            now = time.time()
            if now - self.last_restart.get(identity, 0) < self.restart_cooldown:
                return False
            proc = self.processes.get(identity)
            if proc and proc.poll() is None:
                print("[KTV] Recuperando canal {}: {}".format(identity, reason), flush=True)
                try:
                    proc.terminate()
                    proc.wait(timeout=4)
                except Exception:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except Exception:
                        pass
            self.processes.pop(identity, None)
            self.last_access.pop(identity, None)
            self.last_progress.pop(identity, None)
            self.active_items.pop(identity, None)
        return self.start_transcode(item)

    def start_transcode(self, item):
        identity = item["id"]
        with self.lock:
            existing = self.processes.get(identity)
            if existing and existing.poll() is None:
                self.last_access[identity] = time.time()
                return True
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
                # O demuxer HLS atualiza playlists sozinho. Reconectar em EOF/404
                # força a releitura de recursos expirados e pode travar o fluxo em loop.
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
                "-rw_timeout", "20000000", "-user_agent", "KTV-Server/{}".format(VERSION),
                "-i", item["source_url"], "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", "scale='min(1280,iw)':-2", "-r", "25",
                # Perfil Baseline e sem B-frames ampliam a compatibilidade com TVs Samsung antigas.
                # GOP de 5s alinhado ao HLS: cada segmento começa em um keyframe.
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                "-profile:v", "baseline", "-level", "3.1", "-pix_fmt", "yuv420p",
                "-bf", "0", "-refs", "1",
                "-b:v", "2500k", "-maxrate", "2800k", "-bufsize", "5000k",
                "-g", "125", "-keyint_min", "125", "-sc_threshold", "0",
                "-force_key_frames", "expr:gte(t,n_forced*5)",
                "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "128k", "-ac", "2", "-ar", "44100",
                "-avoid_negative_ts", "make_zero",
                "-f", "hls", "-hls_segment_type", "mpegts",
                "-hls_time", "5", "-hls_list_size", "12",
                "-hls_delete_threshold", "15",
                "-hls_flags", "delete_segments+independent_segments+omit_endlist+temp_file",
                # Numeração única evita que a TV reutilize em cache o segmento 00000
                # depois de uma recuperação/reinicialização do FFmpeg.
                "-start_number", str(int(time.time()) % 100000),
                "-hls_segment_filename", segment, output
            ]
            try:
                # Preserve FFmpeg stderr to diagnose source and codec failures.
                log_path = folder / "ffmpeg.log"
                with open(log_path, "ab") as log_file:
                    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=log_file,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                now = time.time()
                self.processes[identity] = proc
                self.last_access[identity] = now
                self.last_progress[identity] = now
                self.last_restart[identity] = now
                self.active_items[identity] = dict(item)
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
            self.last_access.clear()
            self.last_progress.clear()
            self.active_items.clear()


class Handler(BaseHTTPRequestHandler):
    server_version = "KTV-Server/{}".format(VERSION)
    protocol_version = "HTTP/1.1"

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
        return self.respond(status, json.dumps(data, ensure_ascii=True, separators=(",", ":")))

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path in ("/", "/tv-info", "/tv-info/"):
            with self.server.lock:
                channels = len(self.server.channels)
                mode = "FFmpeg H.264/AAC" if self.server.transcode else "Direto"
                source = self.server.source or "Não carregada"
                error = self.server.last_error or "Nenhum"
            title = "Diagnóstico KTV Server" if path.startswith("/tv-info") else "KTV Server IPTV"
            # Página de diagnóstico deliberadamente simples para navegadores Samsung antigos.
            # Não inclui links para JSON/M3U, pois o navegador pode tentar baixá-los.
            html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title></head>
<body bgcolor="#101827" text="#f5f7fa">
<h2>{title}</h2>
<p>STATUS: ONLINE</p>
<p>VERSAO: {version}</p>
<p>CANAIS HLS: {channels}</p>
<p>PROCESSAMENTO: {mode}</p>
<p>ORIGEM: {source}</p>
<p>ULTIMO ERRO: {error}</p>
<hr>
<p>Servidor ativo. Esta pagina e apenas informativa.</p>
<p>Configure o endereco do servidor no aplicativo KTV da TV.</p>
</body></html>""".format(
                title=title, version=VERSION, channels=channels, mode=mode,
                source=source, error=error)
            return self.respond(200, html, "text/html; charset=utf-8")
        if path in ("/tv-test", "/tv-test/"):
            # Diagnóstico ES5 para navegadores Samsung antigos: mede suporte real a HLS
            # e codecs sem iniciar uma transcodificação ou consumir banda do canal.
            page = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>KTV - Teste da TV</title></head>
<body bgcolor="#101827" text="#ffffff"><h2>KTV - Compatibilidade da TV</h2>
<p id="browser">Verificando navegador...</p><p id="hls">HLS: verificando...</p>
<p id="mp4">MP4 H.264: verificando...</p><p id="aac">Áudio AAC: verificando...</p>
<p id="api">Servidor local: verificando...</p>
<p>Envie uma foto desta tela para o suporte KTV.</p><p><a href="/watch">Abrir lista de canais</a></p>
<script type="text/javascript">
(function () {
 var v = document.createElement("video");
 function set(id, value) { document.getElementById(id).innerHTML = value; }
 var ua = navigator.userAgent || "não informado";
 set("browser", "Navegador: " + ua);
 var hls = "";
 try { hls = v.canPlayType("application/vnd.apple.mpegurl") || v.canPlayType("application/x-mpegURL") || ""; } catch(e) {}
 set("hls", "HLS nativo: " + (hls ? hls : "NÃO DETECTADO"));
 var mp4 = "";
 try { mp4 = v.canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"') || ""; } catch(e) {}
 set("mp4", "MP4 H.264/AAC: " + (mp4 ? mp4 : "NÃO DETECTADO"));
 var aac = "";
 try { aac = v.canPlayType('audio/mp4; codecs="mp4a.40.2"') || ""; } catch(e) {}
 set("aac", "Áudio AAC: " + (aac ? aac : "NÃO DETECTADO"));
 try {
  var x = new XMLHttpRequest();
  x.open("GET", "/api/health", true);
  x.onreadystatechange = function () {
   if (x.readyState === 4) set("api", "Servidor local: " + (x.status === 200 ? "OK - " + x.responseText : "HTTP " + x.status));
  };
  x.send(null);
 } catch(e) { set("api", "Servidor local: falha ao testar"); }
}());
</script></body></html>"""
            return self.respond(200, page, "text/html; charset=utf-8")
        if path == "/watch" or path == "/watch/":
            query = parse_qs(urlsplit(self.path).query)
            term = query.get("q", [""])[0].strip().lower()[:80]
            with self.server.lock:
                channels = [dict(x) for x in self.server.channels]
            if term:
                channels = [x for x in channels if term in x["name"].lower()
                            or term in x["category"].lower()]
            shown = channels[:150]
            rows = []
            for channel in shown:
                href = "/watch/{}".format(channel["id"])
                rows.append('<li><a href="{}">{}</a> <small>{}</small></li>'.format(
                    href, html_lib.escape(channel["name"]), html_lib.escape(channel["category"])))
            if not rows:
                rows.append("<li>Nenhum canal encontrado.</li>")
            more = "<p>Mostrando os primeiros 150 resultados. Refine a busca para localizar outros canais.</p>" if len(channels) > 150 else ""
            page = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KTV - Canais</title></head><body bgcolor="#101827" text="#f5f7fa">
<h2>KTV - TV Online</h2><p>Escolha um canal para abrir no navegador da TV.</p>
<form action="/watch" method="get"><input name="q" value="{}" placeholder="Buscar canal ou categoria">
<input type="submit" value="Buscar"></form>
<p>Canais encontrados: {}</p>{}
<ul>{}</ul><p><a href="/">Voltar ao diagnóstico</a></p>
</body></html>""".format(html_lib.escape(term, quote=True), len(channels), more, "".join(rows))
            return self.respond(200, page, "text/html; charset=utf-8")
        if path.startswith("/watch/"):
            identity = path[len("/watch/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9]{16}", identity):
                return self.respond(404, "<html><body>Canal inválido. <a href='/watch'>Voltar</a></body></html>",
                                    "text/html; charset=utf-8")
            item = self.server.channel(identity)
            if not item:
                return self.respond(404, "<html><body>Canal não encontrado. <a href='/watch'>Voltar</a></body></html>",
                                    "text/html; charset=utf-8")
            hls_url = "/live/{}/index.m3u8".format(identity)
            mp4_url = "/live-mp4/{}".format(identity)
            direct_url = item["source_url"]
            page = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{}</title></head><body bgcolor="#000000" text="#ffffff">
<h3>{}</h3><video id="ktv-player" controls autoplay playsinline width="100%" height="auto"></video>
<img id="ktv-mjpeg" style="display:none;width:100%;height:auto" alt="Transmissão KTV">
<audio id="ktv-audio" controls autoplay style="width:100%;display:none"></audio>
<p id="ktv-status">Detectando formato de reprodução...</p><p><a href="/watch">Voltar aos canais</a></p>
<script type="text/javascript">
(function () {{
 var v=document.getElementById("ktv-player"), img=document.getElementById("ktv-mjpeg"), a=document.getElementById("ktv-audio"), s=document.getElementById("ktv-status");
 var hls="{}", mp4="{}", mjpeg="/live-mjpeg/{}", audio="/live-audio/{}", direct="{}", transcode="{}";
 var hs="";
 try {{ hs=v.canPlayType("application/vnd.apple.mpegurl")||v.canPlayType("application/x-mpegURL")||""; }} catch(e) {{}}
 if(hs) {{
  s.innerHTML="Modo selecionado: HLS";
  v.src=hls;
  try {{ v.load(); v.play(); }} catch(e) {{}}
 }} else if(transcode==="True") {{
  v.style.display="none";
  img.style.display="block";
  s.innerHTML="Modo MJPEG + áudio MP3. Qualidade otimizada para rede local.";
  img.src=mjpeg;
  a.style.display="block";
  a.src=audio;
  try {{ a.load(); a.play(); }} catch(e) {{}}
 }} else {{
  s.innerHTML="HLS não detectado; tentando origem direta";
  v.src=direct;
  try {{ v.load(); v.play(); }} catch(e) {{}}
 }}
 v.addEventListener("error",function(){{s.innerHTML="Falha ao decodificar o fluxo. Recarregue a página ou teste outro canal."; }},false);
}}());
</script></body></html>""".format(html_lib.escape(item["name"]), html_lib.escape(item["name"]),
 html_lib.escape(hls_url, quote=True), html_lib.escape(mp4_url, quote=True),
 html_lib.escape(identity, quote=True), html_lib.escape(identity, quote=True),
 html_lib.escape(direct_url, quote=True),
 str(self.server.transcode))
            return self.respond(200, page, "text/html; charset=utf-8")
        if path == "/api/health":
            with self.server.lock:
                return self.json(200, {"app": "KTV Server IPTV", "version": VERSION,
                    "status": "ok", "channels": len(self.server.channels),
                    "processing": "ffmpeg-h264-aac" if self.server.transcode else "direct",
                    "ffmpeg": bool(self.server.ffmpeg), "source": self.server.source,
                    "last_error": self.server.last_error})
        if path.startswith("/api/stream/"):
            identity = path[len("/api/stream/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9]{16}", identity):
                return self.json(400, {"error": "ID de canal inválido"})
            folder = HLS_CACHE / identity
            manifest = folder / "index.m3u8"
            segments = sorted(folder.glob("segment_*.ts")) if folder.exists() else []
            with self.server.lock:
                proc = self.server.processes.get(identity)
                running = bool(proc and proc.poll() is None)
                exit_code = self.server.last_exit.get(identity)
                last_access = self.server.last_access.get(identity)
                last_restart = self.server.last_restart.get(identity)
            newest_age = None
            if segments:
                try:
                    newest_age = round(max(0, time.time() - max(x.stat().st_mtime for x in segments)), 1)
                except OSError:
                    pass
            manifest_text = ""
            if manifest.is_file():
                try:
                    manifest_text = manifest.read_text(encoding="utf-8", errors="replace")[:12000]
                except OSError:
                    pass
            return self.json(200, {
                "channel": identity, "ffmpeg_running": running, "ffmpeg_exit_code": exit_code,
                "segment_count": len(segments), "newest_segment_age_seconds": newest_age,
                "manifest_exists": bool(manifest_text), "manifest": manifest_text,
                "last_request_epoch": last_access, "last_restart_epoch": last_restart
            })
        if path in ("/api/state", "/state"):
            client = parse_qs(urlsplit(self.path).query).get("client", ["samsung"])[0][:40]
            with self.server.lock:
                items = []
                for channel in self.server.channels:
                    # Contrato mínimo consumido pelo app Samsung Legacy (JavaScript ES5).
                    # Evita enviar metadados que a TV não utiliza e reduz o JSON recebido.
                    url = (self.server.base_url + "/live/" + channel["id"] + "/index.m3u8"
                           if self.server.transcode else channel["source_url"])
                    items.append({"name": channel["name"], "type": "hls",
                                  "url": url, "duration": 0})
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
        if path.startswith("/live-audio/"):
            identity = path[len("/live-audio/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9]{16}", identity):
                return self.json(404, {"error": "Canal inválido"})
            item = self.server.channel(identity)
            if not item:
                return self.json(404, {"error": "Canal não encontrado"})
            if not self.server.transcode:
                return self.respond(503, "FFmpeg indisponível", "text/plain; charset=utf-8")
            folder = HLS_CACHE / identity
            folder.mkdir(parents=True, exist_ok=True)
            command = [
                self.server.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
                "-fflags", "+genpts+discardcorrupt", "-reconnect", "1",
                "-reconnect_streamed", "1", "-reconnect_delay_max", "8",
                "-rw_timeout", "20000000", "-user_agent", "KTV-Server/{}".format(VERSION),
                "-i", item["source_url"], "-map", "0:a:0", "-vn",
                "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame",
                "-b:a", "96k", "-flush_packets", "1", "-f", "mp3", "pipe:1"
            ]
            proc = None
            try:
                with open(folder / "ffmpeg-audio.log", "ab") as log_file:
                    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=log_file, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), bufsize=0)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                print("[KTV] Cliente desconectou do áudio {}".format(identity), flush=True)
            finally:
                if proc:
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait(timeout=3)
                    except Exception:
                        try: proc.kill()
                        except Exception: pass
                    try: proc.stdout.close()
                    except Exception: pass
            self.close_connection = True
            return
        if path.startswith("/live-mjpeg/"):
            identity = path[len("/live-mjpeg/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9]{16}", identity):
                return self.json(404, {"error": "Canal inválido"})
            item = self.server.channel(identity)
            if not item:
                return self.json(404, {"error": "Canal não encontrado"})
            if not self.server.transcode:
                return self.respond(503, "FFmpeg indisponível", "text/plain; charset=utf-8")
            folder = HLS_CACHE / identity
            folder.mkdir(parents=True, exist_ok=True)
            command = [
                self.server.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
                "-fflags", "+genpts+discardcorrupt", "-reconnect", "1",
                "-reconnect_streamed", "1", "-reconnect_delay_max", "8",
                "-rw_timeout", "20000000", "-user_agent", "KTV-Server/{}".format(VERSION),
                "-i", item["source_url"], "-map", "0:v:0", "-an",
                "-vf", "fps=12,scale='min(854,iw)':-2",
                "-threads", "2", "-c:v", "mjpeg", "-q:v", "6",
                "-flush_packets", "1", "-f", "mpjpeg",
                "-boundary_tag", "ktvframe", "pipe:1"
            ]
            proc = None
            bytes_sent = 0
            started = time.time()
            try:
                with open(folder / "ffmpeg-mjpeg.log", "ab") as log_file:
                    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=log_file, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), bufsize=0)
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=ktvframe")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = proc.stdout.read(2048)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    bytes_sent += len(chunk)
                print("[KTV] MJPEG {} encerrou; bytes={}, duração={}s, código={}".format(
                    identity, bytes_sent, round(time.time()-started, 1), proc.poll()), flush=True)
            except (BrokenPipeError, ConnectionResetError, OSError):
                print("[KTV] Cliente desconectou do MJPEG {}".format(identity), flush=True)
            finally:
                if proc:
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait(timeout=3)
                    except Exception:
                        try: proc.kill()
                        except Exception: pass
                    try: proc.stdout.close()
                    except Exception: pass
            self.close_connection = True
            return
        if path.startswith("/live-mp4/"):
            identity = path[len("/live-mp4/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9]{16}", identity):
                return self.json(404, {"error": "Canal inválido"})
            item = self.server.channel(identity)
            if not item:
                return self.json(404, {"error": "Canal não encontrado"})
            if not self.server.transcode:
                return self.respond(503, "FFmpeg indisponível", "text/plain; charset=utf-8")
            # MP4 fragmentado por HTTP chunked para navegadores sem HLS nativo.
            folder = HLS_CACHE / identity
            folder.mkdir(parents=True, exist_ok=True)
            command = [
                self.server.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
                "-fflags", "+genpts+discardcorrupt", "-reconnect", "1",
                "-reconnect_streamed", "1", "-reconnect_delay_max", "8",
                "-rw_timeout", "20000000", "-user_agent", "KTV-Server/{}".format(VERSION),
                "-i", item["source_url"], "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", "scale='min(854,iw)':-2", "-r", "25",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-profile:v", "baseline", "-level", "3.1", "-pix_fmt", "yuv420p",
                "-bf", "0", "-refs", "1", "-b:v", "900k", "-maxrate", "1100k",
                "-bufsize", "1800k", "-g", "50", "-keyint_min", "50", "-sc_threshold", "0",
                "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "96k", "-ac", "2", "-ar", "44100",
                "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                "-frag_duration", "1000000", "-f", "mp4", "pipe:1"
            ]
            proc = None
            try:
                with open(folder / "ffmpeg-mp4.log", "ab") as log_file:
                    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=log_file, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), bufsize=0)
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Connection", "close")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk: break
                    self.wfile.write(("%X\r\n" % len(chunk)).encode("ascii"))
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                if proc:
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            proc.wait(timeout=3)
                    except Exception:
                        try: proc.kill()
                        except Exception: pass
                    try: proc.stdout.close()
                    except Exception: pass
            self.close_connection = True
            return
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
            if filename == "index.m3u8":
                if not self.server.start_transcode(item):
                    return self.json(503, {"error": self.server.last_error})
                # Aguarda o primeiro manifesto/segmento para evitar que a TV receba
                # um erro imediato enquanto o FFmpeg ainda inicializa o fluxo.
                deadline = time.time() + 15
                manifest = HLS_CACHE / identity / "index.m3u8"
                while time.time() < deadline:
                    if manifest.is_file() and manifest.stat().st_size > 0:
                        break
                    proc = self.server.processes.get(identity)
                    if proc is not None and proc.poll() is not None:
                        break
                    time.sleep(0.25)
            with self.server.lock:
                if identity in self.server.processes:
                    self.server.last_access[identity] = time.time()
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
    print("TV no navegador: {}/watch".format(base))
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
