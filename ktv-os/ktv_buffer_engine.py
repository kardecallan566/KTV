"""KTV Buffer Engine: bounded buffering policy and stream recovery scheduler.

This is an experimental policy module. It is not wired into the live player yet:
automatic retries must first be validated against real HLS/live sources on Pi.
"""
import threading
import time


class BufferEngineError(ValueError):
    pass


class KTVBufferEngine:
    """Track buffer health and schedule bounded retries with backoff.

    A caller supplies a restart callback. Retry callbacks execute on a worker
    thread, never inside the playback bus/UI thread.
    """

    def __init__(self, restart, max_retries=4, base_delay=1.5, max_delay=18.0,
                 stable_reset_seconds=30.0, clock=time.monotonic):
        if not callable(restart):
            raise BufferEngineError('Callback de recuperacao invalido')
        if type(max_retries) is not int or not 0 <= max_retries <= 12:
            raise BufferEngineError('Limite de tentativas invalido')
        if not 0.1 <= float(base_delay) <= 30 or not 0.1 <= float(max_delay) <= 120:
            raise BufferEngineError('Intervalo de recuperacao invalido')
        self._restart = restart
        self._max_retries = max_retries
        self._base_delay = float(base_delay)
        self._max_delay = float(max_delay)
        self._stable_reset = float(stable_reset_seconds)
        self._clock = clock
        self._lock = threading.RLock()
        self._generation = 0
        self._active = False
        self._state = 'idle'
        self._percent = 0
        self._retry_count = 0
        self._last_reason = None
        self._last_change = self._clock()
        self._healthy_since = None
        self._retry_at = None
        self._worker = None
        self._events = []

    def _event(self, name, detail=None):
        self._events.append({'event': name, 'detail': str(detail)[:200] if detail else None,
                             'at': round(self._clock(), 2)})
        self._events = self._events[-25:]
        self._last_change = self._clock()

    def start(self):
        with self._lock:
            self._generation += 1
            self._active = True
            self._state = 'healthy'
            self._percent = 100
            self._retry_count = 0
            self._last_reason = None
            self._retry_at = None
            self._healthy_since = self._clock()
            self._event('session-start')
            return self.status()

    def stop(self):
        with self._lock:
            self._generation += 1
            self._active = False
            self._state = 'idle'
            self._retry_at = None
            self._healthy_since = None
            self._event('session-stop')
        worker = self._worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=1)
        return self.status()

    def update_buffering(self, percent):
        if type(percent) not in (int, float) or not 0 <= percent <= 100:
            raise BufferEngineError('Percentual de buffer invalido')
        with self._lock:
            if not self._active:
                return self.status()
            self._percent = int(percent)
            if percent < 100:
                self._state = 'buffering'
                self._healthy_since = None
            else:
                self._state = 'healthy'
                if self._healthy_since is None:
                    self._healthy_since = self._clock()
                if self._clock() - self._healthy_since >= self._stable_reset:
                    if self._retry_count:
                        self._event('retry-counter-reset', 'stream stable')
                    self._retry_count = 0
            self._event('buffering', self._percent)
            return self.status()

    def request_recovery(self, reason='stream-error'):
        """Request one bounded retry. Returns False if inactive/exhausted."""
        with self._lock:
            if not self._active:
                self._event('recovery-ignored', 'inactive')
                return False
            if self._retry_count >= self._max_retries:
                self._state = 'failed'
                self._last_reason = str(reason)[:200]
                self._event('recovery-exhausted', self._last_reason)
                return False
            self._retry_count += 1
            self._last_reason = str(reason)[:200]
            delay = min(self._max_delay, self._base_delay * (2 ** (self._retry_count - 1)))
            self._retry_at = self._clock() + delay
            self._state = 'recovering'
            generation = self._generation
            self._event('recovery-scheduled', 'attempt {} in {:.1f}s'.format(self._retry_count, delay))
            worker = threading.Thread(target=self._run_retry,
                                      args=(generation, delay, self._retry_count),
                                      name='ktv-buffer-recovery', daemon=True)
            self._worker = worker
            worker.start()
            return True

    def _run_retry(self, generation, delay, attempt):
        deadline = self._clock() + delay
        while self._clock() < deadline:
            with self._lock:
                if not self._active or generation != self._generation:
                    return
            time.sleep(min(0.1, max(0, deadline - self._clock())))
        with self._lock:
            if not self._active or generation != self._generation:
                return
            self._state = 'restarting'
            self._retry_at = None
            self._event('recovery-start', attempt)
        try:
            result = self._restart()
            with self._lock:
                if not self._active or generation != self._generation:
                    return
                self._state = 'healthy' if result is not False else 'failed'
                self._percent = 100 if result is not False else 0
                self._healthy_since = self._clock() if result is not False else None
                self._event('recovery-success' if result is not False else 'recovery-failed', attempt)
        except Exception as exc:
            with self._lock:
                if not self._active or generation != self._generation:
                    return
                self._state = 'degraded'
                self._last_reason = str(exc)[:200]
                self._event('recovery-exception', self._last_reason)

    def status(self):
        with self._lock:
            now = self._clock()
            return {
                'engine': 'ktv-buffer-experimental',
                'active': self._active,
                'state': self._state,
                'buffering_percent': self._percent,
                'retry_count': self._retry_count,
                'retry_limit': self._max_retries,
                'retry_in_seconds': round(max(0, self._retry_at - now), 1)
                    if self._retry_at is not None else None,
                'last_reason': self._last_reason,
                'events': list(self._events),
            }
