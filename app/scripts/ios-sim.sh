#!/usr/bin/env bash
# Build, install, and launch the iOS app on the first available iPhone simulator.
set -euo pipefail
cd "$(dirname "$0")/.."

xcodebuild \
  -project Rinq.xcodeproj \
  -scheme RinqApp \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO \
  build >/dev/null

APP_PATH=$(find build/Build/Products -name 'RinqApp.app' | grep iphonesimulator | head -1)
[ -n "$APP_PATH" ] || { echo "built .app not found" >&2; exit 1; }

UDID=$(xcrun simctl list devices available | grep -iE 'iphone' | head -1 | grep -oE '[0-9A-Fa-f-]{36}' | head -1)
[ -n "$UDID" ] || { echo "No iPhone simulator found" >&2; exit 1; }

xcrun simctl boot "$UDID" 2>/dev/null || true
open -a Simulator
xcrun simctl install "$UDID" "$APP_PATH"
BUNDLE=$(/usr/libexec/PlistBuddy -c "Print CFBundleIdentifier" "$APP_PATH/Info.plist")
xcrun simctl launch "$UDID" "$BUNDLE"
echo "launched $BUNDLE on $UDID"
