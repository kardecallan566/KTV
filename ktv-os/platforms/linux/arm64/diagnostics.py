#!/usr/bin/env python3
"""Read-only ARM64 host preflight for KTV OS.

This utility does not install packages, change boot settings, alter firmware,
or claim that hardware video decoding works. It reports what the host exposes.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
from pathlib import Path
from typing import Callable


class Arm64Diagnostics:
    def __init__(
        self,
        root: str | Path = "/",
        machine: str | None = None,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        self.root = Path(root)
        self.machine = (machine or platform.machine()).strip().lower()
        self.which = which or shutil.which

    def _path(self, absolute_path: str) -> Path:
        return self.root / absolute_path.lstrip("/")

    def _read_text(self, absolute_path: str) -> str | None:
        try:
            return self._path(absolute_path).read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, UnicodeError):
            return None

    def _os_release(self) -> dict[str, str]:
        content = self._read_text("/etc/os-release") or ""
        values: dict[str, str] = {}
        for line in content.splitlines():
            key, separator, value = line.partition("=")
            if not separator or not key or key.startswith("#"):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            values[key] = value.replace(r"\"", '"').replace(r"\\", "\\")
        return values

    def _memory_total_mb(self) -> int | None:
        content = self._read_text("/proc/meminfo") or ""
        for line in content.splitlines():
            key, separator, value = line.partition(":")
            if key != "MemTotal" or not separator:
                continue
            parts = value.strip().split()
            try:
                amount = int(parts[0])
            except (ValueError, IndexError):
                return None
            unit = parts[1].lower() if len(parts) > 1 else "kb"
            if unit == "kb":
                return max(1, amount // 1024)
            if unit == "mb":
                return amount
            if unit == "b":
                return max(1, amount // (1024 * 1024))
            return None
        return None

    def _temperature_c(self) -> float | None:
        thermal_root = self._path("/sys/class/thermal")
        try:
            zones = sorted(thermal_root.glob("thermal_zone*/temp"))
        except OSError:
            return None
        for temp_path in zones:
            try:
                raw = int(temp_path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                continue
            value = raw / 1000.0 if raw > 1000 else float(raw)
            if 0 < value < 150:
                return round(value, 1)
        return None

    def _gpu_devices(self) -> list[str]:
        dri_root = self._path("/dev/dri")
        try:
            return sorted(
                item.name for item in dri_root.iterdir()
                if item.name.startswith(("card", "renderD"))
            )
        except OSError:
            return []

    def _display_connectors(self) -> list[dict[str, str]]:
        drm_root = self._path("/sys/class/drm")
        connectors: list[dict[str, str]] = []
        try:
            entries = sorted(drm_root.iterdir())
        except OSError:
            return connectors
        for entry in entries:
            if "-" not in entry.name:
                continue
            status_path = entry / "status"
            try:
                status = status_path.read_text(encoding="ascii").strip()
            except OSError:
                continue
            connectors.append({"name": entry.name, "status": status})
        return connectors

    def _input_devices(self) -> list[str]:
        input_root = self._path("/dev/input")
        try:
            return sorted(item.name for item in input_root.glob("event*"))
        except OSError:
            return []

    def collect(self) -> dict[str, object]:
        is_arm64 = self.machine in ("aarch64", "arm64")
        model = self._read_text("/proc/device-tree/model")
        os_release = self._os_release()
        dependencies = {
            "mpv": bool(self.which("mpv")),
            "chromium": bool(self.which("chromium") or self.which("chromium-browser")),
            "systemctl": bool(self.which("systemctl")),
            "nmcli": bool(self.which("nmcli")),
        }
        connectors = self._display_connectors()
        return {
            "platform": "linux-arm64" if is_arm64 else "unsupported",
            "architecture": self.machine or "unknown",
            "is_arm64": is_arm64,
            "board_model": model.replace("\x00", "").strip() if model else None,
            "os": {
                "name": os_release.get("PRETTY_NAME") or os_release.get("NAME"),
                "id": os_release.get("ID"),
                "version": os_release.get("VERSION_ID"),
            },
            "memory_total_mb": self._memory_total_mb(),
            "cpu_temperature_c": self._temperature_c(),
            "gpu_devices": self._gpu_devices(),
            "display_connectors": connectors,
            "input_devices": self._input_devices(),
            "dependencies": dependencies,
            "media_acceleration": {
                "status": "not_verified",
                "hardware_decoder": None,
                "message": (
                    "A aceleracao so pode ser confirmada durante a reproducao, "
                    "consultando o decoder realmente ativo e os frames perdidos."
                ),
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostico somente leitura do host ARM64 do KTV OS.")
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio em JSON.")
    parser.add_argument(
        "--require-arm64",
        action="store_true",
        help="Retorna codigo 2 se o sistema nao estiver executando em ARM64.",
    )
    args = parser.parse_args(argv)
    report = Arm64Diagnostics().collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("KTV OS - diagnostico Linux ARM64")
        print("Plataforma: {}".format(report["platform"]))
        print("Arquitetura: {}".format(report["architecture"]))
        print("Placa: {}".format(report["board_model"] or "nao identificada"))
        print("Memoria: {} MB".format(report["memory_total_mb"] or "nao identificada"))
        print("GPU DRM: {}".format(", ".join(report["gpu_devices"]) or "nao detectada"))
        print("Aceleracao de video: ainda nao verificada")
        print("Dependencias: {}".format(report["dependencies"]))
    if args.require_arm64 and not report["is_arm64"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
