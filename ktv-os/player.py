"""Native playback for KTV OS. No shell, no remote-control IPC exposure.

Quality selects an initial HLS variant via mpv; it is NOT adaptive bitrate.
Telemetry reads only local mpv properties through a private Unix socket.
"""
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit
from stream_urls import validate_stream_url, validate_pluto_url, StreamURLError

QUALITY_PROFILES = {
    'economy': {'hls_bitrate': 'min', 'forward': '12MiB', 'back': '4MiB'},
    'balanced': {'hls_bitrate': '4000000', 'forward': '32MiB', 'back': '8MiB'},
    'best': {'hls_bitrate': 'max', 'forward': '64MiB', 'back': '16MiB'},
}
# All property names are fixed: the browser cannot choose mpv commands.
VIDEO_PROPERTIES = (
    'video-params', 'video-codec', 'container-fps', 'estimated-vf-fps',
    'frame-drop-count', 'decoder-frame-drop-count', 'demuxer-cache-duration',
    'hwdec-current', 'vid', 'aid', 'video-out-params',
)


def _number(value, maximum):
    """Clamp unreliable player metadata without inventing values."""
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if not 0 <= value <= maximum:
        return None
    return round(value, 2) if isinstance(value, float) else value


class NativePlayer:
    def __init__(self, executable=None, popen=None):
        self.executable = executable if executable is not None else shutil.which('mpv')
        self.popen = popen or subprocess.Popen
        self.lock = threading.RLock()
        self.process = None
        self.current = None
        self.quality = None
        self.decode = None
        self.last_exit_code = None
        self.ipc_dir = None
        self.ipc_path = None

    @property
    def available(self):
        return bool(self.executable)

    def _clear_ipc(self):
        if self.ipc_dir:
            shutil.rmtree(self.ipc_dir, ignore_errors=True)
        self.ipc_dir = None
        self.ipc_path = None

    def _read_video_state(self):
        if not self.ipc_path or not hasattr(socket, 'AF_UNIX'):
            return None
        properties = {}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.18)
                client.connect(self.ipc_path)
                for ident, name in enumerate(VIDEO_PROPERTIES, 1):
                    request = {'command': ['get_property', name], 'request_id': ident}
                    client.sendall((json.dumps(request) + '\n').encode('utf-8'))
                received = b''
                # Fixed budget: never wait on a stuck player or unbounded IPC data.
                while len(properties) < len(VIDEO_PROPERTIES) and len(received) < 32768:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    received += chunk
                    while b'\n' in received:
                        line, received = received.split(b'\n', 1)
                        if len(line) > 8192:
                            continue
                        try:
                            reply = json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if not isinstance(reply, dict) or reply.get('error') != 'success':
                            continue
                        ident = reply.get('request_id')
                        if type(ident) is int and 1 <= ident <= len(VIDEO_PROPERTIES):
                            properties[VIDEO_PROPERTIES[ident-1]] = reply.get('data')
        except (OSError, ValueError):
            return None
        if not properties:
            return None
        params = properties.get('video-params')
        params = params if isinstance(params, dict) else {}
        width = _number(params.get('w'), 7680)
        height = _number(params.get('h'), 4320)
        fps = _number(properties.get('estimated-vf-fps'), 240)
        if not fps:
            fps = _number(properties.get('container-fps'), 240)
        codec = properties.get('video-codec')
        hwdec = properties.get('hwdec-current')
        output = properties.get('video-out-params')
        video_track = properties.get('vid')
        audio_track = properties.get('aid')
        return {
            'video_rendered': isinstance(output, dict),
            'video_track': type(video_track) is int and video_track > 0,
            'audio_track': type(audio_track) is int and audio_track > 0,
            'width': width if width and width >= 16 else None,
            'height': height if height and height >= 16 else None,
            'fps': fps if fps and fps > 0 else None,
            'codec': codec[:32] if isinstance(codec, str) else None,
            'hardware_decoder': hwdec[:32] if isinstance(hwdec, str) else None,
            'dropped_frames': _number(properties.get('frame-drop-count'), 100000000),
            'decoder_dropped_frames': _number(properties.get('decoder-frame-drop-count'), 100000000),
            'buffer_seconds': _number(properties.get('demuxer-cache-duration'), 3600),
        }

    def status(self):
        with self.lock:
            code = self.process.poll() if self.process is not None else None
            playing = self.process is not None and code is None
            if not playing:
                if self.process is not None:
                    self.last_exit_code = code
                self.process = None
                self.current = None
                self.quality = None
                self.decode = None
                self._clear_ipc()
            return {
                'available': self.available,
                'playing': playing,
                'name': self.current,
                'quality': self.quality if playing else None,
                'decode': self.decode if playing else None,
                'exit_code': None if playing else self.last_exit_code,
                'video': self._read_video_state() if playing else None,
            }

    def stop(self):
        with self.lock:
            if self.process is None:
                self._clear_ipc()
                return False
            process = self.process
            self.process = None
            self.current = None
            self.quality = None
            self.decode = None
            self.last_exit_code = None
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            finally:
                self._clear_ipc()
            return True

    def play(self, source, name, quality='balanced', decode='default'):
        if not self.executable:
            raise RuntimeError('mpv nao instalado. Disponivel na imagem KTV OS Linux Live.')
        if not isinstance(source, str) or not source or source.startswith('-') or '\0' in source:
            raise ValueError('Fonte de video invalida')
        # Reject network protocols beyond direct HTTP(S), and unsafe local
        # destinations even when another caller forgets to validate streams.
        if source.startswith(('http://', 'https://')):
            try:
                if urlsplit(source).hostname == 'ipv4.pluto.tv':
                    validate_pluto_url(source)
                else:
                    validate_stream_url(source)
            except StreamURLError as exc:
                raise ValueError(str(exc)) from exc
        elif '://' in source or source.startswith(('data:', 'edl:', 'lavf:', 'ytdl:', 'mpv:')):
            raise ValueError('Protocolo de video nao autorizado')
        if type(quality) is not str or quality not in QUALITY_PROFILES:
            raise ValueError('Perfil de qualidade invalido')
        if type(decode) is not str or decode not in ('default', 'compatible'):
            raise ValueError('Modo de decodificacao invalido')
        self.stop()
        args = [
            self.executable, '--no-config', '--no-ytdl', '--fullscreen',
            '--force-window=yes', '--really-quiet',
        ]
        if decode == 'compatible':
            # Manual fallback for audio-only/black picture or buggy GPU drivers.
            # Software decoding + X11 output is slower: never enable by default.
            args.extend(('--hwdec=no', '--vo=x11', '--profile=sw-fast'))
        else:
            args.append('--hwdec=auto-safe')
        if urlsplit(source).path.lower().endswith('.m3u8'):
            chosen = QUALITY_PROFILES[quality]
            args.extend((
                '--hls-bitrate=' + chosen['hls_bitrate'],
                '--demuxer-max-bytes=' + chosen['forward'],
                '--demuxer-max-back-bytes=' + chosen['back'],
            ))
        # mpv IPC is a local diagnostic socket, never a public TCP endpoint.
        if os.name == 'posix' and hasattr(socket, 'AF_UNIX'):
            self.ipc_dir = tempfile.mkdtemp(prefix='ktv-mpv-')
            self.ipc_path = os.path.join(self.ipc_dir, 'control.sock')
            args.append('--input-ipc-server=' + self.ipc_path)
        args.extend(('--', source))
        with self.lock:
            try:
                self.process = self.popen(args, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as exc:
                self._clear_ipc()
                raise RuntimeError('Nao foi possivel iniciar mpv: {}'.format(exc))
            self.current = name
            self.quality = quality
            self.decode = decode
            self.last_exit_code = None
            return self.status()

    def close(self):
        self.stop()


def safe_media_path(root, filename, extensions):
    """Resolve a basename inside an explicitly selected folder; reject symlinks."""
    if not isinstance(filename, str) or not filename or filename.startswith('.') or \
            filename in ('.', '..') or '/' in filename or '\\' in filename or '\0' in filename:
        raise ValueError('Nome de midia invalido')
    base = Path(root).resolve(strict=True)
    candidate = base / filename
    if candidate.suffix.lower() not in extensions or candidate.is_symlink() or \
            not candidate.is_file() or candidate.resolve().parent != base:
        raise ValueError('Midia fora do local autorizado')
    return candidate
