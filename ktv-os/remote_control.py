"""PIN-paired, LAN-only navigation remote for the KTV display."""
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque


class RemoteControl:
    ACTIONS = frozenset({
        'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
        'accept', 'back', 'home', 'stop',
        'mouse_move', 'mouse_left', 'mouse_right', 'scroll_up', 'scroll_down',
        'channels', 'tv', 'iptv', 'movies', 'sports', 'news', 'cartoons',
    })

    def __init__(self):
        self.pin = '{:06d}'.format(secrets.randbelow(1000000))
        self._lock = threading.RLock()
        self._sessions = {}
        self._attempts = defaultdict(deque)
        self._events = deque(maxlen=100)
        self._sequence = 0

    def pair(self, pin, address):
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[address]
            while attempts and now - attempts[0] > 300:
                attempts.popleft()
            if len(attempts) >= 8:
                raise ValueError('Muitas tentativas. Aguarde cinco minutos e tente novamente.')
            attempts.append(now)
            supplied = str(pin or '')
            if not hmac.compare_digest(supplied, self.pin):
                raise ValueError('Código incorreto. Confira o código exibido na TV.')
            token = secrets.token_urlsafe(32)
            self._sessions[token] = now + 8 * 60 * 60
            return token

    def command(self, token, action, dx=0, dy=0):
        now = time.monotonic()
        with self._lock:
            expiry = self._sessions.get(str(token or ''))
            if expiry is None or expiry <= now:
                self._sessions.pop(str(token or ''), None)
                raise ValueError('Controle não conectado. Digite novamente o código da TV.')
            if type(action) is not str or action not in self.ACTIONS:
                raise ValueError('Comando não permitido.')
            if action == 'mouse_move':
                if type(dx) is not int or type(dy) is not int or abs(dx) > 1000 or abs(dy) > 1000:
                    raise ValueError('Movimento do mouse invalido.')
                return {'ok': True, 'action': action, 'dx': dx, 'dy': dy}
            if action in ('mouse_left', 'mouse_right', 'scroll_up', 'scroll_down'):
                return {'ok': True, 'action': action}
            self._sequence += 1
            self._events.append({'sequence': self._sequence, 'action': action})
            return {'ok': True, 'sequence': self._sequence}

    def events_since(self, after):
        with self._lock:
            events = [event for event in self._events if event['sequence'] > after]
            return {'events': events, 'last': self._sequence}
