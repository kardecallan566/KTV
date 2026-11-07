#!/usr/bin/env bash
# Ajusta o sistema instalado para o fuso oficial de Brasília.
set -Eeuo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Execute com sudo: sudo bash $0" >&2
  exit 1
fi
if ! command -v timedatectl >/dev/null 2>&1; then
  echo "timedatectl não está disponível neste sistema." >&2
  exit 1
fi
timedatectl set-timezone America/Sao_Paulo
timedatectl status
