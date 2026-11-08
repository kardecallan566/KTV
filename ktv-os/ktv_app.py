"""KTV App for Windows: desktop window around the existing KTV OS interface."""
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox

from launcher import KTVOSServer

APP_NAME = "KTV App"
HOST = "127.0.0.1"
PORT = 0  # porta livre: evita conflito com uma instância KTV OS já aberta


def wait_server(host, port, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def main():
    try:
        import webview
    except ImportError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_NAME,
            "O componente de janela do KTV App não está instalado.\n"
            "Execute install_windows.bat ou use a versão empacotada."
        )
        root.destroy()
        return 2

    server = None
    server_thread = None
    try:
        server = KTVOSServer(host=HOST, port=PORT)
        app_port = server.server_address[1]
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        if not wait_server(HOST, app_port):
            raise RuntimeError("O servidor local do KTV não iniciou.")
        window = webview.create_window(
            APP_NAME, f"http://{HOST}:{app_port}/",
            width=1280, height=720, min_size=(800, 500), fullscreen=True,
            background_color="#10131a",
        )
        webview.start()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, f"Não foi possível iniciar o KTV App.\n\n{exc}")
        root.destroy()
        return 1
    finally:
        if server:
            try:
                server.shutdown()
                server.player.close()
                server.server_close()
            except Exception:
                pass
        if server_thread:
            server_thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
