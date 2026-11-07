#!/usr/bin/env python3
"""Atualiza o KTV instalado no pendrive sem Git e preserva dados locais.

Uso:
  python3 tools/atualizar_ktv_usb.py
  python3 tools/atualizar_ktv_usb.py --check
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ZIP = "https://github.com/kardecallan566/KTV/archive/refs/heads/main.zip"
EXPECTED_ROOT = Path("/mnt/ktv-usb/ktv-os")
PROTECTED_NAMES = {
    ".ktv-config", ".ktv-os", ".ktv-backups", "channels.json",
    "iptv_free_favorites.json", "pluto_favorites.json", "logs",
}
PROTECTED_SUFFIXES = (".log", ".local")


def is_protected(relative: Path) -> bool:
    return any(part in PROTECTED_NAMES for part in relative.parts) or relative.name.endswith(PROTECTED_SUFFIXES)


def download_archive(destination: Path) -> None:
    request = urllib.request.Request(
        REPO_ZIP,
        headers={"User-Agent": "KTV-USB-Updater/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualizador seguro do KTV no pendrive")
    parser.add_argument("--check", action="store_true", help="apenas verifica se há conexão e pacote disponível")
    parser.add_argument("--root", type=Path, default=EXPECTED_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()

    if not (root / "launcher.py").is_file() or not (root / "app" / "index.html").is_file():
        print(f"ERRO: não encontrei uma instalação KTV válida em {root}", file=sys.stderr)
        return 2
    if root != EXPECTED_ROOT.resolve() and "--root" not in sys.argv:
        print("ERRO: caminho de instalação inesperado.", file=sys.stderr)
        return 2
    if not args.check and not os.access(root, os.W_OK):
        print("ERRO: sem permissão de escrita. Execute com sudo.", file=sys.stderr)
        return 2

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / ".ktv-backups" / stamp
    updated = 0
    skipped = 0

    try:
        with tempfile.TemporaryDirectory(prefix="ktv-update-") as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "ktv.zip"
            print("Baixando versão atual do KTV (GitHub)...")
            download_archive(archive)
            with zipfile.ZipFile(archive) as zf:
                candidates = [n for n in zf.namelist() if n.endswith("/ktv-os/launcher.py")]
                if not candidates:
                    raise RuntimeError("pacote baixado não contém ktv-os/launcher.py")
                prefix = candidates[0].rsplit("ktv-os/launcher.py", 1)[0] + "ktv-os/"
                source = tmp_path / "source"
                source.mkdir()
                for name in zf.namelist():
                    if not name.startswith(prefix):
                        continue
                    relative_text = name[len(prefix):]
                    if not relative_text:
                        continue
                    relative = Path(relative_text)
                    if relative.is_absolute() or ".." in relative.parts or is_protected(relative):
                        skipped += 1
                        continue
                    target = source / relative
                    if name.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst)

            incoming = [p for p in source.rglob("*") if p.is_file()]
            if not (source / "launcher.py").is_file() or not (source / "app" / "index.html").is_file():
                raise RuntimeError("estrutura do pacote KTV incompleta; instalação não foi alterada")
            if args.check:
                print(f"OK: pacote válido; {len(incoming)} arquivos disponíveis para atualização.")
                return 0

            backup_root.mkdir(parents=True, exist_ok=True)
            for src in incoming:
                relative = src.relative_to(source)
                if is_protected(relative):
                    skipped += 1
                    continue
                target = root / relative
                if target.exists():
                    if target.is_dir():
                        raise RuntimeError(f"conflito: arquivo do KTV coincide com pasta local: {target}")
                    backup = backup_root / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                target.parent.mkdir(parents=True, exist_ok=True)
                staged = target.with_name(target.name + ".ktv-new")
                shutil.copy2(src, staged)
                os.replace(staged, target)
                updated += 1

        print(f"Atualização concluída: {updated} arquivos atualizados.")
        print(f"Backup dos arquivos substituídos: {backup_root}")
        print("Configurações, favoritos e arquivos locais protegidos foram mantidos.")
        print("Recarregue o KTV na TV (Ctrl+Shift+R) ou reinicie o serviço se necessário.")
        return 0
    except Exception as exc:
        print(f"ERRO na atualização: {exc}", file=sys.stderr)
        print("Os arquivos já substituídos têm cópias no backup criado.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
