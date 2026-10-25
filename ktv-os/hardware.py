"""KTV OS hardware integration (Linux X11 and PulseAudio).

Video mode change is temporary until confirmed, with a 20-second rollback.
Only output names and modes *reported by xrandr* are accepted. Audio commands
accept only discovered PulseAudio sinks. No shell or firmware modifications.
"""
import re
import shutil
import subprocess
import threading
import secrets
import time
import display_layout

MODE_RE = re.compile(r'^(\d{3,5})x(\d{3,5})$')
OUTPUT_RE = re.compile(r'^([A-Za-z0-9_.-]+)\s+connected(?:\s|$)')
SINK_RE = re.compile(r'^\d+\s+(\S+)\s+')
DEFAULT_RE = re.compile(r'^Default Sink:\s*(\S+)\s*$', re.M)
PERCENT_RE = re.compile(r'(\d{1,3})%')
TIMEOUT_SECONDS = 20


class HardwareError(ValueError):
    pass


class HardwareManager:
    def __init__(self, runner=None, timer_factory=None):
        self.runner = runner or subprocess.run
        self.timer_factory = timer_factory or threading.Timer
        self.lock = threading.RLock()
        self.pending = None
        self.timer = None

    def _exec(self, args):
        if not shutil.which(args[0]):
            raise HardwareError('Ferramenta {} indisponivel no sistema'.format(args[0]))
        try:
            outcome = self.runner(args, capture_output=True, text=True, timeout=4, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HardwareError('Falha ao consultar hardware: {}'.format(exc))
        if outcome.returncode != 0:
            raise HardwareError((outcome.stderr or 'Comando nao suportado neste dispositivo').strip()[:180])
        return outcome.stdout

    def _screens(self):
        output = self._exec(['xrandr', '--query'])
        screens, current = [], None
        for line in output.splitlines():
            match = OUTPUT_RE.match(line)
            if match:
                name = match.group(1)
                current = {'name': name, 'modes': [], 'current': None,
                           'hdmi': name.upper().startswith(('HDMI', 'DP'))}
                screens.append(current)
                continue
            if current is None:
                continue
            parts = line.strip().split()
            if not parts or not MODE_RE.fullmatch(parts[0]):
                continue
            mode = parts[0]
            width, height = [int(x) for x in mode.split('x')]
            if not 640 <= width <= 7680 or not 480 <= height <= 4320:
                continue
            if mode not in current['modes']:
                current['modes'].append(mode)
            if any('*' in part for part in parts[1:]):
                current['current'] = mode
        return screens

    def _audio(self):
        sinks_raw = self._exec(['pactl', 'list', 'short', 'sinks'])
        info = self._exec(['pactl', 'info'])
        sinks = []
        for line in sinks_raw.splitlines():
            match = SINK_RE.match(line)
            if match:
                sinks.append({'name': match.group(1),
                              'hdmi': 'hdmi' in match.group(1).lower()})
        default_match = DEFAULT_RE.search(info)
        current = default_match.group(1) if default_match else ''
        volume = None
        muted = None
        try:
            vol = self._exec(['pactl', 'get-sink-volume', '@DEFAULT_SINK@'])
            match = PERCENT_RE.search(vol)
            if match:
                volume = int(match.group(1))
            mute = self._exec(['pactl', 'get-sink-mute', '@DEFAULT_SINK@'])
            muted = mute.strip().lower().endswith('yes')
        except HardwareError:
            pass
        return {'available': True, 'sinks': sinks, 'default': current,
                'volume': volume, 'muted': muted}

    def status(self):
        with self.lock:
            try:
                screens = self._screens()
                display_error = ''
            except HardwareError as exc:
                screens, display_error = [], str(exc)
            try:
                audio = self._audio()
                audio_error = ''
            except HardwareError as exc:
                audio = {'available': False, 'sinks': [], 'default': '',
                         'volume': None, 'muted': None}
                audio_error = str(exc)
            remaining = max(0, int(self.pending['deadline'] - time.monotonic())) if self.pending else 0
            layout = []
            if not display_error:
                try:
                    layout = display_layout.outputs(self._exec(['xrandr', '--query']))
                except HardwareError:
                    pass
            return {
                'display': {'available': not bool(display_error), 'outputs': screens,
                            'layout': layout,
                            'error': display_error,
                            'pending': bool(self.pending), 'remaining': remaining},
                'audio': dict(audio, error=audio_error)
            }

    def preview(self, output, mode):
        with self.lock:
            if self.pending:
                raise HardwareError('Confirme ou cancele a mudanca de video anterior')
            if not isinstance(output, str) or not isinstance(mode, str):
                raise HardwareError('Selecao HDMI invalida')
            screens = self._screens()
            selected = next((x for x in screens if x['name'] == output), None)
            if not selected or not selected['hdmi'] or not selected['current']:
                raise HardwareError('Saida HDMI/DisplayPort ativa nao encontrada')
            if mode not in selected['modes'] or not MODE_RE.fullmatch(mode):
                raise HardwareError('Resolucao nao anunciada por este monitor')
            prior = selected['current']
            if mode == prior:
                return {'pending': False, 'message': 'A resolucao ja esta ativa'}
            self._exec(['xrandr', '--output', output, '--mode', mode])
            token = secrets.token_hex(12)
            self.pending = {'token': token, 'output': output, 'previous': prior,
                            'deadline': time.monotonic() + TIMEOUT_SECONDS}
            self.timer = self.timer_factory(TIMEOUT_SECONDS, self._rollback)
            self.timer.daemon = True
            self.timer.start()
            return {'pending': True, 'token': token, 'seconds': TIMEOUT_SECONDS,
                    'message': 'Confirme a imagem antes de o temporizador encerrar'}

    def preview_layout(self, output, kind):
        with self.lock:
            if self.pending:
                raise HardwareError('Confirme ou cancele o ajuste de imagem anterior')
            if not isinstance(output, str) or not isinstance(kind, str):
                raise HardwareError('Seleção de HDMI inválida')
            current = display_layout.outputs(self._exec(['xrandr', '--query']))
            try:
                args = display_layout.layout_command(current, output, kind)
                restore = display_layout.restore_command(current)
            except ValueError as exc:
                raise HardwareError(str(exc))
            self._exec(args)
            token = secrets.token_hex(12)
            self.pending = {'token': token, 'restore': restore,
                            'deadline': time.monotonic() + TIMEOUT_SECONDS}
            self.timer = self.timer_factory(TIMEOUT_SECONDS, self._rollback)
            self.timer.daemon = True
            self.timer.start()
            return {'pending': True, 'token': token, 'seconds': TIMEOUT_SECONDS,
                    'message': 'Confirme o ajuste HDMI para mantê-lo nesta sessão'}

    def _rollback(self):
        with self.lock:
            previous = self.pending
            self.pending = None
            self.timer = None
            if previous:
                try:
                    if 'restore' in previous:
                        self._exec(previous['restore'])
                    else:
                        self._exec(['xrandr', '--output', previous['output'],
                                    '--mode', previous['previous']])
                except HardwareError:
                    pass

    def confirm(self, token):
        with self.lock:
            if not self.pending or not isinstance(token, str) or token != self.pending['token']:
                raise HardwareError('Confirmacao expirada ou invalida')
            if time.monotonic() >= self.pending['deadline']:
                self._rollback()
                raise HardwareError('Tempo encerrado, resolucao anterior recuperada')
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.pending = None
            return {'pending': False, 'message': 'Resolucao confirmada para esta sessao'}

    def cancel(self):
        self._rollback()
        return {'pending': False, 'message': 'Resolucao anterior restaurada'}

    def choose_audio(self, sink):
        if not isinstance(sink, str):
            raise HardwareError('Saida de audio invalida')
        with self.lock:
            available = {item['name'] for item in self._audio()['sinks']}
            if sink not in available:
                raise HardwareError('Saida de audio nao encontrada')
            self._exec(['pactl', 'set-default-sink', sink])
            return {'message': 'Saida de audio selecionada'}

    def set_volume(self, volume):
        if type(volume) is not int or not 0 <= volume <= 100:
            raise HardwareError('Volume deve estar entre 0 e 100')
        with self.lock:
            self._exec(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '{}%'.format(volume)])
            return {'message': 'Volume ajustado para {}%'.format(volume)}

    def toggle_mute(self):
        with self.lock:
            self._exec(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', 'toggle'])
            return {'message': 'Estado de mudo alterado'}

    def close(self):
        self.cancel()
