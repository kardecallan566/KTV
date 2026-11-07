"""KTV Media Engine — experimental GStreamer core with progress/recovery.

This is intentionally not connected to the production NativePlayer (mpv).
"""
import threading
import time
from urllib.parse import urlsplit

from stream_urls import validate_stream_url, validate_pluto_url, StreamURLError
from ktv_stream_recovery import KTVStreamRecovery


class MediaEngineError(RuntimeError):
    """A user-safe media engine failure."""


class KTVMediaEngine:
    """Observable GStreamer playbin controller with experimental watchdog."""

    def __init__(self, gst=None, recovery_enabled=True, stall_timeout=45.0,
                 max_recoveries=3):
        self._lock = threading.RLock()
        self._gst = gst
        self._pipeline = None
        self._bus = None
        self._worker = None
        self._stop_event = threading.Event()
        self._source_uri = None
        self._source = None
        self._state = 'idle'
        self._error = None
        self._buffering = 0
        self._started_at = None
        self._last_event_at = None
        self._last_position_ns = None
        self._position_supported = False
        self._events = []
        self._recovery_enabled = bool(recovery_enabled)
        self._recovery = KTVStreamRecovery(
            self._recover_pipeline, stall_timeout=stall_timeout,
            poll_interval=2.0, max_recoveries=max_recoveries, cooldown=10.0)

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
        self.stop()
        with self._lock:
            pipeline = gst.ElementFactory.make('playbin', 'ktv-playbin')
            if pipeline is None:
                raise MediaEngineError('Plugin GStreamer playbin nao encontrado')
            uri = source if source.startswith(('http://', 'https://')) else 'file://' + source
            pipeline.set_property('uri', uri)
            self._pipeline = pipeline
            self._bus = pipeline.get_bus()
            self._source_uri = uri
            self._source = name[:160] if isinstance(name, str) else 'KTV stream'
            self._state = 'starting'
            self._error = None
            self._buffering = 0
            self._last_position_ns = None
            self._position_supported = False
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
            if self._recovery_enabled:
                self._recovery.start()
            self._record('play-request', self._source)
            return self.status()

    def _record(self, event, detail=None):
        now = time.monotonic()
        self._last_event_at = now
        self._events.append({'event': event, 'detail': str(detail)[:240] if detail is not None else None,
                             'at_seconds': round(now - (self._started_at or now), 2)})
        self._events = self._events[-40:]

    def _query_progress(self, gst, pipeline):
        try:
            ok, position = pipeline.query_position(gst.Format.TIME)
            if ok and isinstance(position, int) and position >= 0:
                with self._lock:
                    previous = self._last_position_ns
                    self._last_position_ns = position
                    self._position_supported = True
                if previous is None or position != previous:
                    self._recovery.report_progress(position)
                return
        except Exception as exc:
            with self._lock:
                self._position_supported = False
                self._record('position-query-warning', exc)

    def _watch_bus(self):
        gst = self._gst or self._load_gst()
        mask = (gst.MessageType.ERROR | gst.MessageType.EOS |
                gst.MessageType.BUFFERING | gst.MessageType.STATE_CHANGED |
                gst.MessageType.WARNING | gst.MessageType.ASYNC_DONE)
        last_query = 0.0
        while not self._stop_event.is_set():
            with self._lock:
                bus, pipeline = self._bus, self._pipeline
            if bus is None or pipeline is None:
                return
            message = bus.timed_pop_filtered(250 * gst.MSECOND, mask)
            now = time.monotonic()
            if now - last_query >= 1.0:
                self._query_progress(gst, pipeline)
                last_query = now
            if message is None:
                continue
            if message.type == gst.MessageType.ERROR:
                error, debug = message.parse_error()
                with self._lock:
                    self._state = 'error'
                    self._error = str(error)[:300]
                    self._record('error', debug or error)
                if self._recovery_enabled:
                    self._recovery.report_error(str(error))
            elif message.type == gst.MessageType.EOS:
                with self._lock:
                    self._state = 'ended'
                    self._record('eos')
                self._recovery.pause()
            elif message.type == gst.MessageType.BUFFERING:
                percent = message.parse_buffering()
                with self._lock:
                    self._buffering = max(0, min(100, int(percent)))
                    self._state = 'buffering' if percent < 100 else 'playing'
                    self._record('buffering', percent)
            elif message.type == gst.MessageType.ASYNC_DONE:
                with self._lock:
                    if self._state not in ('error', 'ended'):
                        self._state = 'playing'
                    self._record('async-done')
            elif message.type == gst.MessageType.WARNING:
                warning, debug = message.parse_warning()
                with self._lock:
                    self._record('warning', debug or warning)
            elif message.type == gst.MessageType.STATE_CHANGED and message.src == pipeline:
                old, new, pending = message.parse_state_changed()
                with self._lock:
                    self._record('state', '{}->{}'.format(old.value_nick, new.value_nick))

    def pause(self):
        gst = self._gst or self._load_gst()
        with self._lock:
            pipeline = self._pipeline
            if pipeline is None:
                return False
            result = pipeline.set_state(gst.State.PAUSED)
            if result == gst.StateChangeReturn.FAILURE:
                return False
            self._state = 'paused'
            self._record('pause')
        self._recovery.pause()
        return True

    def resume(self):
        gst = self._gst or self._load_gst()
        with self._lock:
            pipeline = self._pipeline
            if pipeline is None:
                return False
            result = pipeline.set_state(gst.State.PLAYING)
            if result == gst.StateChangeReturn.FAILURE:
                return False
            self._state = 'starting'
            self._record('resume')
        self._recovery.resume()
        return True

    def _recover_pipeline(self):
        gst = self._gst or self._load_gst()
        with self._lock:
            pipeline = self._pipeline
            if pipeline is None or self._stop_event.is_set():
                return False
            self._error = None
            self._buffering = 0
            self._state = 'recovering'
            self._record('pipeline-recovery-request')
        # State transitions happen on the recovery worker, outside the bus loop.
        if pipeline.set_state(gst.State.READY) == gst.StateChangeReturn.FAILURE:
            return False
        time.sleep(0.35)
        result = pipeline.set_state(gst.State.PLAYING)
        with self._lock:
            if result != gst.StateChangeReturn.FAILURE:
                self._state = 'starting'
                self._last_position_ns = None
                self._record('pipeline-recovery-playing')
                return True
            self._state = 'error'
            self._record('pipeline-recovery-failed')
            return False

    def status(self):
        with self._lock:
            recovery = self._recovery.status()
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
                'position_query_supported': self._position_supported,
                'recovery': recovery,
                'events': list(self._events),
            }

    def stop(self):
        self._recovery.stop()
        with self._lock:
            pipeline, worker = self._pipeline, self._worker
            self._stop_event.set()
            self._pipeline = None
            self._bus = None
            self._worker = None
            self._source_uri = None
            self._source = None
            self._buffering = 0
            if pipeline is not None:
                gst = self._gst or self._load_gst()
                pipeline.set_state(gst.State.NULL)
            self._state = 'idle'
            self._record('stop')
        if worker and worker is not threading.current_thread():
            worker.join(timeout=1.0)
        return pipeline is not None

    def close(self):
        self.stop()
