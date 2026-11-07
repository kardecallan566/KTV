#!/usr/bin/env bash
# KTV OS installer for Raspberry Pi OS / DietPi (Debian-based).
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute como root: sudo bash /caminho/ktv-os/raspberry-pi/install.sh"
  exit 1
fi

# When launched from a root shell, prefer DietPi's standard account.
TARGET_USER="${SUDO_USER:-}"
if [[ -z "$TARGET_USER" ]] || ! id "$TARGET_USER" >/dev/null 2>&1; then
  if id dietpi >/dev/null 2>&1; then
    TARGET_USER="dietpi"
  elif id pi >/dev/null 2>&1; then
    TARGET_USER="pi"
  else
    TARGET_USER="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 && $7 !~ /nologin|false/ {print $1; exit}')"
  fi
fi
if [[ -z "$TARGET_USER" ]] || ! id "$TARGET_USER" >/dev/null 2>&1; then
  echo "ERRO: não encontrei um usuário comum para executar o KTV."
  exit 1
fi

TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
TARGET_UID="$(id -u "$TARGET_USER")"
TARGET_GID="$(id -g "$TARGET_USER")"
if [[ -z "$TARGET_HOME" || ! -d "$TARGET_HOME" ]]; then
  echo "ERRO: não consegui localizar a pasta pessoal de $TARGET_USER."
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
echo "==> Sistema: $(. /etc/os-release && echo "$PRETTY_NAME")"
echo "==> Arquitetura: $ARCH"
echo "==> Usuário da sessão KTV: $TARGET_USER"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ ! -f "$REPO_ROOT/ktv-os/launcher.py" || ! -f "$REPO_ROOT/ktv-os/app/index.html" ]]; then
  echo "ERRO: não encontrei os arquivos do KTV no pendrive."
  echo "Caminho analisado: $REPO_ROOT/ktv-os"
  exit 1
fi

# Capture the USB filesystem UUID so systemd can automount it at boot/hot-plug.
USB_DEVICE="$(findmnt -n -o SOURCE --target "$REPO_ROOT" | head -n1)"
USB_UUID=""
if [[ -b "$USB_DEVICE" ]]; then
  USB_UUID="$(blkid -s UUID -o value "$USB_DEVICE" 2>/dev/null || true)"
fi
if [[ -z "$USB_UUID" ]]; then
  echo "ERRO: não consegui identificar o UUID da partição USB montada em $REPO_ROOT."
  echo "Não vou configurar uma montagem automática sem identificar o dispositivo com segurança."
  exit 1
fi

echo "==> Instalando dependências (pode levar alguns minutos)..."
apt-get update
if apt-cache show chromium >/dev/null 2>&1; then
  BROWSER_PACKAGE="chromium"
elif apt-cache show chromium-browser >/dev/null 2>&1; then
  BROWSER_PACKAGE="chromium-browser"
else
  echo "ERRO: não encontrei o pacote Chromium nos repositórios configurados."
  exit 1
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 mpv "$BROWSER_PACKAGE" rsync \
  xserver-xorg xinit openbox lightdm curl ca-certificates x11-xserver-utils

echo "==> Configurando montagem automática do pendrive..."
install -d /mnt/ktv-usb
FSTAB_LINE="UUID=$USB_UUID /mnt/ktv-usb vfat nofail,x-systemd.automount,x-systemd.device-timeout=10,uid=$TARGET_UID,gid=$TARGET_GID,umask=0022 0 0"
if ! grep -qE "^[[:space:]]*UUID=$USB_UUID[[:space:]]" /etc/fstab; then
  printf '%s\n' "$FSTAB_LINE" >> /etc/fstab
fi
systemctl daemon-reload

echo "==> Copiando KTV OS para /opt/ktv-os..."
install -d -o "$TARGET_USER" -g "$TARGET_USER" /opt/ktv-os
rsync -a --delete --exclude='.git' --exclude='__pycache__' \
  "$REPO_ROOT/ktv-os/" /opt/ktv-os/
chown -R "$TARGET_USER:$TARGET_USER" /opt/ktv-os

echo "==> Criando inicialização kiosk..."
install -d -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.config/openbox"
cat > /opt/ktv-os/raspberry-pi/usb-kiosk-watcher.sh <<'WATCHER'
#!/usr/bin/env bash
set -u

# systemd automount mounts the USB at /mnt/ktv-usb when it is accessed.
# Also accept common desktop automount locations as a fallback.
USB_ROOT=""
while [[ -z "$USB_ROOT" ]]; do
  if [[ -f /mnt/ktv-usb/ktv-os/launcher.py && -f /mnt/ktv-usb/ktv-os/app/index.html ]]; then
    USB_ROOT="/mnt/ktv-usb/ktv-os"
  else
    for base in "/media/$USER" "/run/media/$USER"; do
      [[ -d "$base" ]] || continue
      for mount in "$base"/*; do
        [[ -f "$mount/ktv-os/launcher.py" && -f "$mount/ktv-os/app/index.html" ]] || continue
        USB_ROOT="$mount/ktv-os"
        break 2
      done
    done
  fi
  [[ -n "$USB_ROOT" ]] || sleep 2
done

cd "$USB_ROOT"
export KTV_STATE_DIR="$(dirname "$USB_ROOT")/.ktv-config"
mkdir -p "$KTV_STATE_DIR"
python3 launcher.py &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

for i in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8787/ >/dev/null && break
  sleep 1
done

if command -v chromium >/dev/null 2>&1; then
  BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
  BROWSER=chromium-browser
else
  echo "Chromium não foi encontrado."
  exit 1
fi

"$BROWSER" --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --kiosk --incognito --noerrdialogs --disable-infobars \
  http://127.0.0.1:8787/
WATCHER
chmod 755 /opt/ktv-os/raspberry-pi/usb-kiosk-watcher.sh
chown "$TARGET_USER:$TARGET_USER" /opt/ktv-os/raspberry-pi/usb-kiosk-watcher.sh

cat > "$TARGET_HOME/.config/openbox/autostart" <<'OPENBOX'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
/opt/ktv-os/raspberry-pi/usb-kiosk-watcher.sh
OPENBOX
chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/openbox/autostart"
chmod 755 "$TARGET_HOME/.config/openbox/autostart"

install -d /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-ktv-kiosk.conf <<LIGHTDM
[Seat:*]
autologin-user=$TARGET_USER
autologin-user-timeout=0
user-session=openbox
LIGHTDM

install -d /usr/share/xsessions
cat > /usr/share/xsessions/openbox.desktop <<'SESSION'
[Desktop Entry]
Name=Openbox
Comment=KTV OS kiosk
Exec=openbox-session
Type=Application
SESSION

systemctl enable lightdm
systemctl set-default graphical.target

echo
echo "Instalação concluída."
echo "Usuário: $TARGET_USER"
echo "Pendrive: UUID=$USB_UUID (montagem automática em /mnt/ktv-usb)"
echo "Reinicie com: reboot"
echo "Ao iniciar, o sistema aguardará o pendrive e abrirá o KTV automaticamente."
