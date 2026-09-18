## Problem

Quota alerts pulse in the menu bar and popover. The dismissal action was attached only to the alert banner, so clicking the rings, content area, tab control, or another part of the popover did not acknowledge the alert. This made the intended click-to-stop behavior easy to miss and left the animation running.

## Decision

Treat any tap inside the Rinq popover as acknowledgment when an active alert exists. Attach a simultaneous tap gesture to the full `RootView` content shape, clear the active alert through `Store.dismissAlerts()`, and immediately ask `AppDelegate` to redraw the menu-bar icon. Keep the gesture simultaneous so the original picker, button, field, and drag interactions still receive the same click.

The alert banner is now informational and says `Click anywhere`; it is no longer the only dismissal target. The root view also exposes a named accessibility dismissal action. Dismissal remains conditional on an active alert and persists until that quota condition clears.

## Alternatives considered

- Keep dismissal on the alert banner: rejected because the hit target is too narrow and caused the reported failure.
- Dismiss when the popover opens: rejected because an automatically opened alert must remain visible until the user actually acknowledges it.
- Install a process-wide AppKit mouse event monitor: rejected because the SwiftUI root gesture covers this window without adding event-monitor lifecycle and cleanup state.

## Consequences

- The first click anywhere inside an alerting popover acknowledges all currently visible alerts and stops their alert rendering.
- That click also performs its original control action because the acknowledgment gesture is simultaneous.
- Later refreshes keep the same condition dismissed; once the condition clears, a future recurrence can alert again.
- This changes only macOS popover interaction. Alert thresholds, daemon APIs, and iOS/watchOS behavior are unchanged.
