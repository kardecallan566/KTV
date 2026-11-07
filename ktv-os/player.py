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
    'economy': {'hls_bitrate': 'min', 'forward': '12MiB', 'back': '4MiB', 'cache_secs': 15, 'readahead_secs': 10},
    'balanced': {'hls_bitrate': '4000000', 'forward': '32MiB', 'back': '8MiB', 'cache_secs': 30, 'readahead_secs': 25},
    'best': {'hls_bitrate': 'max', 'forward': '64MiB', 'back': '16MiB', 'cache_secs': 40, 'readahead_secs': 32},
}
# All property names are fixed: the browser cannot choose mpv commands.
VIDEO_PROPERTIES = (
    'video-params', 'video-codec', 'container-fps', 'estimated-vf-fps',
    'frame-drop-count', 'decoder-frame-drop-count', 'vo-drop-frame-count',\n    'vo-delayed-frame-count', 'audio-codec', 'audio-params', 'demuxer-cache-duration',
    'audio-pts', 'audio-speed', 'audio-bitrate', 'avsync',
    'hwdec-current', 'vid', 'aid', 'video-out-params',
    'time-pos', 'pause', 'eof-reached',
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
            'time_pos': _number(properties.get('time-pos'), 8640000),
            'paused': properties.get('pause') is True,
            'eof_reached': properties.get('eof-reached') is True,
            'video_rendered': isinstance(output, dict),
            'video_track': type(video_track) is int and video_track > 0,
            'audio_track': type(audio_track) is int and audio_track > 0,
            'width': width if width and width >= 16 else None,
            'height': height if height and height >= 16 else None,
            'fps': fps if fps and fps > 0 else None,
            'codec': codec[:32] if isinstance(codec, str) else None,
            'hardware_decoder': hwdec[:32] if isinstance(hwdec, str) else None,
            'dropped_frames': _number(properties.get('frame-drop-count'), 100000000),\n            'vo_dropped_frames': _number(properties.get('vo-drop-frame-count'), 100000000),\n            'vo_delayed_frames': _number(properties.get('vo-delayed-frame-count'), 100000000),
            'decoder_dropped_frames': _number(properties.get('decoder-frame-drop-count'), 100000000),
            'buffer_seconds': _number(properties.get('demuxer-cache-duration'), 3600),
            'audio_pts': _number(properties.get('audio-pts'), 8640000),
            'audio_speed': _number(properties.get('audio-speed'), 10),
            'audio_bitrate': _number(properties.get('audio-bitrate'), 100000000),\n            'audio_codec': (properties.get('audio-codec')[:32] if isinstance(properties.get('audio-codec'), str) else None),\n            'audio_output': isinstance(properties.get('audio-params'), dict),
            'av_sync': _number(properties.get('avsync'), 3600),
        }

    def set_audio_delay(self, delay):
        """Set mpv audio-delay in seconds using the private local IPC socket."""
        if type(delay) not in (int, float) or not math.isfinite(delay) or not -5 <= delay <= 5:
            raise ValueError('Atraso de áudio deve ficar entre -5 e 5 segundos')
        with self.lock:
            if self.process is None or self.process.poll() is not None or not self.ipc_path:
                raise RuntimeError('Player nativo não está em reprodução')
            request = json.dumps({'command':['set_property','audio-delay',round(float(delay),3)]})+'\n'
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                    client.settimeout(0.5)
                    client.connect(self.ipc_path)
                    client.sendall(request.encode('utf-8'))
                    response = client.recv(4096)
                replies=[json.loads(line) for line in response.splitlines() if line.strip()]
                if not any(item.get('error')=='success' for item in replies if isinstance(item,dict)):
                    raise RuntimeError('mpv não confirmou o ajuste de áudio')
            except (OSError,ValueError,json.JSONDecodeError) as exc:
                raise RuntimeError('Não foi possível ajustar áudio via IPC: {}'.format(exc))
            return round(float(delay),3)

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

    def play(self, source, name, quality='balanced', decode='default', user_agent=None, referrer=None):
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
            '--force-window=yes', '--ontop=yes', '--ontop-level=system', '--really-quiet',
            '--cache=yes', '--cache-secs=' + str(QUALITY_PROFILES[quality]['cache_secs']),
            '--demuxer-readahead-secs=' + str(QUALITY_PROFILES[quality]['readahead_secs']),
            '--demuxer-max-bytes=' + QUALITY_PROFILES[quality]['forward'],
            '--demuxer-max-back-bytes=' + QUALITY_PROFILES[quality]['back'],
            '--demuxer-thread=yes', '--audio-buffer=1.0', '--video-sync=audio', '--framedrop=vo',
            '--vd-lavc-threads=1', '--network-timeout=25',
            '--audio-pitch-correction=yes', '--interpolation=no', '--opengl-swapinterval=1',
            '--hr-seek=no', '--force-seekable=no',
        ]
        is_pluto = (urlsplit(source).hostname == 'ipv4.pluto.tv'
                    and urlsplit(source).path.endswith('/master.m3u8'))
        if is_pluto:
            # End-of-playlist should be detected by the recovery worker, not
            # exit silently. A user-initiated Q/CLOSE_WIN exits with code 77.
            args.extend(('--keep-open=yes','--network-timeout=25',
                         '--demuxer-thread=yes','--cache=yes','--cache-secs=30'))
        # Optional HTTP headers are supplied only by a server-side catalog,
        # never directly by the browser. Keep them bounded and syntactically safe.
        if user_agent is not None:
            if (type(user_agent) is not str or not 1 <= len(user_agent) <= 200 or
                    any(ord(char) < 32 or ord(char) == 127 for char in user_agent)):
                raise ValueError('User-Agent de transmissao invalido')
            args.append('--user-agent=' + user_agent)
        if referrer is not None:
            try:
                ref_parts = urlsplit(referrer)
                valid_referrer = (type(referrer) is str and len(referrer) <= 300 and
                                  ref_parts.scheme == 'https' and ref_parts.hostname and
                                  ref_parts.username is None and ref_parts.password is None and
                                  ref_parts.port in (None, 443) and not ref_parts.fragment)
            except ValueError:
                valid_referrer = False
            if not valid_referrer:
                raise ValueError('Referer de transmissao invalido')
            args.append('--referrer=' + referrer)
        if decode == 'compatible':
            # Manual fallback for audio-only/black picture or buggy GPU drivers.
            # Software decoding + X11 output is slower: never enable by default.
            args.extend(('--hwdec=no', '--vo=x11', '--profile=sw-fast'))
        else:
            args.append('--hwdec=auto-safe')
        media_path = urlsplit(source).path.lower()
        is_hls = media_path.endswith('.m3u8')
        is_ts = media_path.endswith('.ts')
        if is_hls or is_ts:
            chosen = QUALITY_PROFILES[quality]
            # HTTP reconnect applies to direct MPEG-TS as well as HLS. For TS,
            # avoid reconnect_at_eof so finite .ts files do not unexpectedly loop.
            reconnect = 'reconnect=1,reconnect_streamed=1,reconnect_delay_max=10'
            if is_hls:
                reconnect += ',reconnect_at_eof=1'
            args.append('--stream-lavf-o=' + reconnect)
            args.extend((
                '--demuxer-max-bytes=' + chosen['forward'],
                '--demuxer-max-back-bytes=' + chosen['back'],
            ))
            if is_hls:
                args.append('--hls-bitrate=' + chosen['hls_bitrate'])
        # mpv IPC is a local diagnostic socket, never a public TCP endpoint.
        if os.name == 'posix' and hasattr(socket, 'AF_UNIX'):
            self.ipc_dir = tempfile.mkdtemp(prefix='ktv-mpv-')
            self.ipc_path = os.path.join(self.ipc_dir, 'control.sock')
            args.append('--input-ipc-server=' + self.ipc_path)
            if is_pluto:
                bindings=os.path.join(self.ipc_dir,'pluto-keys.conf')
                with open(bindings,'w',encoding='ascii') as config:
                    config.write('q quit 77\nQ quit 77\nCLOSE_WIN quit 77\n')
                os.chmod(bindings,0o600)
                args.append('--input-conf='+bindings)
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
            self.backend = 'mpv'
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
