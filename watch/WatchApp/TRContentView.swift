import SwiftUI

struct TRContentView: View {
    @State private var status: TRStatus = .sample
    @State private var statusURL: String = UserDefaults.standard.string(forKey: "statusURL") ?? ""

    var body: some View {
        TabView {
            OverviewPage(status: status)
            ForEach(vendors, id: \.self) { vendor in
                VendorPage(rings: rings(for: vendor), vendor: vendor)
            }
            SettingsPage(statusURL: $statusURL, onSave: {
                saveURL()
                Task { await refresh() }
            })
        }
        .tabViewStyle(.page)
        .task { await refresh() }
    }

    private var vendors: [String] {
        var seen: [String] = []
        for r in status.rings where !seen.contains(r.vendor ?? r.id) {
            seen.append(r.vendor ?? r.id)
        }
        return seen
    }

    private func rings(for vendor: String) -> [TRRing] {
        status.rings.filter { ($0.vendor ?? $0.id) == vendor }
    }

    private func saveURL() {
        UserDefaults.standard.set(statusURL, forKey: "statusURL")
    }

    private func refresh() async {
        if let remote = await TRStatusLoader.remote() {
            status = remote
        }
    }
}

struct OverviewPage: View {
    let status: TRStatus

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                RingStackView(rings: status.rings, outerDiameter: 96)
                VStack(spacing: 1) {
                    Text(headline)
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                    Text(waiting > 0 ? "waiting" : "running")
                        .font(.system(size: 8, weight: .semibold))
                        .foregroundStyle(waiting > 0 ? .orange : .secondary)
                }
            }
            HStack(spacing: 14) {
                stat("\(done)", "done", .green)
                stat("\(failed)", "failed", failed > 0 ? .red : .secondary)
                if let focus = status.focus, focus.mode == "focus" {
                    stat("\(focus.remainingMins ?? 0)m", "break", .orange)
                }
            }
            Text("updated \(updatedText)")
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
        }
    }

    private var waiting: Int { status.agents?.waiting ?? 0 }
    private var done: Int { status.agents?.doneToday ?? 0 }
    private var failed: Int { status.agents?.failedToday ?? 0 }
    private var headline: String { waiting > 0 ? "\(waiting)" : "\(status.agents?.running ?? 0)" }

    private var updatedText: String {
        guard let t = status.updatedAt else { return "—" }
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.string(from: Date(timeIntervalSince1970: TimeInterval(t)))
    }

    private func stat(_ value: String, _ label: String, _ color: Color) -> some View {
        VStack(spacing: 1) {
            Text(value).font(.system(size: 15, weight: .bold, design: .rounded)).foregroundStyle(color)
            Text(label).font(.system(size: 8)).foregroundStyle(.secondary)
        }
    }
}

struct VendorPage: View {
    let rings: [TRRing]
    let vendor: String

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Text(displayName)
                    .font(.system(size: 15, weight: .bold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                ForEach(rings) { ring in
                    BarRow(ring: ring)
                }
            }
            .padding(.horizontal, 4)
        }
    }

    private var displayName: String {
        (rings.first?.label ?? vendor).components(separatedBy: " ").first ?? vendor
    }
}

struct BarRow: View {
    let ring: TRRing

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(shortLabel).font(.system(size: 11, weight: .semibold))
                Spacer()
                Text(percentText)
                    .font(.system(size: 11, weight: .bold, design: .rounded))
                    .foregroundStyle(unknown ? .secondary : TRPalette.color(ring.accent))
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(TRPalette.color(ring.accent).opacity(0.18))
                    Capsule()
                        .fill(unknown ? Color.gray : TRPalette.color(ring.accent))
                        .frame(width: geo.size.width * (unknown ? 0 : fraction))
                }
            }
            .frame(height: 8)
            Text(detail)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
        }
    }

    private var shortLabel: String {
        if ring.kind == "balance" { return "balance" }
        var parts = ring.label.components(separatedBy: " ")
        guard parts.count > 1 else { return ring.label }
        parts.removeFirst()
        return parts.joined(separator: " ")
    }

    private var isBalance: Bool { ring.kind == "balance" }
    private var unknown: Bool { pct == nil || ring.status == "unknown" }
    private var pct: Int? { isBalance ? (ring.remainingPercent ?? ring.usedPercent) : ring.usedPercent }
    private var fraction: CGFloat {
        guard let p = pct else { return 0 }
        return CGFloat(min(max(p, 0), 100)) / 100.0
    }
    private var percentText: String {
        if isBalance, let rem = ring.remaining, ring.remainingPercent == nil {
            return "\(symbol)\(String(format: "%.1f", rem))"
        }
        return unknown ? "--" : "\(pct ?? 0)%"
    }

    private var symbol: String { (ring.currency == "USD") ? "$" : "¥" }

    private var detail: String {
        if unknown { return "no data — set API key" }
        if isBalance {
            if let rem = ring.remaining {
                return "\(symbol)\(String(format: "%.2f", rem)) left"
            }
            return "balance"
        }
        if ring.kind == "budget", let spent = ring.spentUsd, let budget = ring.budgetUsd {
            return String(format: "$%.2f / $%.0f", spent, budget)
        }
        if let reset = ring.resetsAt {
            let secs = Date(timeIntervalSince1970: TimeInterval(reset)).timeIntervalSinceNow
            if secs <= 0 { return "\(ring.usedPercent ?? 0)% used" }
            let mins = Int(secs / 60)
            if mins >= 1440 { return "resets in \(mins / 1440)d" }
            if mins >= 60 { return "resets in \(mins / 60)h \(mins % 60)m" }
            return "resets in \(mins)m"
        }
        return "\(ring.usedPercent ?? 0)%"
    }
}

struct SettingsPage: View {
    @Binding var statusURL: String
    let onSave: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                Text("Rinq").font(.system(size: 15, weight: .bold))
                Text("Status endpoint").font(.system(size: 10, weight: .semibold)).foregroundStyle(.secondary)
                TextField("https://…/status", text: $statusURL)
                    .font(.system(size: 10))
                    .multilineTextAlignment(.center)
                    .padding(.vertical, 6)
                    .padding(.horizontal, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color.gray.opacity(0.15))
                    )
                Button("Save & refresh") { onSave() }
                    .font(.system(size: 11, weight: .semibold))
            }
            .padding(.horizontal, 8)
        }
    }
}

@main
struct RinqWatchApp: App {
    var body: some Scene {
        WindowGroup {
            TRContentView()
        }
    }
}
