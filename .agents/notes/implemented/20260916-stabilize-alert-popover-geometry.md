## Problem

After a quota alert was dismissed, the macOS popover still appeared to pulse and the ring stack shifted out of place. The alert state controlled geometry in three places: the initial `NSPopover.contentSize`, the root layout's 54-point alert allowance, and each alerting quota row's vertical padding.

The initial popover layout did not include the active alert, so an alert popover opened at the plain size and resized immediately after SwiftUI appeared. Dismissal then removed the alert allowance, increased the available ring diameter, removed row padding, and resized the AppKit popover in the same update. These geometry changes were perceived as whole-window pulsing and ring misalignment even after alert colors were cleared.

## Decision

Use one `PopoverLayout.make(rings:visibleScreenSize:hasAlerts:)` entry point for both the AppKit initial size and SwiftUI content. When a popover observes an alert, reserve its alert slot for the rest of that popover instance. Dismissing the alert removes the banner and alert colors but leaves an empty fixed-height slot until the popover closes; the next popover starts from current state and can use the compact no-alert layout.

Remove alert-dependent vertical padding from quota rows. Gate ring and row pulse opacity on both the animation state and the current presence of an alert, so a stale `repeatForever` transaction cannot affect rendering after dismissal. Apply dismissal inside an explicit no-animation transaction. Keep the banner summary to one line so it cannot exceed the fixed slot.

## Alternatives considered

- Resize the popover down immediately after dismissal: rejected because it moves the anchored window and recomputes ring size at the exact moment the user expects visual stability.
- Keep alert-dependent row padding but animate the transition: rejected because animation preserves the unwanted geometry change and makes alignment depend on timing.
- Disable all alert pulsing: rejected because the requested behavior is to stop it after acknowledgment, not remove the active-alert signal entirely.
- Delay resizing with a timer: rejected because it makes behavior nondeterministic and still shifts the interface while the popover remains open.

## Consequences

- Alert popovers open at their final size instead of resizing once after presentation.
- Acknowledgment immediately stops alert visual effects without moving the window, ring stack, or quota rows.
- A dismissed alert leaves blank alert-slot space only until the current popover closes. Reopening uses the compact no-alert layout.
- If a new alert arrives while a plain popover is already open, the slot can still be added so the alert remains visible.
- Alert thresholds, dismissal persistence, daemon APIs, and non-macOS clients are unchanged.
