#!/usr/bin/env bash
# Build RinqMenu.app and a distributable DMG into dist/.
#
# The app bundles the Python daemon runtime (mac/rinq) and an installer
# script, so a DMG install is self-contained: on first run the app installs
# an app-managed daemon into ~/.rinq + launchd (see DaemonSetup.swift).
# The DMG is ad-hoc signed (no Developer ID); Gatekeeper on other machines
# needs a right-click open on first launch. Universal builds need full Xcode;
# with only CLT this produces a single-arch binary for the build host.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$REPO/mac/rinq/__init__.py")"
[ -n "$VERSION" ] || { echo "cannot read __version__ from mac/rinq/__init__.py" >&2; exit 1; }
ARCH="$(uname -m)"
DIST="$REPO/dist"
APP="$DIST/stage/RinqMenu.app"

echo "==> swift build (release)"
cd "$REPO/mac/RinqMenu"
swift build -c release

echo "==> assembling RinqMenu.app $VERSION ($ARCH)"
rm -rf "$DIST/stage"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp ".build/release/RinqMenu" "$APP/Contents/MacOS/RinqMenu"
install -m 755 "$REPO/mac/RinqMenu/install-daemon.sh" \
  "$APP/Contents/Resources/install-daemon.sh"
mkdir -p "$APP/Contents/Resources/rinq-runtime/rinq"
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  "$REPO/mac/rinq/" "$APP/Contents/Resources/rinq-runtime/rinq/"

ICON_KEYS=""
if [ -f "$REPO/mac/RinqMenu/Resources/AppIcon.icns" ]; then
  cp "$REPO/mac/RinqMenu/Resources/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
  ICON_KEYS="  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleIconName</key><string>AppIcon</string>"
fi

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleDisplayName</key><string>Rinq</string>
  <key>CFBundleExecutable</key><string>RinqMenu</string>
  <key>CFBundleIdentifier</key><string>com.rinq.menu</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>RinqMenu</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key><true/>
  </dict>
$ICON_KEYS
</dict>
</plist>
EOF

echo "==> ad-hoc codesign"
codesign --force --sign - "$APP"
codesign --verify --strict "$APP"

echo "==> creating DMG"
DMG_ROOT="$DIST/dmgroot"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R "$APP" "$DMG_ROOT/RinqMenu.app"
ln -sfn /Applications "$DMG_ROOT/Applications"
DMG="$DIST/RinqMenu-$VERSION-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "RinqMenu $VERSION" -srcfolder "$DMG_ROOT" \
  -format UDZO -o "$DMG" -ov >/dev/null
hdiutil verify "$DMG" >/dev/null
rm -rf "$DIST/stage" "$DMG_ROOT"

echo "built $DMG"
