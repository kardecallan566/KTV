"""KTV Stream Recovery Engine.

Experimental watchdog for streams that stop making progress without emitting an
explicit playback error. Kept independent from the production mpv player.
"""
import threading
import time


class StreamRecoveryError(ValueError):
    pass


class KTVStreamRecovery:
    """Watch progress markers and run bounded recovery callbacks off-thread."""

    def __init__(self, recover, stall_timeout=20.0, poll_interval=2.0,
                 max_recoveries=3, cooldown=8.0, clock=time.monotonic):
        if not callable(recover):
            raise StreamRecoveryError('Callback de recuperacao invalido')
        if not 3 <= float(stall_timeout) <= 300:
            raise StreamRecoveryError('Timeout de travamento invalido')
        if not 0.1 <= float(poll_interval) <= 30:
            raise StreamRecoveryError('Intervalo de monitoramento invalido')
        if type(max_recoveries) is not int or not 0 <= max_recoveries <= 10:
            raise StreamRecoveryError('Limite de recuperacoes invalido')
        if not 0 <= float(cooldown) <= 120:
            raise StreamRecoveryError('Cooldown invalido')
        self._recover = recover
        self._stall_timeout = float(stall_timeout)
        self._poll_interval = float(poll_interval)
        self._max_recoveries = max_recoveries
        self._cooldown = float(cooldown)
        self._clock = clock
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._generation = 0
        self._active = False
        self._paused = False
        self._state = 'idle'
        self._last_progress_at = None
        self._last_marker = None
        self._recoveries = 0
        self._last_reason = None
        self._last_recovery_at = None
        self._monitor = None
        self._worker = None
        self._events = []

    def _event(self, name, detail=None):
        self._events.append({
            'event': name,
            'detail': str(detail)[:180] if detail is not None else None,
            'at': round(self._clock(), 2),
        })
        self._events = self._events[-30:]

    def start(self, initial_marker=None):
        with self._lock:
            self.stop(join=False)
            self._generation += 1
            generation = self._generation
            now = self._clock()
            self._active = True
            self._paused = False
            self._state = 'watching'
            self._last_progress_at = now
            self._last_marker = initial_marker
            self._recoveries = 0
            self._last_reason = None
            self._last_recovery_at = None
            self._event('watch-start')
            self._monitor = threading.Thread(
                target=self._monitor_loop, args=(generation,),
                name='ktv-stream-watchdog', daemon=True)
            self._monitor.start()
            return self.status()

    def stop(self, join=True):
        with self._lock:
            self._generation += 1
            self._active = False
            self._paused = False
            self._state = 'idle'
            self._event('watch-stop')
            self._wake.set()
            monitor, worker = self._monitor, self._worker
        if join:
            current = threading.current_thread()
            for thread in (monitor, worker):
                if thread and thread is not current:
                    thread.join(timeout=1)
        return self.status()

    def pause(self):
        with self._lock:
            if not self._active:
                return False
            self._paused = True
            self._state = 'paused'
            self._event('watch-paused')
            return True

    def resume(self):
        with self._lock:
            if not self._active:
                return False
            self._paused = False
            self._last_progress_at = self._clock()
            self._state = 'watching'
            self._event('watch-resumed')
            self._wake.set()
            return True

    def report_progress(self, marker=None):
        """Report actual advancement (frame, byte count, PTS, etc.).

        If marker is supplied, duplicate markers do not reset the stall timer.
        If omitted, each call is treated as a fresh progress observation.
        """
        with self._lock:
            if not self._active:
                return False
            if marker is not None and marker == self._last_marker:
                return False
            self._last_marker = marker
            self._last_progress_at = self._clock()
            if not self._paused and self._state not in ('recovering', 'failed'):
                self._state = 'watching'
            self._event('progress', marker)
            return True

    def report_error(self, reason='stream-error'):
        with self._lock:
            if not self._active or self._paused:
                return False
            self._last_reason = str(reason)[:180]
            self._event('stream-error', self._last_reason)
            return self._schedule_recovery(self._last_reason)

    def _monitor_loop(self, generation):
        while True:
            self._wake.wait(self._poll_interval)
            self._wake.clear()
            with self._lock:
                if not self._active or generation != self._generation:
                    return
                if self._paused or self._state in ('recovering', 'failed'):
                    continue
                elapsed = self._clock() - self._last_progress_at
                if elapsed >= self._stall_timeout:
                    reason = 'no-progress-{:.1f}s'.format(elapsed)
                    self._last_reason = reason
                    self._event('stall-detected', reason)
                    self._schedule_recovery(reason)

    def _schedule_recovery(self, reason):
        # Caller holds the RLock.
        if self._state == 'recovering':
            return False
        now = self._clock()
        if self._last_recovery_at is not None and now - self._last_recovery_at < self._cooldown:
            self._event('recovery-cooldown', reason)
            return False
        if self._recoveries >= self._max_recoveries:
            self._state = 'failed'
            self._event('recovery-exhausted', reason)
            return False
        self._recoveries += 1
        attempt = self._recoveries
        generation = self._generation
        self._last_recovery_at = now
        self._state = 'recovering'
        self._event('recovery-start', 'attempt {}: {}'.format(attempt, reason))
        self._worker = threading.Thread(
            target=self._run_recovery, args=(generation, attempt),
            name='ktv-stream-recovery', daemon=True)
        self._worker.start()
        return True

    def _run_recovery(self, generation, attempt):
        try:
            result = self._recover()
            detail = 'callback returned false' if result is False else 'callback completed'
            success = result is not False
        except Exception as exc:
            detail = str(exc)[:180]
            success = False
        with self._lock:
            if not self._active or generation != self._generation:
                return
            if success:
                self._last_progress_at = self._clock()
                self._last_marker = None
                self._state = 'watching'
                self._event('recovery-complete', 'attempt {}: {}'.format(attempt, detail))
            elif self._recoveries >= self._max_recoveries:
                self._state = 'failed'
                self._event('recovery-failed', 'attempt {}: {}'.format(attempt, detail))
            else:
                self._state = 'degraded'
                self._event('recovery-failed', 'attempt {}: {}'.format(attempt, detail))

    def status(self):
        with self._lock:
            now = self._clock()
            stalled_for = (max(0.0, now - self._last_progress_at)
                           if self._last_progress_at is not None else None)
            return {
                'engine': 'ktv-stream-recovery-experimental',
                'active': self._active,
                'paused': self._paused,
                'state': self._state,
                'stalled_for_seconds': round(stalled_for, 1) if stalled_for is not None else None,
                'stall_timeout_seconds': self._stall_timeout,
                'recoveries': self._recoveries,
                'recovery_limit': self._max_recoveries,
                'last_reason': self._last_reason,
                'events': list(self._events),
            }
