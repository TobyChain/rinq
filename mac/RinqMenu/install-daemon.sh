#!/usr/bin/env bash
# Install the rinq daemon + CLI from a RinqMenu.app bundle.
# Usage: install-daemon.sh <version> [port]
#
# Invoked by RinqMenu on first run / upgrade / repair for DMG installs, and
# safe to re-run. It writes the `.app-managed` marker so the app can tell
# app-managed installs (auto-upgraded with the app) from repo installs
# (install.sh; never marked, never touched by the app).
#
# A non-default port derives a distinct launchd label (com.rinq.daemon.p<port>)
# so an isolated test stack can coexist with the real agent.
set -euo pipefail

VERSION="${1:?usage: install-daemon.sh <version> [port]}"
PORT="${2:-7788}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# RINQ_RUNTIME_SRC lets the repo-side script run without a built bundle.
RUNTIME="${RINQ_RUNTIME_SRC:-$HERE/rinq-runtime}"
[ -d "$RUNTIME/rinq" ] || { echo "rinq runtime not found at $RUNTIME" >&2; exit 1; }

TR_HOME="$HOME/.rinq"
LIBEXEC="$TR_HOME/libexec"
BIN_DIR="$HOME/.local/bin"
LOG_DIR="$HOME/Library/Logs"

PYTHON=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$cand" ]; then PYTHON="$cand"; break; fi
done
[ -n "$PYTHON" ] || { echo "python3 not found" >&2; exit 1; }

if [ "$PORT" = "7788" ]; then
  LABEL="com.rinq.daemon"
else
  LABEL="com.rinq.daemon.p$PORT"
fi
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$BIN_DIR" "$HOME/Library/LaunchAgents" "$LOG_DIR" "$TR_HOME"

rm -rf "$LIBEXEC"
mkdir -p "$LIBEXEC"
cp -R "$RUNTIME/rinq" "$LIBEXEC/rinq"
printf '%s\n' "$VERSION" > "$LIBEXEC/rinq/.app-managed"

cat > "$LIBEXEC/rinq-cli" <<EOF
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, "$LIBEXEC")
from rinq.cli import main
if __name__ == "__main__":
    raise SystemExit(main())
EOF
chmod +x "$LIBEXEC/rinq-cli"

cat > "$BIN_DIR/rinq" <<EOF
#!/bin/sh
for py in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 python3; do
  if command -v "\$py" >/dev/null 2>&1; then
    exec "\$py" "$LIBEXEC/rinq-cli" "\$@"
  fi
done
echo "no python3 found" >&2
exit 1
EOF
chmod +x "$BIN_DIR/rinq"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$LIBEXEC/rinq-cli</string>
    <string>serve</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/rinq.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/rinq.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null \
  || launchctl load "$PLIST" 2>/dev/null || true

echo "rinq daemon installed ($LABEL, port $PORT, version $VERSION)"
