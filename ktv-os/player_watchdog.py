"""Conservative playback watchdog for native mpv sessions.

It detects timeline stalls without restarting arbitrary streams. Pluto's
credential-aware recovery remains handled by PlutoRecovery.
"""
import threading
import time

CHECK_INTERVAL = 5
STALL_SECONDS = 45
START_GRACE = 35


class PlayerWatchdog:
    def __init__(self, player, clock=None, threaded=True):
        self.player = player
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.started = 0
        self.last_progress = 0
        self.last_pos = None
        self.state = "idle"
        self.message = "Monitor aguardando reprodução."
        self.thread = None
        if threaded:
            self.thread = threading.Thread(target=self._loop, daemon=True,
                                          name="ktv-player-watchdog")
            self.thread.start()

    def _loop(self):
        while not self.stop_event.wait(CHECK_INTERVAL):
            self.tick()

    def reset(self):
        now = self.clock()
        with self.lock:
            self.started = now
            self.last_progress = now
            self.last_pos = None
            self.state = "starting"
            self.message = "Monitor verificando início do stream."

    def tick(self):
        info = self.player.status()
        now = self.clock()
        with self.lock:
            if not info.get("playing"):
                self.started = 0
                self.last_pos = None
                self.state = "idle"
                self.message = "Nenhuma reprodução nativa ativa."
                return self.status_unlocked()
            video = info.get("video")
            if not isinstance(video, dict):
                self.state = "unknown"
                self.message = "Player ativo; telemetria indisponível."
                return self.status_unlocked()
            if video.get("paused") is True:
                self.state = "paused"
                self.message = "Reprodução pausada pelo usuário."
                return self.status_unlocked()
            if not self.started:
                self.started = now
                self.last_progress = now
            pos = video.get("time_pos")
            if isinstance(pos, (int, float)):
                if self.last_pos is None or pos > self.last_pos + 0.2:
                    self.last_pos = pos
                    self.last_progress = now
                    self.state = "healthy"
                    self.message = "Avanço de reprodução normal."
                elif pos < self.last_pos - 5:
                    # Live timelines can reset/wrap; treat as progress.
                    self.last_pos = pos
                    self.last_progress = now
                    self.state = "healthy"
                    self.message = "Linha do tempo ao vivo reiniciada."
            if now - self.started < START_GRACE:
                self.state = "starting"
                self.message = "Aguardando o stream estabilizar."
            elif now - self.last_progress >= STALL_SECONDS:
                self.state = "stalled"
                self.message = "Possível travamento: linha do tempo sem avançar."
            elif self.state not in ("healthy", "stalled"):
                self.state = "healthy"
                self.message = "Player ativo; monitoramento normal."
            return self.status_unlocked()

    def status_unlocked(self):
        now = self.clock()
        return {
            "state": self.state,
            "message": self.message,
            "stall_seconds": (round(max(0, now - self.last_progress))
                              if self.last_progress else 0),
        }

    def status(self):
        with self.lock:
            return self.status_unlocked()

    def close(self):
        self.stop_event.set()
        if self.thread is not None and threading.current_thread() != self.thread:
            self.thread.join(timeout=2)
