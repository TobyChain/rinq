## Problem

Some text and symbols in the macOS Rinq popover rendered with white rectangular backgrounds. The popover opacity workaround recursively enabled layers for every descendant `NSView` and assigned `windowBackgroundColor` whenever a child layer had no background. SwiftUI bridges text, symbols, controls, and layout nodes through descendant AppKit views, so the workaround painted local rectangles behind content that should remain transparent.

## Decision

Keep the opaque window background only on the popover's root content view. Continue walking the hierarchy solely to configure any `NSVisualEffectView` as inactive `windowBackground` material with within-window blending. Do not enable layers or assign background colors on ordinary descendant views. SwiftUI's root `Color(NSColor.windowBackgroundColor)` remains the application-level background.

## Alternatives considered

- Remove all AppKit background configuration: rejected because the original workaround addressed unreadable vibrant popover content and the root still needs a deterministic opaque backing.
- Clear every descendant background after the recursive pass: rejected because that could erase intentional native control backgrounds and still forces unnecessary layer creation.
- Special-case text and image view classes: rejected because SwiftUI's private hosting hierarchy is not a stable API and other control classes could exhibit the same artifact.

## Consequences

- The popover retains one uniform opaque background.
- Text, SF Symbols, controls, and SwiftUI layout subviews preserve transparent local backgrounds unless they intentionally draw one.
- Native visual-effect backdrops remain disabled for readability.
- A regression test verifies that root configuration does not paint ordinary nested content views.
