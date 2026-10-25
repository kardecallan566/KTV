"""Lightweight Pluto TV recovery controller for expiring HLS sessions.

Background checks run only for a user-selected Pluto channel. Never proxy
streams, refresh credentials without a playback request, or bypass DRM.
"""
import threading
import time

CHECK_INTERVAL=5
STALL_SECONDS=75
START_GRACE=90
RETRY_DELAYS=(3, 8, 20, 45, 90, 120)
MAX_FAILURES=7
USER_QUIT_CODE=77


class PlutoRecovery:
    def __init__(self, catalog, player, clock=None, threaded=True):
        self.catalog=catalog
        self.player=player
        self.clock=clock or time.monotonic
        self.lock=threading.RLock()
        self._stop=threading.Event()
        self.generation=0
        self.session=None
        self.phase='idle'
        self.issue=None
        self.attempts=0
        self.deadline=0
        self.last_progress=0
        self.last_pos=None
        self.started=0
        self.thread=None
        if threaded:
            self.thread=threading.Thread(target=self._loop, daemon=True, name='ktv-pluto-recovery')
            self.thread.start()

    def _loop(self):
        while not self._stop.wait(CHECK_INTERVAL):
            self.tick()

    def activate(self, ident, quality, decode):
        # Caller must first validate the channel ID and start the native mpv.
        with self.lock:
            self.generation+=1
            self.session=(ident,quality,decode)
            self.phase='playing'
            self.issue=None
            self.attempts=0
            self.started=self.clock()
            self.last_progress=self.started
            self.last_pos=None
            self.deadline=0

    def cancel(self):
        with self.lock:
            self.generation+=1
            self.session=None
            self.phase='idle'
            self.issue=None
            self.attempts=0
            self.last_pos=None
            self.deadline=0

    def status(self):
        with self.lock:
            return {
                'active':self.session is not None,
                'phase':self.phase,
                'attempts':self.attempts,
                'retry_seconds':max(0,round(self.deadline-self.clock())) if self.phase=='waiting' else 0,
                'message':self.issue,
            }

    def tick(self):
        with self.lock:
            if not self.session or self._stop.is_set():
                return
            now=self.clock()
            if self.phase=='waiting':
                if now<self.deadline:return
                self.phase='recovering'
            elif self.phase in ('recovering','attention'):
                return
            else:
                # The player gives us the *current* video state, not a stale URL.
                info=self.player.status()
                if info.get('playing'):
                    video=info.get('video')
                    if not isinstance(video,dict):
                        return  # No IPC / telemetry: do not kill healthy playback.
                    if video.get('paused') is True:
                        self.last_progress=now
                        return
                    pos=video.get('time_pos')
                    if type(pos) in (int,float):
                        if self.last_pos is None or pos>self.last_pos+0.2:
                            self.last_pos=pos
                            self.last_progress=now
                            if now-self.started>=40:
                                self.attempts=0
                                self.issue=None
                                self.phase='playing'
                        elif pos<self.last_pos-5:  # a live timeline may wrap
                            self.last_pos=pos
                            self.last_progress=now
                    if video.get('eof_reached') is True:
                        self.issue='O servidor terminou a playlist ao vivo; buscando sinal atualizado.'
                    elif pos is None or now-self.started<START_GRACE or now-self.last_progress<STALL_SECONDS:
                        return
                    else:
                        self.issue='A reprodução ficou sem avanço; tentando reconectar.'
                elif info.get('exit_code')==USER_QUIT_CODE:
                    self.cancel()
                    return
                else:
                    self.issue='A transmissão foi interrompida; tentando restabelecer.'
                self.phase='recovering'
            gen=self.generation
            session=self.session
            if self.attempts>=MAX_FAILURES:
                self.phase='attention'
                self.issue='Muitas tentativas sem sinal. Verifique a rede ou tente novamente manualmente.'
                return
            self.attempts+=1

        # Network fetch must never hold the session lock: Stop must remain responsive.
        ident,quality,decode=session
        try:
            url,title=self.catalog.play_url(ident,force_refresh=True)
        except (OSError,ValueError,RuntimeError):
            self._failure(gen,'Não foi possível atualizar a transmissão Pluto TV.')
            return
        with self.lock:
            if gen!=self.generation or self.session!=session or self._stop.is_set():
                return
            try:
                from player import NativePlayer
                if isinstance(self.player,NativePlayer):
                    self.player.play(url,title,quality=quality,decode=decode)
                else:
                    self.player.play(url,title)
            except (OSError,ValueError,RuntimeError):
                self._failure(gen,'O player não conseguiu reabrir a transmissão.')
                return
            now=self.clock()
            self.started=now
            self.last_progress=now
            self.last_pos=None
            self.deadline=0
            self.phase='playing'
            self.issue='Transmissão reconectada automaticamente.'

    def _failure(self,gen,message):
        with self.lock:
            if gen!=self.generation or not self.session:
                return
            self.issue=message
            if self.attempts>=MAX_FAILURES:
                self.phase='attention'
                self.issue='Não foi possível recuperar o canal. Confira conexão e disponibilidade.'
                return
            seconds=RETRY_DELAYS[min(self.attempts-1,len(RETRY_DELAYS)-1)]
            self.deadline=self.clock()+seconds
            self.phase='waiting'

    def close(self):
        self._stop.set()
        self.cancel()
        if self.thread is not None and threading.current_thread()!=self.thread:
            self.thread.join(timeout=2)
