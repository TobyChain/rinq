## Problem

Two macOS menu-bar issues after the alert-dismissal work:

1. The popover had no way to quit the app. `RinqMenu` runs as an
   `.accessory` agent with no Dock icon and no application menu, so a user
   who wanted to stop it had to use `launchctl` or Activity Monitor.
2. Text, SF Symbols, and the ring stack showed white rectangular backgrounds.
   The root cause was the earlier recursive `makeOpaque` popover-background
   workaround (committed at `84c9b27`, the deployed v0.1.3 binary). It set
   `windowBackgroundColor` on every descendant `NSView`, painting rectangles
   behind SwiftUI-bridged content. The source fix for this
   (`configurePopoverBackground`, note `20260916-remove-white-control-backgrounds`)
   was already in the working tree but had not been rebuilt into the running
   `~/.rinq/bin/RinqMenu`, so the artifact was still visible at runtime.

## Decision

Add a persistent one-line footer (`PopoverFooter` in `RootView.swift`) shown
under every tab, with a right-aligned `Quit Rinq` button that calls
`NSApplication.shared.terminate(nil)`. Reserve its height in the popover
layout by adding `PopoverLayout.footerHeight` (34) to `fixedHeight` in
`Models.swift`, so the popover grows to fit the footer and ring diameter still
adapts. The footer is plain-styled and secondary-colored so it does not
compete with the rings.

Make the menu launch agent quittable: change `KeepAlive` from `true` to
`{ SuccessfulExit = false }` in both the repo template
`mac/com.rinq.menu.plist` and the deployed
`~/Library/LaunchAgents/com.rinq.menu.plist`. A clean user-initiated quit
(exit code 0) is no longer relaunched, while a crash or the next login still
starts the app.

Rebuild with `build.sh` and reload the launch agent so the running binary
finally includes the non-recursive background fix. This is what actually
removes the white backgrounds the user reported; the code was correct but
unshipped.

## Alternatives considered

- Quit via a right-click `NSMenu` on the status item: rejected for this change
  because the user asked for a quit control inside the popover; a status-item
  menu is not visible where they were looking. Left as a possible addition.
- Put quit in the Providers/Settings tab only: rejected because a quit action
  should be reachable from any tab without hunting.
- Show a version string in the footer: rejected per user; it would add a third
  place to keep the version in sync (`mac/rinq/__init__.py`,
  `app/project.yml`) with no runtime source of truth in the Swift app.
- Leave `KeepAlive=true` and rely on the button: rejected because launchd would
  relaunch the app within seconds, making quit ineffective.
- Fix white backgrounds again in code: unnecessary; the code fix already
  existed. The real gap was that the deployed binary was stale.

## Consequences

- The popover always shows a Quit control; clicking it terminates the app and
  launchd does not relaunch it until crash or next login.
- The footer adds 34 pt of fixed height; ring diameter shrinks slightly on
  small screens but stays within the half-screen cap (covered by
  `testLayoutReservesFooterHeight`).
- After redeploy, popover text, SF Symbols, controls, and rings render on the
  single opaque root background with no white rectangles.
- `swift test` (27 tests) and `swift build -c release` pass. The deployed
  `~/.rinq/bin/RinqMenu` hash-matches the fresh release build and exports
  `PopoverFooter`; `/status` still returns 200.
- Alert thresholds, dismissal behavior, daemon APIs, and iOS/watchOS clients
  are unchanged.
