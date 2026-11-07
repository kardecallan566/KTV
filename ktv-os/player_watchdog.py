"""Conservative mpv timeline watchdog with bounded generic reconnection."""
import threading
import time

CHECK_INTERVAL = 5
STALL_SECONDS = 60
START_GRACE = 35
MAX_RECOVERY_ATTEMPTS = 3
RECOVERY_COOLDOWN = 30


class PlayerWatchdog:
    def __init__(self, player, clock=None, threaded=True, recover=None):
        self.player = player
        self.clock = clock or time.monotonic
        self.recover = recover
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.started = 0
        self.last_progress = 0
        self.last_pos = None
        self.state = "idle"
        self.message = "Monitor aguardando reprodução."
        self.session = None
        self.recovery_attempts = 0
        self.last_recovery = 0
        self.recovery_in_progress = False
        self.thread = None
        if threaded:
            self.thread = threading.Thread(target=self._loop, daemon=True,
                                          name="ktv-player-watchdog")
            self.thread.start()

    def _loop(self):
        while not self.stop_event.wait(CHECK_INTERVAL):
            self.tick()

    def set_session(self, source, name, quality, decode, user_agent=None,
                    referrer=None, recoverable=True):
        with self.lock:
            self.session = ((source, name, quality, decode, user_agent, referrer)
                           if recoverable else None)
            self.recovery_attempts = 0
            self.last_recovery = 0
            self.recovery_in_progress = False

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
                self.session = None
                self.recovery_attempts = 0
                self.recovery_in_progress = False
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
                if (self.session and self.recover and not self.recovery_in_progress
                        and self.recovery_attempts < MAX_RECOVERY_ATTEMPTS
                        and now - self.last_recovery >= RECOVERY_COOLDOWN):
                    self.recovery_in_progress = True
                    threading.Thread(target=self._recover_session, daemon=True,
                                     name="ktv-watchdog-recovery").start()
            elif self.state not in ("healthy", "stalled", "recovering"):
                self.state = "healthy"
                self.message = "Player ativo; monitoramento normal."
            return self.status_unlocked()

    def _recover_session(self):
        # Serialize recovery against session replacement/manual channel changes.
        with self.lock:
            session = self.session
            if not session or self.stop_event.is_set():
                self.recovery_in_progress = False
                return
            self.recovery_attempts += 1
            self.last_recovery = self.clock()
            try:
                result = self.recover(session)
                if result:
                    now = self.clock()
                    self.started = now
                    self.last_progress = now
                    self.last_pos = None
                    self.state = "recovering"
                    self.message = "Reconexão automática solicitada; aguardando sinal."
                else:
                    self.message = "Reconexão automática não foi possível; mantendo monitoramento."
            except Exception:
                self.message = "Falha ao tentar reconexão automática."
            finally:
                self.recovery_in_progress = False

    def status_unlocked(self):
        now = self.clock()
        return {
            "state": self.state,
            "message": self.message,
            "stall_seconds": round(max(0, now - self.last_progress)) if self.last_progress else 0,
            "recovery_attempts": self.recovery_attempts,
            "recovery_available": bool(self.session and self.recover),
            "recovery_in_progress": self.recovery_in_progress,
        }

    def status(self):
        with self.lock:
            return self.status_unlocked()

    def close(self):
        self.stop_event.set()
        with self.lock:
            self.session = None
        if self.thread is not None and threading.current_thread() != self.thread:
            self.thread.join(timeout=2)
