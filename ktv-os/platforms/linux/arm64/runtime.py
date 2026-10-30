#!/usr/bin/env python3
"""Manual Linux ARM64 kiosk runtime for the KTV OS.

Starts the existing local KTV server and Chromium in kiosk mode. The server
binds only to loopback. This is a manual test launcher, not a systemd installer.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_arm64(machine: str | None = None) -> bool:
    value = (machine or platform.machine()).strip().lower()
    return value in ("aarch64", "arm64")


def find_chromium(which: Callable[[str], str | None] = shutil.which) -> str | None:
    return which("chromium") or which("chromium-browser")


def build_browser_command(
    executable: str,
    url: str,
    safe_browser: bool = False,
) -> list[str]:
    command = [
        executable,
        "--no-first-run",
        "--disable-session-crashed-bubble",
        "--noerrdialogs",
        "--password-store=basic",
        "--kiosk",
        "--app=" + url,
    ]
    if safe_browser:
        command.extend(("--disable-gpu", "--disable-gpu-compositing"))
    return command


def wait_for_server(
    url: str,
    attempts: int = 40,
    interval: float = 0.25,
    opener: Callable[..., object] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    for _ in range(max(1, attempts)):
        try:
            with opener(url, timeout=1) as response:
                if getattr(response, "status", None) == 200:
                    return True
        except (OSError, URLError):
            pass
        sleeper(interval)
    return False


def _default_server_factory() -> Callable[..., object]:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from launcher import KTVOSServer

    return KTVOSServer


def run(
    args: argparse.Namespace,
    machine: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    popen: Callable[..., object] = subprocess.Popen,
    server_factory: Callable[..., object] | None = None,
    opener: Callable[..., object] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    printer: Callable[[str], None] = print,
) -> int:
    if not is_arm64(machine):
        printer("KTV OS ARM64: este runtime exige Linux aarch64/arm64.")
        return 2

    browser = find_chromium(which)
    if not browser:
        printer("KTV OS ARM64: Chromium nao encontrado. Instale-o no Raspberry Pi OS.")
        return 3

    factory = server_factory or _default_server_factory()
    server = factory(
        host="127.0.0.1",
        port=args.port,
        media_dir=args.media_dir,
        state_dir=args.state_dir,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    browser_process = None
    try:
        server_thread.start()
        actual_port = server.server_address[1]
        url = "http://127.0.0.1:{}/".format(actual_port)
        if not wait_for_server(url + "api/status", opener=opener, sleeper=sleeper):
            raise RuntimeError("O servidor KTV nao respondeu ao healthcheck local.")

        printer("KTV OS ARM64: servidor local ativo em {}".format(url))
        printer("KTV OS ARM64: abrindo Chromium em modo kiosk.")
        command = build_browser_command(browser, url, safe_browser=args.safe_browser)
        browser_process = popen(command, stdin=subprocess.DEVNULL)
        return int(browser_process.wait())
    except KeyboardInterrupt:
        printer("KTV OS ARM64: encerramento solicitado pelo usuario.")
        return 0
    except (OSError, RuntimeError) as exc:
        printer("KTV OS ARM64: {}".format(exc))
        return 1
    finally:
        if browser_process is not None:
            try:
                if browser_process.poll() is None:
                    browser_process.terminate()
                    try:
                        browser_process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        browser_process.kill()
                        browser_process.wait(timeout=3)
            except OSError:
                pass
        if server_thread.is_alive():
            server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inicia o KTV OS manualmente no Raspberry Pi OS 64-bit."
    )
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--media-dir", help="Pasta local autorizada para midias.")
    parser.add_argument("--state-dir", help="Pasta para canais, favoritos e configuracoes.")
    parser.add_argument(
        "--safe-browser",
        action="store_true",
        help="Abre Chromium sem composicao GPU como modo de recuperacao.",
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
