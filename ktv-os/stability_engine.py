"""Conservative playback intelligence for KTV OS / Raspberry Pi 3.

Pure decision logic: no player commands, no hardware assumptions, easy to test.
"""
from collections import deque
from statistics import median
from pathlib import Path


PI3_PROFILE = {
    "name": "raspberry-pi-3",
    "quality": "economy",
    "decode": "default",
    "max_width": 1280,
    "max_height": 720,
    "max_fps": 30,
    "reason": "Perfil conservador para CPU/RAM limitadas; sem forçar decoder por hardware.",
}


class FrameTrend:
    """Classify cumulative mpv frame counters using deltas over a rolling window."""
    def __init__(self, window=6):
        self.window = max(3, int(window))
        self.samples = deque(maxlen=self.window)
        self.last_vo = None
        self.last_decoder = None

    def reset(self):
        self.samples.clear()
        self.last_vo = self.last_decoder = None

    def update(self, vo_dropped, decoder_dropped, now):
        if type(vo_dropped) is not int or vo_dropped < 0:
            vo_dropped = None
        if type(decoder_dropped) is not int or decoder_dropped < 0:
            decoder_dropped = None
        vo_delta = max(0, vo_dropped - self.last_vo) if vo_dropped is not None and self.last_vo is not None else 0
        dec_delta = max(0, decoder_dropped - self.last_decoder) if decoder_dropped is not None and self.last_decoder is not None else 0
        if vo_dropped is not None:
            self.last_vo = vo_dropped
        if decoder_dropped is not None:
            self.last_decoder = decoder_dropped
        self.samples.append({"at": now, "vo": vo_delta, "decoder": dec_delta})
        vo_rate = sum(x["vo"] for x in self.samples)
        decoder_rate = sum(x["decoder"] for x in self.samples)
        count = len(self.samples)
        if count < 3:
            level = "warming"
        elif decoder_rate >= 12 or vo_rate >= 30:
            level = "critical"
        elif decoder_rate >= 4 or vo_rate >= 12:
            level = "warning"
        else:
            level = "stable"
        return {"level": level, "samples": count, "vo_delta": vo_delta,
                "decoder_delta": dec_delta, "vo_window": vo_rate,
                "decoder_window": decoder_rate}


def diagnose_audio(video, previous_audio_pts=None, previous_time_pos=None):
    """Distinguish no track, missing telemetry and likely stalled audio."""
    if not isinstance(video, dict):
        return {"state": "unknown", "message": "Telemetria de áudio indisponível."}
    if video.get("audio_track") is False:
        return {"state": "no_track", "message": "Nenhuma faixa de áudio selecionada."}
    pts = video.get("audio_pts")
    pos = video.get("time_pos")
    if pts is None:
        return {"state": "unknown", "message": "mpv não forneceu audio-pts; não é possível confirmar silêncio."}
    if isinstance(previous_audio_pts, (int, float)) and isinstance(previous_time_pos, (int, float)):
        timeline_delta = pos - previous_time_pos if isinstance(pos, (int, float)) else 0
        audio_delta = pts - previous_audio_pts
        if timeline_delta > 2 and audio_delta < 0.15:
            return {"state": "suspect_stalled", "message": "Vídeo avança, mas audio-pts quase não progride."}
    return {"state": "track_active", "message": "Faixa selecionada e relógio de áudio disponível; isso não comprova som audível."}


class SmartDecoder:
    """A single conservative fallback, cooldown and explicit recovery policy."""
    COOLDOWN = 180
    def __init__(self, clock):
        self.clock = clock
        self.last_switch = 0
        self.switches = 0
        self.reason = None

    def recommend(self, metrics, current="default"):
        if current == "compatible":
            return {"action": "hold", "decode": current, "reason": "Fallback já ativo; sem alternância automática de volta."}
        if self.switches >= 1:
            return {"action": "hold", "decode": current, "reason": "Fallback automático limitado a uma tentativa por sessão."}
        if self.last_switch and self.clock() - self.last_switch < self.COOLDOWN:
            return {"action": "hold", "decode": current, "reason": "Cooldown do decoder ativo."}
        video = metrics.get("video") or {}
        trend = metrics.get("frame_trend") or {}
        visual = metrics.get("visual") or {}
        if visual.get("state") == "black_or_missing" and video.get("video_track") and trend.get("level") in ("warning", "critical"):
            return {"action": "fallback", "decode": "compatible", "reason": "Saída visual ausente junto a pressão de frames."}
        if trend.get("level") == "critical" and trend.get("decoder_window", 0) >= 12:
            return {"action": "fallback", "decode": "compatible", "reason": "Queda de frames do decoder persistente."}
        return {"action": "hold", "decode": current, "reason": "Evidências insuficientes para trocar decoder."}

    def record_switch(self, reason):
        self.last_switch = self.clock()
        self.switches += 1
        self.reason = str(reason)[:160]


def visual_state(video, timeline_advanced):
    """Use mpv output + timeline as a rendered-output proxy; never claim HDMI pixels."""
    if not isinstance(video, dict):
        return {"state": "unknown", "confidence": "low", "message": "Sem telemetria de vídeo."}
    if video.get("video_track") is False:
        return {"state": "audio_only", "confidence": "high", "message": "Fonte sem faixa de vídeo ativa."}
    if video.get("video_rendered") and timeline_advanced:
        return {"state": "progressing", "confidence": "medium", "message": "Saída de vídeo inicializada e timeline avançando (proxy de frames apresentados)."}
    if video.get("video_track") and not video.get("video_rendered"):
        return {"state": "black_or_missing", "confidence": "low", "message": "Faixa de vídeo existe, mas saída de vídeo não foi confirmada."}
    return {"state": "unknown", "confidence": "low", "message": "Não há evidência suficiente para avaliar frames."}


def detect_playback_profile(model_path="/proc/device-tree/model"):
    """Select conservative defaults only when Raspberry Pi 3 is explicitly detected."""
    try:
        model = Path(model_path).read_bytes().decode("ascii", "ignore").replace("\\x00", "").strip()
    except OSError:
        model = ""
    if "Raspberry Pi 3" in model or "BCM2837" in model:
        return dict(PI3_PROFILE)
    return {"name": "generic", "quality": "balanced", "decode": "default",
            "max_width": None, "max_height": None, "max_fps": None,
            "reason": "Hardware não identificado; perfil padrão equilibrado."}
