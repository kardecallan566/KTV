"""Platform-neutral contracts for KTV OS runtimes.

Adapters implement these protocols. The current AMD64 runtime is intentionally
not forced to adopt them all at once; migration is incremental and test-led.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence, runtime_checkable


CONTRACTS_VERSION = "1.0"


@dataclass(frozen=True)
class Capability:
    """A feature reported by a real adapter, never inferred from its platform."""

    name: str
    available: bool
    source: str = "unknown"
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationResult:
    """Stable result envelope for operations that may be unsupported or fail."""

    ok: bool
    code: str
    message: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaStatus:
    available: bool
    playing: bool = False
    paused: bool = False
    source_name: str | None = None
    position_seconds: float | None = None
    duration_seconds: float | None = None
    video_width: int | None = None
    video_height: int | None = None
    fps: float | None = None
    codec: str | None = None
    hardware_decoder: str | None = None
    dropped_frames: int | None = None
    buffering: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class RemoteKeyEvent:
    key: str
    action: Literal["pressed", "released"]
    source: str = "unknown"
    repeat: bool = False


@dataclass(frozen=True)
class DeviceInfo:
    platform: str
    architecture: str
    model: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    memory_total_mb: int | None = None
    cpu_temperature_c: float | None = None
    gpu_devices: tuple[str, ...] = ()
    display_connectors: tuple[str, ...] = ()


@runtime_checkable
class MediaPlayer(Protocol):
    def capabilities(self) -> Sequence[Capability]: ...
    def status(self) -> MediaStatus: ...
    def play(self, source: str, name: str, profile: str = "balanced") -> OperationResult: ...
    def pause(self) -> OperationResult: ...
    def resume(self) -> OperationResult: ...
    def seek(self, position_seconds: float) -> OperationResult: ...
    def stop(self) -> OperationResult: ...


@runtime_checkable
class RemoteInput(Protocol):
    def capabilities(self) -> Sequence[Capability]: ...
    def subscribe(self, callback: Callable[[RemoteKeyEvent], None]) -> Callable[[], None]: ...


@runtime_checkable
class DeviceInfoProvider(Protocol):
    def get_info(self) -> DeviceInfo: ...


@runtime_checkable
class DisplayAdapter(Protocol):
    def capabilities(self) -> Sequence[Capability]: ...
    def list_outputs(self) -> OperationResult: ...
    def set_mode(self, output_id: str, mode: str) -> OperationResult: ...
    def rollback(self) -> OperationResult: ...


@runtime_checkable
class AudioOutputAdapter(Protocol):
    def capabilities(self) -> Sequence[Capability]: ...
    def list_outputs(self) -> OperationResult: ...
    def set_volume(self, output_id: str, volume: int) -> OperationResult: ...
    def set_muted(self, output_id: str, muted: bool) -> OperationResult: ...


@runtime_checkable
class NetworkAdapter(Protocol):
    def status(self) -> OperationResult: ...
    def scan_wifi(self) -> OperationResult: ...
    def connect_wifi(self, ssid: str, password: str) -> OperationResult: ...


@runtime_checkable
class StorageAdapter(Protocol):
    def list_volumes(self) -> OperationResult: ...
    def backup(self, source_id: str, destination_id: str) -> OperationResult: ...


@runtime_checkable
class SystemPowerAdapter(Protocol):
    def request(self, action: Literal["shutdown", "reboot"]) -> OperationResult: ...


@runtime_checkable
class AppLifecycleAdapter(Protocol):
    def health(self) -> OperationResult: ...
    def restart(self) -> OperationResult: ...
