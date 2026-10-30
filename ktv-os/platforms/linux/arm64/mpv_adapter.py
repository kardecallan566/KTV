"""Contract adapter around the KTV OS native mpv player.

The adapter keeps mpv's Unix IPC private and exposes only fixed, semantic
operations. It does not accept arbitrary mpv commands from the UI.
"""
from __future__ import annotations

import json
import math
import socket
from typing import Any

from core.contracts import Capability, MediaStatus, OperationResult


class MpvMediaPlayerAdapter:
    def __init__(self, player: Any, socket_module: Any = socket) -> None:
        self.player = player
        self.socket_module = socket_module

    def capabilities(self) -> list[Capability]:
        available = bool(getattr(self.player, "available", False))
        has_ipc = hasattr(self.socket_module, "AF_UNIX")
        return [
            Capability(name="play", available=available, source="mpv"),
            Capability(name="pause", available=available and has_ipc, source="mpv-ipc"),
            Capability(name="resume", available=available and has_ipc, source="mpv-ipc"),
            Capability(name="seek", available=available and has_ipc, source="mpv-ipc"),
            Capability(name="stop", available=available, source="mpv"),
        ]

    @staticmethod
    def _number(value: object) -> int | float | None:
        if type(value) not in (int, float) or not math.isfinite(value):
            return None
        return value

    def status(self) -> MediaStatus:
        raw = self.player.status()
        raw = raw if isinstance(raw, dict) else {}
        video = raw.get("video")
        video = video if isinstance(video, dict) else {}
        width = video.get("width")
        height = video.get("height")
        dropped = video.get("dropped_frames")
        return MediaStatus(
            available=raw.get("available") is True,
            playing=raw.get("playing") is True,
            paused=video.get("paused") is True,
            source_name=raw.get("name") if isinstance(raw.get("name"), str) else None,
            position_seconds=self._number(video.get("time_pos")),
            duration_seconds=None,
            video_width=width if type(width) is int and width > 0 else None,
            video_height=height if type(height) is int and height > 0 else None,
            fps=self._number(video.get("fps")),
            codec=video.get("codec") if isinstance(video.get("codec"), str) else None,
            hardware_decoder=(
                video.get("hardware_decoder")
                if isinstance(video.get("hardware_decoder"), str) and video.get("hardware_decoder")
                else None
            ),
            dropped_frames=(
                dropped if type(dropped) is int and dropped >= 0 else None
            ),
            buffering=False,
            error_code=(
                "player_exited"
                if not raw.get("playing") and raw.get("exit_code") is not None
                else None
            ),
        )

    def play(self, source: str, name: str, profile: str = "balanced") -> OperationResult:
        try:
            result = self.player.play(source, name, quality=profile)
        except (RuntimeError, ValueError) as exc:
            return OperationResult(ok=False, code="player_error", message=str(exc))
        playing = isinstance(result, dict) and result.get("playing") is True
        return OperationResult(
            ok=True,
            code="playing" if playing else "started",
            data={"playing": playing},
        )

    def _send_command(self, command: list[object]) -> OperationResult:
        ipc_path = getattr(self.player, "ipc_path", None)
        if not ipc_path or not hasattr(self.socket_module, "AF_UNIX"):
            return OperationResult(
                ok=False,
                code="not_available",
                message="O controle mpv so fica disponivel durante uma sessao ativa.",
            )
        request = {"command": command, "request_id": 1}
        try:
            with self.socket_module.socket(
                self.socket_module.AF_UNIX,
                self.socket_module.SOCK_STREAM,
            ) as client:
                client.settimeout(0.6)
                client.connect(ipc_path)
                client.sendall((json.dumps(request) + "\n").encode("utf-8"))
                received = bytearray()
                while b"\n" not in received and len(received) < 8192:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    received.extend(chunk)
            for line in bytes(received).splitlines():
                try:
                    reply = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if isinstance(reply, dict) and reply.get("request_id") == 1:
                    if reply.get("error") == "success":
                        return OperationResult(ok=True, code="command_sent")
                    return OperationResult(
                        ok=False,
                        code="player_error",
                        message="O mpv recusou a operacao solicitada.",
                    )
        except OSError:
            return OperationResult(
                ok=False,
                code="not_available",
                message="Nao foi possivel acessar a sessao local do mpv.",
            )
        return OperationResult(
            ok=False,
            code="timeout",
            message="O mpv nao confirmou a operacao no tempo esperado.",
        )

    def pause(self) -> OperationResult:
        return self._send_command(["set_property", "pause", True])

    def resume(self) -> OperationResult:
        return self._send_command(["set_property", "pause", False])

    def seek(self, position_seconds: float) -> OperationResult:
        if (
            type(position_seconds) not in (int, float)
            or not math.isfinite(position_seconds)
            or position_seconds < 0
        ):
            return OperationResult(
                ok=False,
                code="invalid_argument",
                message="A posicao de busca deve ser um numero finito e nao negativo.",
            )
        return self._send_command(["seek", float(position_seconds), "absolute+exact"])

    def stop(self) -> OperationResult:
        try:
            stopped = self.player.stop()
        except OSError:
            return OperationResult(ok=False, code="player_error", message="Falha ao parar o mpv.")
        return OperationResult(
            ok=True,
            code="stopped" if stopped else "already_stopped",
        )
