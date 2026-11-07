#!/usr/bin/env bash
# Prepare a mounted USB drive with the KTV OS application files.
# This copies files only; it NEVER formats or repartitions a disk.
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Use: sudo bash ktv-os/raspberry-pi/prepare-usb.sh /media/USER/USB"
  exit 1
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: sudo bash ktv-os/raspberry-pi/prepare-usb.sh /path/to/mounted/USB"
  exit 2
fi
USB="$(realpath "$1")"
[[ -d "$USB" ]] || { echo "USB mount not found"; exit 1; }
findmnt -rn -T "$USB" >/dev/null || { echo "The path is not on a mounted filesystem."; exit 1; }
SOURCE="$(cd "$(dirname "$0")/../.." && pwd)/ktv-os"
[[ -f "$SOURCE/launcher.py" && -f "$SOURCE/app/index.html" ]] || { echo "KTV source not found: $SOURCE"; exit 1; }
if [[ "$USB" == "/" || "$USB" == "/boot" || "$USB" == "/home" || "$USB" == "/opt" ]]; then
  echo "Refusing unsafe destination: $USB"; exit 1
fi
DEST="$USB/ktv-os"
echo "Source: $SOURCE"
echo "Destination: $DEST"
echo "This will replace files inside $DEST, but will preserve .ktv-config."
read -r -p "Continue? [s/N] " answer
[[ "${answer,,}" == "s" ]] || exit 0
mkdir -p "$DEST"
rsync -a --delete --exclude='.git' --exclude='__pycache__' "$SOURCE/" "$DEST/"
mkdir -p "$USB/.ktv-config"
sync
echo
echo "KTV OS copied successfully to $DEST"
echo "Safely eject the USB before connecting it to the Raspberry Pi."
