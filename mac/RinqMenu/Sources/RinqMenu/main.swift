import AppKit
import WebKit

// RinqMenu: a tiny menu-bar item. The icon is drawn as small concentric rings
// from the top three quota values; clicking opens the web dashboard in a
// popover (served by the rinq daemon at 127.0.0.1).
@MainActor
final class StatusFetcher {
    struct Ring: Decodable {
        let label: String
        let kind: String?
        let usedPercent: Int?
        let remainingPercent: Int?
        let status: String?
    }
    struct Status: Decodable { let rings: [Ring] }

    func pct(_ r: Ring) -> Int? {
        if r.kind == "balance" { return r.remainingPercent ?? r.usedPercent }
        return r.usedPercent
    }

    func fetch(port: Int, completion: @escaping ([Ring]) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:\(port)/status") else { return completion([]) }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data, let s = try? JSONDecoder().decode(Status.self, from: data) else {
                DispatchQueue.main.async { completion([]) }
                return
            }
            DispatchQueue.main.async { completion(s.rings) }
        }.resume()
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var item: NSStatusItem!
    private let fetcher = StatusFetcher()
    private var popover: NSPopover?
    private var webView: WKWebView?
    private var timer: Timer?
    private let port: Int = Int(ProcessInfo.processInfo.environment["RINQ_PORT"] ?? "7788") ?? 7788

    func applicationDidFinishLaunching(_ note: Notification) {
        item = NSStatusBar.system.statusItem(withLength: 26)
        item.button?.target = self
        item.button?.action = #selector(toggle(_:))
        render(rings: [])
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
        refresh()
    }

    @objc private func toggle(_ sender: Any?) {
        if let pop = popover, pop.isShown { pop.performClose(sender); return }
        let pop = NSPopover()
        pop.behavior = .transient
        pop.contentSize = NSSize(width: 340, height: 470)
        let controller = NSViewController()
        let wv = WKWebView(frame: CGRect(x: 0, y: 0, width: 340, height: 470))
        if let url = URL(string: "http://127.0.0.1:\(port)/") {
            wv.load(URLRequest(url: url))
        }
        controller.view = wv
        pop.contentViewController = controller
        pop.show(relativeTo: item.button!.bounds, of: item.button!, preferredEdge: .minY)
        popover = pop
        webView = wv
    }

    private func refresh() {
        fetcher.fetch(port: port) { [weak self] rings in self?.render(rings: rings) }
    }

    private func render(rings: [StatusFetcher.Ring]) {
        let top = Array(rings.prefix(3))
        let pcts: [Int?] = top.map { fetcher.pct($0) }
        item.button?.image = Self.ringImage(pcts: pcts)
        item.button?.image?.isTemplate = false
        item.button?.toolTip = top.enumerated().map { i, r in
            let p = pcts[i]
            return "\(r.label): \(p.map { "\($0)%" } ?? "--")"
        }.joined(separator: "\n")
    }

    static func ringImage(pcts: [Int?]) -> NSImage {
        let size = 22.0
        let image = NSImage(size: NSSize(width: size, height: size))
        image.lockFocus()
        let center = NSPoint(x: size / 2, y: size / 2)
        let colors: [NSColor] = [.systemBlue, .systemPurple, .systemGreen, .systemOrange]
        for (i, pct) in pcts.enumerated() {
            let radius = (size / 2 - 2) - Double(i) * 3.2
            let ring = NSBezierPath()
            ring.lineWidth = 2.4
            ring.lineCapStyle = .round
            let track = NSBezierPath()
            colors[i].withAlphaComponent(0.18).setStroke()
            track.appendArc(withCenter: center, radius: radius, startAngle: 0, endAngle: 360)
            track.lineWidth = 2.4
            track.stroke()
            let p = CGFloat(pct ?? 0) / 100.0
            colors[i].setStroke()
            ring.appendArc(withCenter: center, radius: radius, startAngle: -90, endAngle: -90 + 360 * p)
            ring.stroke()
        }
        image.unlockFocus()
        return image
    }
}

let app = NSApplication.shared
let delegate = MainActor.assumeIsolated { AppDelegate() }
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
