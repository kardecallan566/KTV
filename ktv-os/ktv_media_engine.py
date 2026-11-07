"""KTV Media Engine — experimental GStreamer playback core.

This module is deliberately isolated from the production NativePlayer (mpv).
It lets KTV validate the GStreamer runtime and exercise a playback pipeline
without changing the channels/UI that currently work. Integration is a later,
explicit step after testing on the Raspberry Pi 3.
"""
import threading
import time
from urllib.parse import urlsplit

from stream_urls import validate_stream_url, validate_pluto_url, StreamURLError


class MediaEngineError(RuntimeError):
    """A user-safe media engine failure."""


class KTVMediaEngine:
    """Small, observable GStreamer playbin controller (prototype).

    Requires PyGObject + GStreamer plugins on the host. Does not install them,
    launch a shell, or expose a GStreamer command/API to the browser.
    """

    def __init__(self, gst=None):
        self._lock = threading.RLock()
        self._gst = gst
        self._pipeline = None
        self._bus = None
        self._worker = None
        self._stop_event = threading.Event()
        self._source = None
        self._state = 'idle'
        self._error = None
        self._buffering = 0
        self._started_at = None
        self._last_event_at = None
        self._events = []

    @staticmethod
    def _load_gst():
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            Gst.init(None)
            return Gst
        except (ImportError, ValueError, RuntimeError) as exc:
            raise MediaEngineError(
                'GStreamer/PyGObject indisponivel. Instale os pacotes do engine experimental.'
            ) from exc

    @property
    def available(self):
        try:
            gst = self._gst or self._load_gst()
            return bool(gst.ElementFactory.find('playbin'))
        except MediaEngineError:
            return False

    def _validate_source(self, source):
        if not isinstance(source, str) or not source or source.startswith('-') or '\\0' in source:
            raise ValueError('Fonte de video invalida')
        parts = urlsplit(source)
        if parts.scheme in ('http', 'https'):
            try:
                if parts.hostname == 'ipv4.pluto.tv':
                    validate_pluto_url(source)
                else:
                    validate_stream_url(source)
            except StreamURLError as exc:
                raise ValueError(str(exc)) from exc
        elif parts.scheme or not source.startswith('/'):
            raise ValueError('Somente HTTP(S) e arquivos locais autorizados')
        return source

    def play(self, source, name='KTV stream'):
        source = self._validate_source(source)
        gst = self._gst or self._load_gst()
        with self._lock:
            self.stop()
            pipeline = gst.ElementFactory.make('playbin', 'ktv-playbin')
            if pipeline is None:
                raise MediaEngineError('Plugin GStreamer playbin nao encontrado')
            # playbin owns demux/decode selection; KTV owns lifecycle, state,
            # diagnostics and (in a later stage) recovery policy.
            pipeline.set_property('uri', source if source.startswith(('http://', 'https://'))
                                  else 'file://' + source)
            bus = pipeline.get_bus()
            self._pipeline = pipeline
            self._bus = bus
            self._source = name[:160] if isinstance(name, str) else 'KTV stream'
            self._state = 'starting'
            self._error = None
            self._buffering = 0
            self._started_at = time.monotonic()
            self._last_event_at = self._started_at
            self._events = []
            self._stop_event.clear()
            result = pipeline.set_state(gst.State.PLAYING)
            if result == gst.StateChangeReturn.FAILURE:
                self._pipeline = None
                self._bus = None
                self._state = 'error'
                raise MediaEngineError('GStreamer nao conseguiu iniciar a reproducao')
            self._worker = threading.Thread(target=self._watch_bus,
                                           name='ktv-gst-monitor', daemon=True)
            self._worker.start()
            return self.status()

    def _record(self, event, detail=None):
        now = time.monotonic()
        self._last_event_at = now
        self._events.append({'event': event, 'detail': str(detail)[:240] if detail else None,
                             'at_seconds': round(now - (self._started_at or now), 2)})
        self._events = self._events[-30:]

    def _watch_bus(self):
        gst = self._gst or self._load_gst()
        mask = (gst.MessageType.ERROR | gst.MessageType.EOS |
                gst.MessageType.BUFFERING | gst.MessageType.STATE_CHANGED |
                gst.MessageType.WARNING | gst.MessageType.ASYNC_DONE)
        while not self._stop_event.is_set():
            with self._lock:
                bus = self._bus
                pipeline = self._pipeline
            if bus is None or pipeline is None:
                return
            message = bus.timed_pop_filtered(250 * gst.MSECOND, mask)
            if message is None:
                continue
            with self._lock:
                if message.type == gst.MessageType.ERROR:
                    error, debug = message.parse_error()
                    self._state = 'error'
                    self._error = str(error)[:300]
                    self._record('error', debug or error)
                elif message.type == gst.MessageType.EOS:
                    self._state = 'ended'
                    self._record('eos')
                elif message.type == gst.MessageType.BUFFERING:
                    percent = message.parse_buffering()
                    self._buffering = max(0, min(100, int(percent)))
                    self._state = 'buffering' if percent < 100 else 'playing'
                    self._record('buffering', percent)
                elif message.type == gst.MessageType.ASYNC_DONE:
                    if self._state not in ('error', 'ended'):
                        self._state = 'playing'
                    self._record('async-done')
                elif message.type == gst.MessageType.WARNING:
                    warning, debug = message.parse_warning()
                    self._record('warning', debug or warning)
                elif message.type == gst.MessageType.STATE_CHANGED and message.src == pipeline:
                    old, new, pending = message.parse_state_changed()
                    self._record('state', '{}->{}'.format(old.value_nick, new.value_nick))

    def status(self):
        with self._lock:
            return {
                'engine': 'ktv-gstreamer-experimental',
                'available': self.available,
                'state': self._state,
                'source_name': self._source,
                'buffering_percent': self._buffering,
                'error': self._error,
                'elapsed_seconds': round(time.monotonic() - self._started_at, 1)
                    if self._started_at else 0,
                'last_event_seconds_ago': round(time.monotonic() - self._last_event_at, 1)
                    if self._last_event_at else None,
                'events': list(self._events),
            }

    def stop(self):
        with self._lock:
            pipeline = self._pipeline
            worker = self._worker
            self._stop_event.set()
            self._pipeline = None
            self._bus = None
            self._worker = None
            self._source = None
            self._buffering = 0
            if pipeline is not None:
                gst = self._gst or self._load_gst()
                pipeline.set_state(gst.State.NULL)
            self._state = 'idle'
        if worker and worker is not threading.current_thread():
            worker.join(timeout=1.0)
        return pipeline is not None

    def close(self):
        self.stop()
