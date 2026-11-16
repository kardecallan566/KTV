"""Background cache health monitor restricted to the external IPTV playlist.

It never replaces/restarts MPV. When a low buffer fails to refill, it refreshes
the private M3U catalogue and leaves transport reconnection to MPV's HTTP/HLS
reconnect machinery, preserving the currently playing session and timeline.
"""
from __future__ import annotations
import threading
import time
from pathlib import Path

from iptv_free_catalog import refresh_catalog, IPTVFreeCatalogError


class IPTVCacheMonitor:
    SAMPLE_SECONDS = 5
    LOW_BUFFER_SECONDS = 8
    STALL_SECONDS = 15
    REFRESH_COOLDOWN = 60

    def __init__(self, player, catalog_path):
        self.player = player
        self.catalog_path = Path(catalog_path)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._active = False
        self._channel = None
        self._last_cache = None
        self._last_growth = time.monotonic()
        self._last_refresh = 0.0
        self._refreshing = False
        self._refresh_count = 0
        self._failure_count = 0
        self._last_error = None
        self._state = "idle"
        self._buffer = None
        self._stall_seconds = 0
        self._thread = threading.Thread(target=self._run, name="ktv-iptv-cache", daemon=True)
        self._thread.start()

    def activate(self, channel_id, channel_name):
        with self._lock:
            self._active = True
            self._channel = {"id": channel_id, "name": str(channel_name)[:100]}
            self._last_cache = None
            self._last_growth = time.monotonic()
            self._state = "monitoring"
            self._buffer = None
            self._stall_seconds = 0
            self._last_error = None

    def deactivate(self):
        with self._lock:
            self._active = False
            self._channel = None
            self._state = "idle"
            self._buffer = None
            self._stall_seconds = 0

    def status(self):
        with self._lock:
            return {
                "active": self._active,
                "channel": dict(self._channel) if self._channel else None,
                "state": self._state,
                "buffer_seconds": self._buffer,
                "stall_seconds": self._stall_seconds,
                "refreshing": self._refreshing,
                "refresh_count": self._refresh_count,
                "failure_count": self._failure_count,
                "last_error": self._last_error,
                "preserves_playback": True,
                "strategy": "MPV reconnect + background playlist refresh; no player reload",
            }

    def close(self):
        self._stop.set()
        self.deactivate()

    def _refresh_background(self):
        try:
            refresh_catalog(self.catalog_path)
            with self._lock:
                self._refresh_count += 1
                self._last_error = None
                self._state = "refreshed"
        except IPTVFreeCatalogError as exc:
            with self._lock:
                self._failure_count += 1
                self._last_error = str(exc)
                self._state = "refresh_failed"
        finally:
            with self._lock:
                self._refreshing = False

    def _run(self):
        while not self._stop.wait(self.SAMPLE_SECONDS):
            with self._lock:
                if not self._active or self._refreshing:
                    continue
            try:
                status = self.player.status()
                video = status.get("video") if isinstance(status, dict) else None
                buffer_value = video.get("buffer_seconds") if isinstance(video, dict) else None
                if type(buffer_value) not in (int, float):
                    continue
                now = time.monotonic()
                with self._lock:
                    if not self._active:
                        continue
                    self._buffer = round(max(0.0, float(buffer_value)), 2)
                    if self._last_cache is None or buffer_value > self._last_cache + 0.5:
                        self._last_growth = now
                    self._last_cache = float(buffer_value)
                    stagnant = max(0, int(now - self._last_growth))
                    self._stall_seconds = stagnant
                    low_and_stagnant = (buffer_value <= self.LOW_BUFFER_SECONDS and
                                         stagnant >= self.STALL_SECONDS)
                    cooldown_ok = now - self._last_refresh >= self.REFRESH_COOLDOWN
                    if low_and_stagnant and cooldown_ok and not self._refreshing:
                        self._refreshing = True
                        self._last_refresh = now
                        self._state = "refreshing_playlist"
                        threading.Thread(target=self._refresh_background,
                                        name="ktv-iptv-refresh", daemon=True).start()
                    elif not low_and_stagnant and self._state not in ("refreshing_playlist",):
                        self._state = "monitoring"
            except Exception:
                # Monitoring must never affect the playback thread/session.
                continue
