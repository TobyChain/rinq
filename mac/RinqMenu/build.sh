#!/usr/bin/env bash
# Build the Rinq menu-bar app and install it into ~/.rinq/bin.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.rinq/bin"
mkdir -p "$DEST"
cd "$HERE"
echo "building RinqMenu (release)…"
swift build -c release
cp -f "$HERE/.build/release/RinqMenu" "$DEST/RinqMenu"
echo "installed $DEST/RinqMenu"
