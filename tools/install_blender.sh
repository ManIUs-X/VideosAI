#!/usr/bin/env bash
# Installs Blender 4.2 LTS (Linux x64 tarball) + runtime libs. Works on Colab, RunPod, Ubuntu.
set -euo pipefail
VER=${BLENDER_VERSION:-4.2.23}
DEST=${BLENDER_DIR:-/opt/blender}
if [ -x "$DEST/blender-$VER-linux-x64/blender" ]; then echo "Blender $VER already installed"; exit 0; fi
SUDO=""; [ "$(id -u)" != "0" ] && SUDO="sudo"
$SUDO apt-get update -qq || true
$SUDO apt-get install -y -qq libxi6 libxkbcommon0 libsm6 libxrender1 libxxf86vm1 libxfixes3 libgl1 libegl1 ffmpeg >/dev/null || true
$SUDO mkdir -p "$DEST"
curl -sSL "https://download.blender.org/release/Blender4.2/blender-$VER-linux-x64.tar.xz" | $SUDO tar xJ -C "$DEST"
"$DEST/blender-$VER-linux-x64/blender" -b --version | head -1
