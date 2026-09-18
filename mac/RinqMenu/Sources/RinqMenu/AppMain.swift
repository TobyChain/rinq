import AppKit
import SwiftUI

// RinqMenu: a menu-bar item showing the configured quota rings. Clicking opens
// a native SwiftUI popover with the dashboard and a Settings tab for adding
// provider keys, toggling vendors, and managing ring order. Data comes from
// the rinq daemon (http://127.0.0.1:<port>).
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    private var item: NSStatusItem!
    private var popover: NSPopover?
    private var store: Store!
    private var timer: Timer?
    private var idleCloseWorkItem: DispatchWorkItem?
    private var popoverEventMonitor: Any?
    private static let idleCloseInterval: TimeInterval = 10

    func applicationDidFinishLaunching(_ note: Notification) {
        item = NSStatusBar.system.statusItem(withLength: 30)
        item.button?.target = self
        item.button?.action = #selector(toggle(_:))
        store = Store()
        render(rings: [], alerts: [])
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                let shouldPresent = await self.store.refresh()
                self.render(rings: self.store.status?.rings ?? [], alerts: self.store.alerts)
                if shouldPresent { self.presentAlertPopover() }
            }
        }
        Task {
            let shouldPresent = await store.refresh()
            render(rings: store.status?.rings ?? [], alerts: store.alerts)
            if shouldPresent { presentAlertPopover() }
        }
    }

    @objc private func toggle(_ sender: Any?) {
        if let pop = popover, pop.isShown { pop.performClose(sender); return }

        let screenSize = item.button?.window?.screen?.visibleFrame.size
            ?? NSScreen.main?.visibleFrame.size
            ?? NSSize(width: 1440, height: 900)
        let initialLayout = PopoverLayout.make(
            rings: store.status?.rings ?? [],
            visibleScreenSize: screenSize,
            hasAlerts: !store.alerts.isEmpty
        )
        let root = NSHostingController(rootView: RootView(
            store: store,
            visibleScreenSize: screenSize,
            onLayoutChange: { [weak self] layout in
                self?.resizePopover(layout)
            },
            onAlertsDismissed: { [weak self] in
                guard let self else { return }
                self.render(rings: self.store.status?.rings ?? [], alerts: self.store.alerts)
            }
        ))
        let pop = NSPopover()
        pop.behavior = .transient
        pop.delegate = self
        pop.contentSize = NSSize(width: initialLayout.width, height: initialLayout.height)
        pop.contentViewController = root
        popover = pop
        pop.show(relativeTo: item.button!.bounds, of: item.button!, preferredEdge: .minY)

        // Replace the popover's vibrant backdrop with a solid window-background
        // layer so the SwiftUI content (including the segmented control) reads
        // cleanly. Runs after show() once the layer tree exists.
        DispatchQueue.main.async {
            if let window = pop.contentViewController?.view.window,
               let content = window.contentView {
                Self.configurePopoverBackground(content)
            }
        }
        startIdleAutoClose()
        Task {
            _ = await store.refresh()
            render(rings: store.status?.rings ?? [], alerts: store.alerts)
        }
    }

    // MARK: - Idle auto-close

    // The popover closes itself after `idleCloseInterval` seconds without user
    // interaction. A local event monitor resets the deadline on any click,
    // scroll, key press, drag, or pointer movement inside the popover window.
    // An open alert popover is kept until the user interacts, so a quota alert
    // is not hidden before it is seen.
    private func startIdleAutoClose() {
        installPopoverEventMonitor()
        scheduleIdleClose()
    }

    private func scheduleIdleClose() {
        idleCloseWorkItem?.cancel()
        let work = DispatchWorkItem { [weak self] in
            guard let self, let pop = self.popover, pop.isShown else { return }
            // Keep an alerting popover open until the alert is acknowledged;
            // re-arm the timer so it closes once the alert clears.
            if !self.store.alerts.isEmpty {
                self.scheduleIdleClose()
                return
            }
            pop.performClose(nil)
        }
        idleCloseWorkItem = work
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.idleCloseInterval, execute: work)
    }

    private func installPopoverEventMonitor() {
        guard popoverEventMonitor == nil else { return }
        let mask: NSEvent.EventTypeMask = [
            .leftMouseDown, .rightMouseDown, .otherMouseDown,
            .leftMouseDragged, .scrollWheel, .keyDown, .mouseMoved,
        ]
        popoverEventMonitor = NSEvent.addLocalMonitorForEvents(matching: mask) { [weak self] event in
            if let self, self.isEventInPopover(event) {
                self.scheduleIdleClose()
            }
            return event
        }
    }

    private func isEventInPopover(_ event: NSEvent) -> Bool {
        guard let popoverWindow = popover?.contentViewController?.view.window else { return false }
        return event.window === popoverWindow
    }

    private func cancelIdleAutoClose() {
        idleCloseWorkItem?.cancel()
        idleCloseWorkItem = nil
        if let monitor = popoverEventMonitor {
            NSEvent.removeMonitor(monitor)
            popoverEventMonitor = nil
        }
    }

    func popoverDidClose(_ notification: Notification) {
        cancelIdleAutoClose()
    }

    private func presentAlertPopover() {
        guard popover == nil || popover?.isShown == false else { return }
        toggle(nil)
    }

    private func resizePopover(_ layout: PopoverLayout) {
        guard let popover else { return }
        let size = NSSize(width: layout.width, height: layout.height)
        if popover.contentSize != size { popover.contentSize = size }
    }

    static func configurePopoverBackground(_ content: NSView) {
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        configureVisualEffects(in: content)
    }

    private static func configureVisualEffects(in view: NSView) {
        for subview in view.subviews {
            if let effect = subview as? NSVisualEffectView {
                effect.material = .windowBackground
                effect.blendingMode = .withinWindow
                effect.state = .inactive
            }
            configureVisualEffects(in: subview)
        }
    }

    private func render(rings: [Ring], alerts: [QuotaAlert]) {
        // The menu-bar icon shows one horizontal progress bar per quota. The
        // popover keeps its full Activity-style ring visualization.
        let visibleRings = RingPresentation.quotaRings(rings)
        let pcts = visibleRings.map { pct($0) }
        let alertLevels = visibleRings.map { ring in
            alerts.first(where: { $0.ringID == ring.id })?.level
        }
        item.button?.image = Self.progressBarImage(pcts: pcts, alertLevels: alertLevels)
        item.button?.toolTip = rings.map { "\($0.label): \($0.usageText)" }.joined(separator: "\n")
    }

    private func pct(_ r: Ring) -> Int {
        r.fillPercent
    }

    static func progressBarImage(
        pcts: [Int],
        alertLevels: [QuotaAlertLevel?] = []
    ) -> NSImage {
        let imageSize = NSSize(width: 24, height: 18)
        let image = NSImage(size: imageSize)
        image.lockFocus()
        let palette: [NSColor] = [
            NSColor(calibratedRed: 0.00, green: 0.52, blue: 1.00, alpha: 1),
            NSColor(calibratedRed: 0.53, green: 0.37, blue: 1.00, alpha: 1),
            NSColor(calibratedRed: 0.08, green: 0.82, blue: 0.40, alpha: 1),
            NSColor(calibratedRed: 1.00, green: 0.58, blue: 0.04, alpha: 1),
            NSColor(calibratedRed: 0.00, green: 0.76, blue: 0.82, alpha: 1),
            NSColor(calibratedRed: 1.00, green: 0.26, blue: 0.22, alpha: 1),
            NSColor(calibratedRed: 1.00, green: 0.22, blue: 0.50, alpha: 1),
            NSColor(calibratedRed: 1.00, green: 0.82, blue: 0.04, alpha: 1),
        ]
        let visiblePcts = pcts.isEmpty ? [0] : pcts
        let layout = MenuBarLayout.make(
            ringCount: visiblePcts.count,
            imageWidth: imageSize.width,
            imageHeight: imageSize.height
        )
        for (i, pct) in visiblePcts.enumerated() {
            let color: NSColor
            if alertLevels.indices.contains(i), let level = alertLevels[i] {
                color = level == .critical ? .systemRed : .systemOrange
            } else {
                color = palette[i % palette.count]
            }
            let y = imageSize.height - layout.top - layout.barHeight
                - CGFloat(i) * (layout.barHeight + layout.gap)
            let trackRect = NSRect(
                x: 1,
                y: y,
                width: layout.barWidth,
                height: layout.barHeight
            )
            color.withAlphaComponent(0.42).setFill()
            NSBezierPath(
                roundedRect: trackRect,
                xRadius: layout.barHeight / 2,
                yRadius: layout.barHeight / 2
            ).fill()

            let progress = CGFloat(max(0, min(100, pct))) / 100
            guard progress > 0 else { continue }
            let fillRect = NSRect(
                x: trackRect.minX,
                y: trackRect.minY,
                width: max(layout.barHeight, trackRect.width * progress),
                height: trackRect.height
            )
            color.withAlphaComponent(0.96).setFill()
            NSBezierPath(
                roundedRect: fillRect,
                xRadius: layout.barHeight / 2,
                yRadius: layout.barHeight / 2
            ).fill()
        }
        image.unlockFocus()
        // Preserve per-provider colors instead of letting macOS template the
        // stacked bars into a single monochrome symbol.
        image.isTemplate = false
        return image
    }
}

@main
struct RinqMenuMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = MainActor.assumeIsolated { AppDelegate() }
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
    }
}
