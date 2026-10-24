#!/usr/bin/env bash
# KTV OS bootable Debian Live ISO (amd64 / PC / HDMI).
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="${KTV_OS_BUILD_DIR:-$SCRIPT_DIR/.build}"
OUTPUT_DIR="${KTV_OS_OUTPUT_DIR:-$SCRIPT_DIR/dist}"
ISO_NAME="KTV-OS-Alpha-0.7-amd64.iso"

die() { printf 'KTV OS: %s\n' "$*" >&2; exit 1; }

check_sources() {
  for file in "$PROJECT_DIR/ktv-os/launcher.py" "$PROJECT_DIR/ktv-os/player.py" "$PROJECT_DIR/ktv-os/channel_store.py" "$PROJECT_DIR/ktv-os/persistence.py" "$PROJECT_DIR/ktv-os/hardware.py" "$PROJECT_DIR/ktv-os/cec_bridge.py" "$PROJECT_DIR/ktv-os/app/index.html" \
    "$PROJECT_DIR/ktv-os/app/app.js" "$SCRIPT_DIR/packages.list.chroot" \
    "$SCRIPT_DIR/overlay/etc/lightdm/lightdm.conf.d/50-ktv-os.conf" \
    "$SCRIPT_DIR/overlay/etc/xdg/openbox/autostart" \
    "$SCRIPT_DIR/overlay/usr/local/bin/ktv-os-session" \
    "$SCRIPT_DIR/overlay/usr/local/bin/ktv-os-diagnostics"; do
    [[ -f "$file" ]] || die "Arquivo obrigatorio ausente: $file"
  done
}

check_sources
if [[ "${1:-}" == "--check" ]]; then
  printf 'KTV OS: arquivos-base validados; pronto para lb config / lb build.\n'
  exit 0
fi
[[ "$#" -eq 0 ]] || die "Uso: sudo bash build-iso.sh [--check]"
[[ "$(id -u)" -eq 0 ]] || die "Execute como root com sudo (somente para gerar a ISO)."
[[ "$(uname -m)" == "x86_64" ]] || die "Esta imagem inicial e para computadores x86_64 (amd64)."
command -v lb >/dev/null || die "Instale live-build: sudo apt install live-build"
command -v debootstrap >/dev/null || die "Instale debootstrap."
command -v xorriso >/dev/null || die "Instale xorriso."
command -v mksquashfs >/dev/null || die "Instale squashfs-tools."

mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"
cd "$BUILD_DIR"

# Rebuild from a clean generated configuration, never touching the user's SSD.
if [[ -e "config" ]]; then
  lb clean --purge >/dev/null
  rm -rf config
fi

lb config \
  --mode debian \
  --distribution trixie \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --debian-installer none \
  --archive-areas "main non-free-firmware" \
  --mirror-chroot-security "http://security.debian.org/debian-security" \
  --mirror-binary-security "http://security.debian.org/debian-security" \
  --bootappend-live "boot=live components locales=pt_BR.UTF-8 keyboard-layouts=br"

mkdir -p config/package-lists
cp "$SCRIPT_DIR/packages.list.chroot" config/package-lists/ktv-os.list.chroot

# Custom OS files are included in the Live root filesystem. No disk partitioning.
mkdir -p config/includes.chroot
cp -a "$SCRIPT_DIR/overlay/." config/includes.chroot/

mkdir -p config/includes.chroot/opt/ktv-os
cp "$PROJECT_DIR/ktv-os/launcher.py" config/includes.chroot/opt/ktv-os/launcher.py
cp "$PROJECT_DIR/ktv-os/player.py" config/includes.chroot/opt/ktv-os/player.py
cp "$PROJECT_DIR/ktv-os/channel_store.py" config/includes.chroot/opt/ktv-os/channel_store.py
cp "$PROJECT_DIR/ktv-os/persistence.py" config/includes.chroot/opt/ktv-os/persistence.py
cp "$PROJECT_DIR/ktv-os/hardware.py" config/includes.chroot/opt/ktv-os/hardware.py
cp "$PROJECT_DIR/ktv-os/cec_bridge.py" config/includes.chroot/opt/ktv-os/cec_bridge.py
cp -a "$PROJECT_DIR/ktv-os/app" config/includes.chroot/opt/ktv-os/app

# The process runs under the unprivileged default Live user via LightDM/Openbox.
chmod 0755 config/includes.chroot/usr/local/bin/ktv-os-session
chmod 0755 config/includes.chroot/usr/local/bin/ktv-os-diagnostics
chmod 0755 config/includes.chroot/etc/xdg/openbox/autostart

printf '\n=== KTV OS: construindo o Linux Live ===\n'
lb build

SOURCE_ISO=""
for candidate in live-image-amd64.hybrid.iso live-image-amd64.iso; do
  if [[ -s "$candidate" ]]; then SOURCE_ISO="$candidate"; break; fi
done
[[ -n "$SOURCE_ISO" ]] || die "A ferramenta terminou sem gerar uma ISO."
cp "$SOURCE_ISO" "$OUTPUT_DIR/$ISO_NAME"
(cd "$OUTPUT_DIR" && sha256sum "$ISO_NAME" > "$ISO_NAME.sha256")
printf '\nISO criada: %s\n' "$OUTPUT_DIR/$ISO_NAME"
printf 'SHA256:     %s\n' "$OUTPUT_DIR/$ISO_NAME.sha256"
printf 'Escreva no pendrive com Rufus/Ventoy, selecionando a unidade correta.\n'
