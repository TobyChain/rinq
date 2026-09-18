## Problem

The macOS popover only closed on an explicit action: clicking the menu-bar
icon again, clicking outside it (`.transient` behavior), or the new Quit
button. If the user opened it to glance at quota and then walked away, it
stayed on screen indefinitely. The request was to auto-close the popover 10
seconds after it opens when the user does not interact with it.

## Decision

Add a deadline-based idle auto-close in `AppDelegate`. When the popover is
shown, `startIdleAutoClose()` installs a local `NSEvent` monitor and schedules
a `DispatchWorkItem` for `idleCloseInterval` (10) seconds. The monitor watches
mouse-down (left/right/other), left-drag, scroll wheel, key-down, and
mouse-moved events; when an event targets the popover window it calls
`scheduleIdleClose()`, which cancels the pending work item and arms a fresh
10-second deadline. On expiry the work item calls `NSPopover.performClose`.

`popoverDidClose` (via `NSPopoverDelegate`) tears down both the work item and
the event monitor, so no timer or monitor survives a closed popover. Clicking
the icon or outside still closes immediately through the existing paths, which
also fire `popoverDidClose` and clean up.

Active alerts are exempt: if `store.alerts` is non-empty when the deadline
fires, the popover stays open and the timer re-arms, so an alert popover is not
hidden before the user sees or acknowledges it. Once the alert clears, the next
deadline closes the popover normally.

## Alternatives considered

- SwiftUI timer inside `RootView`: rejected because the popover lifecycle and
  `performClose` live in `AppDelegate`; driving AppKit window close from a
  view's `onReceive` is more indirect and complicates cancellation on close.
- Repeating `Timer` that polls an idle counter: rejected in favor of a single
  cancel-and-reschedule `DispatchWorkItem`, which is simpler and has no drift
  or leftover-tick concerns.
- Global (not local) event monitor: unnecessary; interaction that should reset
  the timer happens inside this app's popover window, and a local monitor
  avoids observing other applications' events.
- Tracking areas / `mouseEntered` only: rejected because it misses keyboard and
  scroll interaction and does not cover the whole content reliably.
- Closing regardless of alerts: rejected because auto-opened alert popovers
  must remain visible until acknowledged, matching the existing alert contract.

## Consequences

- An idle popover closes 10 seconds after opening; any click, scroll, key
  press, drag, or pointer movement inside it restarts the 10-second window.
- A popover showing an active alert stays open until the alert is dismissed or
  clears, then auto-closes on the next idle window.
- The event monitor and pending close are always removed on
  `popoverDidClose`, including manual and outside-click closes, so nothing
  leaks across open/close cycles.
- Behavior is confined to the macOS menu-bar app. Daemon APIs, alert
  thresholds, dismissal persistence, and iOS/watchOS clients are unchanged.
- `idleCloseInterval` is a single constant, so the duration can be tuned in one
  place.
