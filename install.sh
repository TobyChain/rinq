#!/usr/bin/env bash
# One-command Mac-side install: CLI shim + launchd agent.
# Copies the runtime out of the (TCC-protected) repo into ~/.rinq so the
# launchd agent can read it without Documents-folder permission.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
TR_HOME="$HOME/.rinq"
LIBEXEC="$TR_HOME/libexec"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST_LABEL="com.rinq.daemon"
PLIST_DST="$LAUNCH_AGENTS/$PLIST_LABEL.plist"
LOG_DIR="$HOME/Library/Logs"

PYTHON=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$cand" ]; then PYTHON="$cand"; break; fi
done
[ -n "$PYTHON" ] || { echo "python3 not found" >&2; exit 1; }

mkdir -p "$BIN_DIR" "$LAUNCH_AGENTS" "$LOG_DIR" "$TR_HOME"

rm -rf "$LIBEXEC"
mkdir -p "$LIBEXEC"
cp -R "$REPO/mac/rinq" "$LIBEXEC/rinq"

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
echo "installed $BIN_DIR/rinq"

cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$LIBEXEC/rinq-cli</string>
    <string>serve</string>
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
echo "wrote $PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST" 2>/dev/null || launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || true

echo
echo "rinq daemon: $(launchctl list 2>/dev/null | grep -q "$PLIST_LABEL" && echo loaded || echo 'not loaded (check logs)')"
echo
echo "Next steps:"
echo "  1. Ensure $BIN_DIR is on PATH."
echo "  2. Verify:  rinq status"
echo "  3. Wire agent hooks (see README -> Hooking agents)."
echo "  4. Watch build:  make watch-build  (then make watch-sim)"
