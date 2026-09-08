import AppKit
import SwiftUI

// RinqMenu: a menu-bar item showing the top three quota rings. Clicking opens
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
        item = NSStatusBar.system.statusItem(withLength: 28)
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

        let tab = NSTabViewController()
        tab.tabStyle = .segmentedControlOnTop

        let dash = NSHostingController(rootView: DashboardView(store: store).padding(12))
        dash.title = "Rings"
        let settings = NSHostingController(rootView: SettingsView(store: store))
        settings.title = "Providers"
        tab.addChild(dash)
        tab.addChild(settings)

        let pop = NSPopover()
        pop.behavior = .transient
        pop.contentSize = NSSize(width: 360, height: 470)
        pop.contentViewController = tab
        pop.show(relativeTo: item.button!.bounds, of: item.button!, preferredEdge: .minY)
        popover = pop

        Task { await store.refresh() }
    }

    private func render(rings: [Ring]) {
        let top = Array(rings.prefix(3))
        let pcts = top.map { pct($0) }
        item.button?.image = Self.ringImage(pcts: pcts)
        item.button?.image?.isTemplate = false
        item.button?.toolTip = top.map { "\($0.label): \(pct($0))%" }.joined(separator: "\n")
    }

    private func pct(_ r: Ring) -> Int {
        if r.kind == "balance" { return r.remainingPercent ?? r.usedPercent ?? 0 }
        return r.usedPercent ?? 0
    }

    static func ringImage(pcts: [Int]) -> NSImage {
        let size = 22.0
        let image = NSImage(size: NSSize(width: size, height: size))
        image.lockFocus()
        let center = NSPoint(x: size / 2, y: size / 2)
        let colors: [NSColor] = [.systemBlue, .systemPurple, .systemGreen, .systemOrange]
        for (i, pct) in pcts.enumerated() {
            let radius = (size / 2 - 2) - Double(i) * 3.2
            let track = NSBezierPath()
            colors[i].withAlphaComponent(0.18).setStroke()
            track.appendArc(withCenter: center, radius: radius, startAngle: 0, endAngle: 360)
            track.lineWidth = 2.4
            track.stroke()
            let ring = NSBezierPath()
            colors[i].setStroke()
            ring.lineWidth = 2.4
            ring.lineCapStyle = .round
            let p = CGFloat(pct) / 100.0
            ring.appendArc(withCenter: center, radius: radius, startAngle: -90, endAngle: -90 + 360 * p)
            ring.stroke()
        }
        image.unlockFocus()
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
