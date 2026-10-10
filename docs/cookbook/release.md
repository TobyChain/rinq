# Release runbook (DMG)

How a Rinq release is built, verified, and published. Current state; update in
the same change when the pipeline changes.

## What a release contains

- `RinqMenu-<version>-<arch>.dmg` — `RinqMenu.app` plus an `/Applications`
  symlink. The app bundles the Python daemon runtime (`mac/rinq`) and
  `install-daemon.sh` in `Contents/Resources`, so a DMG install is
  self-contained: on first run `DaemonSetup.swift` installs an app-managed
  daemon into `~/.rinq/libexec`, the `rinq` CLI shim into `~/.local/bin`, and
  the `com.rinq.daemon` launchd agent.
- Version single source: `__version__` in `mac/rinq/__init__.py`. The DMG name,
  `Info.plist` (`CFBundleShortVersionString`), and the app-managed marker all
  derive from it.

### App-managed vs repo installs

`install.sh` never writes `~/.rinq/libexec/rinq/.app-managed`; the bundled
installer always does. The marker is how `DaemonSetup` decides ownership:

| State | Behavior |
| --- | --- |
| marker absent, daemon answers | repo install; app never touches it |
| marker version ≠ app version | app upgrades the daemon and restarts it |
| no daemon on the status port | app installs (fresh machine or repair) |

To hand a repo install over to the app, remove `~/.rinq/libexec` and relaunch
the app.

## Commands

```bash
# build the DMG only (uses the version currently in __init__.py)
make dist            # == scripts/build-dmg.sh

# full release: tests -> bump -> DMG -> commit -> tag -> push -> GitHub release
scripts/release.sh 0.1.8 "dmg distribution"

# rehearsal: same build, no git/GitHub side effects (version file restored)
scripts/release.sh 0.1.8 "dmg distribution" --local

# custom release body instead of the generated one
scripts/release.sh 0.1.8 "dmg distribution" --notes-file notes.md
```

Release commits use the author recorded in `AGENTS.md` (`TobyChain`) with no
AI trailers; commit message is `Release Rinq <version> with <summary>`.

## Local verification before pushing

1. `make mac-test` (42 collector tests) and `swift build -c release`.
   `swift test` needs full Xcode (XCTest); on CLT-only machines
   `scripts/release.sh` detects that and warns instead of failing.
2. `make dist`, then mount the DMG and drag the app into /Applications.
3. Fresh-machine path: run the app with an isolated HOME and port —
   `HOME=~/rinq-dmg-test RINQ_PORT=7799 /Applications/RinqMenu.app/Contents/MacOS/RinqMenu`
   — and check the daemon came up (`curl 127.0.0.1:7799/status`), the marker
   was written, and label `com.rinq.daemon.p7799` is loaded. Clean up with
   `launchctl bootout gui/$(id -u)/com.rinq.daemon.p7799` and remove the test
   HOME. Caveat: the launchd-started daemon still reads the real `~/.rinq`
   config and databases (launchd does not inherit the overridden HOME), so
   this test shares state with a live install; keep the overlap short.

## Prerequisites and constraints

- `gh` authenticated with a token that can write releases on
  `TobyChain/rinq` (fine-grained: Contents read/write; classic: `repo`).
- The DMG is ad-hoc signed (no Developer ID / notarization). Gatekeeper on
  other machines shows a first-launch prompt; release notes tell users to
  right-click → Open. Notarization is the upgrade path once a Developer ID
  exists.
- `uname -m` arch only (arm64 on the current build host). Universal builds
  need full Xcode; nothing in the pipeline is arch-specific.
- The icon (`mac/RinqMenu/Resources/AppIcon.icns`) is a committed asset;
  regenerate with `swift scripts/make-icon.swift` after changing the motif.
