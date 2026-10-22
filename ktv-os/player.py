"""KTV OS native playback: mpv runs on the *computer* executing Linux Live.

Playback is restricted to the indexed channels and opt-in media locations.
Never spawn a shell, load user mpv.conf, or allow arbitrary command-line options.
"""
from pathlib import Path
import shutil
import subprocess
import threading

class NativePlayer:
    def __init__(self, executable=None, popen=None):
        self.executable = executable if executable is not None else shutil.which('mpv')
        self.popen = popen or subprocess.Popen
        self.lock = threading.RLock()
        self.process = None
        self.current = None

    @property
    def available(self):
        return bool(self.executable)

    def status(self):
        with self.lock:
            playing = self.process is not None and self.process.poll() is None
            if not playing:
                self.process = None
                self.current = None
            return {'available': self.available, 'playing': playing, 'name': self.current}

    def stop(self):
        with self.lock:
            if self.process is None:
                return False
            process = self.process
            self.process = None
            self.current = None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            return True

    def play(self, source, name):
        if not self.executable:
            raise RuntimeError('mpv nao instalado. Disponivel na imagem KTV OS Linux Live.')
        if not isinstance(source, str) or not source or source.startswith('-') or '\0' in source:
            raise ValueError('Fonte de video invalida')
        self.stop()
        args = [
            self.executable, '--no-config', '--no-ytdl', '--fullscreen',
            '--force-window=yes', '--hwdec=auto-safe', '--really-quiet', '--',
            source
        ]
        with self.lock:
            try:
                self.process = self.popen(args, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as exc:
                raise RuntimeError('Nao foi possivel iniciar mpv: {}'.format(exc))
            self.current = name
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
            not candidate.is_file() or candidate.resolve() .parent != base:
        raise ValueError('Midia fora do local autorizado')
    return candidate
