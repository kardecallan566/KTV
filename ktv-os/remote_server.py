"""KTV Local Remote: LAN-only WebSocket control and Linux uinput mouse/keyboard."""
import asyncio
import json
import os
import secrets
import socket
from pathlib import Path

from aiohttp import web, WSMsgType

try:
    from evdev import UInput, ecodes
except ImportError:
    UInput = None
    ecodes = None

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "remote-web"
STATE = Path.home() / ".config" / "ktv-os"
CONFIG = STATE / "remote.json"
HOST = os.environ.get("KTV_REMOTE_HOST", "0.0.0.0")
PORT = int(os.environ.get("KTV_REMOTE_PORT", "8765"))
MAX_RATE = 120
KEY_MAP = {
    "Enter": "KEY_ENTER", "Escape": "KEY_ESC", "Backspace": "KEY_BACKSPACE",
    "Tab": "KEY_TAB", " ": "KEY_SPACE", "ArrowUp": "KEY_UP",
    "ArrowDown": "KEY_DOWN", "ArrowLeft": "KEY_LEFT", "ArrowRight": "KEY_RIGHT",
    "Home": "KEY_HOME", "End": "KEY_END", "PageUp": "KEY_PAGEUP",
    "PageDown": "KEY_PAGEDOWN", "Delete": "KEY_DELETE", "Shift": "KEY_LEFTSHIFT",
}
for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEY_MAP[letter.lower()] = "KEY_" + letter
for digit in "0123456789":
    KEY_MAP[digit] = "KEY_" + digit
KEY_MAP.update({f"F{i}": f"KEY_F{i}" for i in range(1, 13)})


def load_config():
    STATE.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            if data.get("pin") and data.get("token"):
                return data
        except (OSError, ValueError):
            pass
    data = {"pin": f"{secrets.randbelow(900000) + 100000}", "token": secrets.token_urlsafe(32)}
    CONFIG.write_text(json.dumps(data), encoding="utf-8")
    CONFIG.chmod(0o600)
    return data


class VirtualInput:
    def __init__(self):
        self.device = None
        self.error = None
        if UInput is None:
            self.error = "python3-evdev não está instalado"
            return
        try:
            capabilities = {
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL],
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE] +
                    [getattr(ecodes, value) for value in set(KEY_MAP.values()) if hasattr(ecodes, value)],
            }
            self.device = UInput(capabilities, name="KTV Virtual Mouse", vendor=0x4B54, product=0x5652)
        except (OSError, PermissionError) as exc:
            self.error = f"uinput indisponível: {exc}"

    def emit(self, event, value=1):
        if not self.device:
            raise RuntimeError(self.error or "dispositivo virtual indisponível")
        code = getattr(ecodes, event, None)
        if code is None:
            raise ValueError("evento inválido")
        event_type = ecodes.EV_REL if event.startswith("REL_") else ecodes.EV_KEY
        self.device.write(event_type, code, int(value))
        self.device.syn()

    def key(self, key, pressed):
        name = KEY_MAP.get(key)
        if not name:
            return
        self.emit(name, 1 if pressed else 0)

    def close(self):
        if self.device:
            self.device.close()
            self.device = None


def private_lan(ip):
    if ip in ("127.0.0.1", "::1"):
        return True
    try:
        address = ipaddress.ip_address(ip)
        return address.is_private or address.is_link_local
    except (ValueError, NameError):
        return False


import ipaddress


async def index(_request):
    return web.FileResponse(WEB / "index.html")


async def static_file(request):
    name = request.match_info["name"]
    if name not in ("app.js", "style.css"):
        raise web.HTTPNotFound()
    return web.FileResponse(WEB / name)


async def status(request):
    engine = request.app["input"]
    return web.json_response({"service": "KTV Local Remote", "paired": True,
                              "virtual_input": bool(engine.device), "input_error": engine.error,
                              "host": socket.gethostname(), "port": PORT})


async def pair(request):
    if not private_lan(request.remote or ""):
        raise web.HTTPForbidden(text="Apenas rede local")
    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise web.HTTPBadRequest(text="JSON inválido")
    if not secrets.compare_digest(str(data.get("pin", "")), request.app["config"]["pin"]):
        raise web.HTTPUnauthorized(text="PIN incorreto")
    return web.json_response({"token": request.app["config"]["token"]})


async def remote_ws(request):
    if not private_lan(request.remote or ""):
        raise web.HTTPForbidden(text="Apenas rede local")
    token = request.query.get("token", "")
    if not secrets.compare_digest(token, request.app["config"]["token"]):
        raise web.HTTPUnauthorized(text="Dispositivo não pareado")
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
    await ws.prepare(request)
    engine = request.app["input"]
    try:
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                if message.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
                continue
            try:
                payload = json.loads(message.data)
                action = payload.get("type")
                if action == "move":
                    engine.emit("REL_X", max(-120, min(120, int(payload.get("x", 0)))))
                    engine.emit("REL_Y", max(-120, min(120, int(payload.get("y", 0)))))
                elif action == "click":
                    button = {"left": "BTN_LEFT", "right": "BTN_RIGHT", "middle": "BTN_MIDDLE"}.get(payload.get("button", "left"))
                    engine.emit(button, 1); engine.emit(button, 0)
                elif action == "scroll":
                    engine.emit("REL_WHEEL", max(-10, min(10, int(payload.get("y", 0)))))
                elif action == "key":
                    engine.key(str(payload.get("key", "")), bool(payload.get("down", True)))
                elif action == "text":
                    for char in str(payload.get("text", ""))[:180]:
                        key = char.lower() if char.isalpha() else char
                        if key in KEY_MAP:
                            engine.key(key, True); engine.key(key, False)
                elif action == "ping":
                    await ws.send_json({"type": "pong"})
                else:
                    await ws.send_json({"type": "error", "message": "comando desconhecido"})
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                await ws.send_json({"type": "error", "message": str(exc)[:180]})
    finally:
        # Release held keys if the browser disconnects unexpectedly.
        for key in KEY_MAP:
            engine.key(key, False)
        await ws.close()
    return ws


def create_app():
    app = web.Application(client_max_size=8192)
    app["config"] = load_config()
    app["input"] = VirtualInput()
    app.router.add_get("/", index)
    app.router.add_get("/{name:app.js|style.css}", static_file)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/pair", pair)
    app.router.add_get("/ws", remote_ws)
    app.on_cleanup.append(lambda _app: _app["input"].close())
    return app


if __name__ == "__main__":
    config = load_config()
    print(f"KTV Local Remote: http://<IP-DA-TV>:{PORT}/")
    print(f"PIN de pareamento: {config['pin']}")
    web.run_app(create_app(), host=HOST, port=PORT, access_log=None)
