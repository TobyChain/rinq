#!/usr/bin/env bash
# Boot a watch simulator, build, install and launch RinqWatch.
set -euo pipefail

cd "$(dirname "$0")/.."

xcodebuild \
  -project Rinq.xcodeproj \
  -scheme RinqWatch \
  -configuration Debug \
  -destination 'generic/platform=watchOS Simulator' \
  -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO \
  build >/dev/null

APP_PATH=$(find build/Build/Products -name 'RinqWatch.app' -maxdepth 2 | head -1)
if [ -z "${APP_PATH:-}" ]; then
  echo "built .app not found" >&2
  exit 1
fi

UDID=$(xcrun simctl list devices available | grep -i 'apple watch' | head -1 | grep -oE '[0-9A-Fa-f-]{36}' | head -1)
if [ -z "${UDID:-}" ]; then
  echo "No Apple Watch simulator found. Run: xcodebuild -downloadPlatform watchOS" >&2
  exit 1
fi

xcrun simctl boot "$UDID" 2>/dev/null || true
open -a Simulator
xcrun simctl install "$UDID" "$APP_PATH"
BUNDLE=$(/usr/libexec/PlistBuddy -c "Print CFBundleIdentifier" "$APP_PATH/Info.plist")
xcrun simctl launch "$UDID" "$BUNDLE"
echo "launched $BUNDLE on $UDID"
