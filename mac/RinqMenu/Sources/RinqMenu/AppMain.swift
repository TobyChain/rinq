import AppKit
import SwiftUI

// RinqMenu: a menu-bar item showing the configured quota rings. Clicking opens
// a native SwiftUI popover with the dashboard and a Settings tab for adding
// provider keys, toggling vendors, and managing ring order. Data comes from
// the rinq daemon (http://127.0.0.1:<port>).
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var item: NSStatusItem!
    private var popover: NSPopover?
    private var store: Store!
    private var timer: Timer?

    func applicationDidFinishLaunching(_ note: Notification) {
        item = NSStatusBar.system.statusItem(withLength: 30)
        item.button?.target = self
        item.button?.action = #selector(toggle(_:))
        store = Store()
        render(rings: [])
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.store.refresh()
                self?.render(rings: self?.store.status?.rings ?? [])
            }
        }
        Task {
            await store.refresh()
            render(rings: store.status?.rings ?? [])
        }
    }

    @objc private func toggle(_ sender: Any?) {
        if let pop = popover, pop.isShown { pop.performClose(sender); return }

        let screenSize = item.button?.window?.screen?.visibleFrame.size
            ?? NSScreen.main?.visibleFrame.size
            ?? NSSize(width: 1440, height: 900)
        let initialLayout = PopoverLayout.make(
            ringCount: store.status?.rings.count ?? 0,
            visibleScreenSize: screenSize
        )
        let root = NSHostingController(rootView: RootView(
            store: store,
            visibleScreenSize: screenSize,
            onLayoutChange: { [weak self] layout in
                self?.resizePopover(layout)
            }
        ))
        let pop = NSPopover()
        pop.behavior = .transient
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
                self.makeOpaque(content)
            }
        }
        Task { await store.refresh() }
    }

    private func resizePopover(_ layout: PopoverLayout) {
        guard let popover else { return }
        let size = NSSize(width: layout.width, height: layout.height)
        if popover.contentSize != size { popover.contentSize = size }
    }

    private func makeOpaque(_ view: NSView) {
        for sub in view.subviews {
            if let vfx = sub as? NSVisualEffectView {
                vfx.material = .windowBackground
                vfx.blendingMode = .withinWindow
                vfx.state = .inactive
            }
            sub.wantsLayer = true
            if sub.layer?.backgroundColor == nil {
                sub.layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
            }
            makeOpaque(sub)
        }
        view.wantsLayer = true
    }

    private func render(rings: [Ring]) {
        // Menu-bar icon shows all configured rings as concentric arcs.
        let pcts = rings.map { pct($0) }
        item.button?.image = Self.ringImage(pcts: pcts)
        item.button?.toolTip = rings.map { "\($0.label): \($0.usageText)" }.joined(separator: "\n")
    }

    private func pct(_ r: Ring) -> Int {
        r.fillPercent
    }

    static func ringImage(pcts: [Int]) -> NSImage {
        let size: CGFloat = 24
        let image = NSImage(size: NSSize(width: size, height: size))
        image.lockFocus()
        let center = NSPoint(x: size / 2, y: size / 2)
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
        let layout = MenuRingLayout.make(ringCount: visiblePcts.count, imageSize: size)
        let step = layout.lineWidth + layout.gap
        for (i, pct) in visiblePcts.enumerated() {
            let radius = layout.outerRadius - CGFloat(i) * step
            guard radius > layout.lineWidth / 2 else { break }
            let color = palette[i % palette.count]
            let track = NSBezierPath()
            color.withAlphaComponent(0.48).setStroke()
            track.appendArc(withCenter: center, radius: radius, startAngle: 0, endAngle: 360)
            track.lineWidth = layout.lineWidth
            track.stroke()
            let ring = NSBezierPath()
            color.withAlphaComponent(0.96).setStroke()
            ring.lineWidth = layout.lineWidth
            ring.lineCapStyle = .round
            let p = CGFloat(pct) / 100.0
            ring.appendArc(withCenter: center, radius: radius, startAngle: -90, endAngle: -90 + 360 * p)
            ring.stroke()
        }
        image.unlockFocus()
        // Preserve per-ring colors. The translucent track remains visible
        // while the nearly opaque used arc carries the actual quota value.
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
