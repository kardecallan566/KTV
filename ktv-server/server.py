#!/usr/bin/env python3
"""KTV Server - servidor local independente para Samsung Smart TV Orsay.
Compatível com o contrato usado por tv-orsay/js/app.js.
Somente biblioteca padrão do Python.
"""
import argparse
import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEDIA = DATA / "media"
STATE_FILE = DATA / "state.json"
ALLOWED = {".mp4", ".m4v", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD = 100 * 1024 * 1024


def load_state():
    DATA.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("items"), list):
                value.setdefault("version", 1)
                value.setdefault("index", 0)
                value.setdefault("playing", True)
                return value
        except (OSError, ValueError):
            pass
    return {"version": 1, "items": [], "index": 0, "playing": True}


class KTVServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, host_url):
        super().__init__(address, Handler)
        self.host_url = host_url.rstrip("/")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.RLock()
        self.state = load_state()
        self.clients = {}
        self.events = {}
        self.tv_probes = []

    def save(self):
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)


class Handler(BaseHTTPRequestHandler):
    server_version = "KTV-Server/0.1.0"

    def log_message(self, fmt, *args):
        print("[KTV Server] " + (fmt % args), flush=True)

    def send_bytes(self, status, body, mime="application/json; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json(self, status, value):
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def read_json(self, limit=1024 * 1024):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 0 or length > limit:
            return None
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            return value if isinstance(value, dict) else None
        except (UnicodeError, ValueError):
            return None

    def authorized(self):
        from hmac import compare_digest
        return compare_digest(self.headers.get("X-KTV-Token", ""), self.server.token)

    def media_file(self, path):
        if not path.is_file():
            return self.json(404, {"error": "Arquivo não encontrado"})
        size = path.stat().st_size
        start, end, status = 0, max(0, size - 1), 200
        header = self.headers.get("Range", "")
        if header:
            import re
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
            if not match or (not match.group(1) and not match.group(2)):
                return self.send_bytes(416, b"", extra={"Content-Range": "bytes */{}".format(size)})
            try:
                if not match.group(1):
                    start = max(0, size - int(match.group(2)))
                else:
                    start = int(match.group(1))
                    if match.group(2):
                        end = min(end, int(match.group(2)))
                if size == 0 or start > end or start >= size:
                    return self.send_bytes(416, b"", extra={"Content-Range": "bytes */{}".format(size)})
            except ValueError:
                return self.send_bytes(416, b"", extra={"Content-Range": "bytes */{}".format(size)})
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, size))
        self.end_headers()
        try:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path in ("/", "/admin", "/admin/"):
            return self.media_file(ROOT / "admin" / "index.html")
        if path == "/api/health":
            return self.json(200, {"app": "KTV Server", "version": VERSION, "status": "ok"})
        if path == "/api/tv-probe":
            self.server.tv_probes.append({"ip": self.client_address[0],
                "user_agent": self.headers.get("User-Agent", "")[:240], "seen": time.time()})
            self.server.tv_probes = self.server.tv_probes[-20:]
            return self.json(200, {"ok": True})
        if path == "/api/state":
            client = parse_qs(parsed.query).get("client", ["orsay"])[0]
            with self.server.lock:
                self.server.clients[client[:32]] = {"ip": self.client_address[0], "seen": time.time()}
                data = dict(self.server.state)
                data["items"] = [dict(item, url=(item["url"] if item.get("type") == "hls"
                    else self.server.host_url + "/media/" + item["id"])) for item in data["items"]]
            return self.json(200, data)
        if path == "/api/event":
            params = parse_qs(parsed.query)
            client = params.get("client", ["tv"])[0][:32]
            event = params.get("event", ["unknown"])[0][:64]
            self.server.events[client] = {"event": event, "ip": self.client_address[0], "seen": time.time()}
            return self.json(200, {"ok": True})
        if path == "/api/library":
            if not self.authorized():
                return self.json(401, {"error": "Token administrativo inválido"})
            items = []
            for file in sorted(MEDIA.iterdir()):
                if file.is_file() and file.suffix.lower() in ALLOWED:
                    kind = "image" if file.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp") else "video"
                    items.append({"id": file.name, "name": file.name, "type": kind, "bytes": file.stat().st_size})
            return self.json(200, {"items": items})
        if path == "/api/status":
            if not self.authorized():
                return self.json(401, {"error": "Token administrativo inválido"})
            now = time.time()
            with self.server.lock:
                clients = {k: {"ip": v["ip"], "last_seen_seconds": round(now-v["seen"])}
                           for k, v in self.server.clients.items()}
                events = {k: {"event": v["event"], "ip": v["ip"], "seconds_ago": round(now-v["seen"])}
                          for k, v in self.server.events.items()}
                return self.json(200, {"version": VERSION, "clients": clients,
                    "events": events, "tv_probes": self.server.tv_probes,
                    "state_version": self.server.state["version"]})
        if path.startswith("/media/"):
            name = path[len("/media/"):]
            if not name or "/" in name or "\\" in name or name.startswith("."):
                return self.json(404, {"error": "Caminho inválido"})
            file = MEDIA / name
            if file.suffix.lower() not in ALLOWED:
                return self.json(404, {"error": "Formato não permitido"})
            return self.media_file(file)
        return self.json(404, {"error": "Rota não encontrada"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self.authorized():
            return self.json(401, {"error": "Token administrativo inválido"})
        if path == "/api/admin/upload":
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            name = unquote(parse_qs(urlsplit(self.path).query).get("filename", [""])[0])
            suffix = Path(name).suffix.lower()
            if size <= 0 or size > MAX_UPLOAD or suffix not in ALLOWED:
                return self.json(400, {"error": "Arquivo inválido ou maior que 100 MB"})
            safe = secrets.token_hex(8) + suffix
            target = MEDIA / safe
            remaining = size
            try:
                with target.open("xb") as output:
                    while remaining:
                        chunk = self.rfile.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise OSError("Upload incompleto")
                        output.write(chunk)
                        remaining -= len(chunk)
            except OSError:
                target.unlink(missing_ok=True)
                return self.json(400, {"error": "Falha ao receber arquivo"})
            return self.json(201, {"id": safe, "name": name})
        if path not in ("/api/admin/state", "/api/admin/command"):
            return self.json(404, {"error": "Rota não encontrada"})
        data = self.read_json()
        if data is None:
            return self.json(400, {"error": "JSON inválido"})
        with self.server.lock:
            state = dict(self.server.state)
            if path.endswith("/state"):
                ids = data.get("ids")
                if not isinstance(ids, list) or len(ids) > 200:
                    return self.json(400, {"error": "Lista de mídias inválida"})
                items = []
                for identity in ids:
                    if not isinstance(identity, str) or Path(identity).name != identity:
                        return self.json(400, {"error": "Identificador inválido"})
                    file = MEDIA / identity
                    if not file.is_file() or file.suffix.lower() not in ALLOWED:
                        return self.json(400, {"error": "Mídia não encontrada: " + identity})
                    kind = "image" if file.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp") else "video"
                    items.append({"id": identity, "name": identity, "type": kind, "duration": 10})
                state.update(items=items, index=0, playing=True)
            else:
                command = data.get("command")
                count = len(state["items"])
                if command == "next" and count:
                    state["index"] = (state["index"] + 1) % count
                elif command == "previous" and count:
                    state["index"] = (state["index"] - 1) % count
                elif command == "play":
                    state["playing"] = True
                elif command == "pause":
                    state["playing"] = False
                elif command == "clear":
                    state.update(items=[], index=0, playing=True)
                else:
                    return self.json(400, {"error": "Comando inválido"})
            state["version"] += 1
            self.server.state = state
            self.server.save()
        return self.json(200, state)


def main():
    parser = argparse.ArgumentParser(description="KTV Server para Samsung Smart TV")
    parser.add_argument("--host", default="0.0.0.0", help="Interface de rede")
    parser.add_argument("--port", type=int, default=8787, help="Porta HTTP (padrão 8787)")
    parser.add_argument("--ip", default="", help="IP do computador anunciado para a TV")
    args = parser.parse_args()
    import socket
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
    server = KTVServer((args.host, args.port), base)
    print("\n=== KTV SERVER v{} ===".format(VERSION))
    print("Painel:       {}".format(base + "/admin/"))
    print("URL para TV:  {}".format(base))
    print("Diagnóstico:  {}".format(base + "/api/health"))
    print("Token admin:  {}".format(server.token))
    print("Mídias:       {}".format(MEDIA))
    print("Apenas rede local confiável. Não exponha esta porta à Internet.")
    print("CTRL+C para encerrar.\n", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nEncerrando KTV Server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
