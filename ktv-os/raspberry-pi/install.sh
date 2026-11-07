#!/usr/bin/env bash
# KTV OS installer for Raspberry Pi OS (Pi 3 Model B / 32-bit).
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute com sudo: sudo bash ktv-os/raspberry-pi/install.sh"
  exit 1
fi

TARGET_USER="${SUDO_USER:-pi}"
if ! id "$TARGET_USER" >/dev/null 2>&1; then
  echo "Usuário '$TARGET_USER' não existe. Rode o script com sudo a partir da sessão do usuário."
  exit 1
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
if [[ -z "$TARGET_HOME" || ! -d "$TARGET_HOME" ]]; then
  echo "Não consegui localizar a pasta pessoal de $TARGET_USER."
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
if [[ "$ARCH" != "armhf" ]]; then
  echo "Aviso: arquitetura detectada: $ARCH. O Pi 3 recomendado é Raspberry Pi OS 32-bit (armhf)."
  read -r -p "Continuar mesmo assim? [s/N] " answer
  [[ "${answer,,}" == "s" ]] || exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="/opt/ktv-os"
echo "==> Instalando dependências (pode levar alguns minutos)..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 mpv chromium-browser rsync \
  xserver-xorg xinit openbox lightdm curl ca-certificates

echo "==> Copiando KTV OS para $DEST..."
install -d -o "$TARGET_USER" -g "$TARGET_USER" "$DEST"
rsync -a --delete --exclude='.git' --exclude='__pycache__' \
  "$REPO_ROOT/ktv-os/" "$DEST/"
chown -R "$TARGET_USER:$TARGET_USER" "$DEST"

echo "==> Criando inicialização kiosk..."
install -d -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.config/openbox"
cat > "$DEST/raspberry-pi/usb-kiosk-watcher.sh" <<'WATCHER'
#!/usr/bin/env bash
set -u
# Wait for a KTV USB drive; it may be plugged in after boot.
USB_ROOT=""
while [[ -z "$USB_ROOT" ]]; do
  for base in "/media/$USER" "/run/media/$USER"; do
    [[ -d "$base" ]] || continue
    for mount in "$base"/*; do
      [[ -d "$mount/ktv-os" && -f "$mount/ktv-os/launcher.py" && -f "$mount/ktv-os/app/index.html" ]] || continue
      USB_ROOT="$mount/ktv-os"
      break 2
    done
  done
  sleep 2
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
chromium-browser --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --kiosk --incognito --noerrdialogs --disable-infobars \
  http://127.0.0.1:8787/
WATCHER
chmod 755 "$DEST/raspberry-pi/usb-kiosk-watcher.sh"
chown "$TARGET_USER:$TARGET_USER" "$DEST/raspberry-pi/usb-kiosk-watcher.sh"

cat > "$TARGET_HOME/.config/openbox/autostart" <<'OPENBOX'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
/opt/ktv-os/raspberry-pi/usb-kiosk-watcher.sh
OPENBOX
chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/openbox/autostart"
chmod 755 "$TARGET_HOME/.config/openbox/autostart"

# Autologin em sessão Openbox; configuração preserva outros arquivos do LightDM.
install -d /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-ktv-kiosk.conf <<LIGHTDM
[Seat:*]
autologin-user=$TARGET_USER
autologin-user-timeout=0
user-session=openbox
LIGHTDM

# Openbox como sessão disponível ao LightDM.
install -d /usr/share/xsessions
cat > /usr/share/xsessions/openbox.desktop <<SESSION
[Desktop Entry]
Name=Openbox
Comment=KTV OS kiosk
Exec=openbox-session
Type=Application
SESSION

systemctl enable lightdm
systemctl set-default graphical.target

echo
echo "Instalação preparada. Reinicie com: sudo reboot"
echo "Ao iniciar, o sistema aguardará o pendrive com KTV OS e abrirá automaticamente."
echo "Para voltar ao terminal: Ctrl+Alt+F2 (ou F3)."
