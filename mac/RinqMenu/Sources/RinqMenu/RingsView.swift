import SwiftUI

struct RingsView: View {
    let rings: [Ring]
    var diameter: CGFloat = 180

    var body: some View {
        ZStack {
            ForEach(Array(Array(rings.prefix(3)).enumerated()), id: \.element.id) { idx, ring in
                RingArc(ring: ring, lineWidth: 13)
                    .frame(width: diameter - CGFloat(idx) * 46,
                           height: diameter - CGFloat(idx) * 46)
            }
        }
        .frame(width: diameter, height: diameter)
    }
}

struct RingArc: View {
    let ring: Ring
    let lineWidth: CGFloat

    private var pct: Int {
        if ring.kind == "balance" { return ring.remainingPercent ?? ring.usedPercent ?? 0 }
        return ring.usedPercent ?? 0
    }

    var body: some View {
        ZStack {
            Circle().stroke(Palette.color(ring.accent).opacity(0.18), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: CGFloat(pct) / 100)
                .stroke(Palette.color(ring.accent),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

struct BarRow: View {
    let ring: Ring

    private var isBalance: Bool { ring.kind == "balance" }
    private var pct: Int { isBalance ? (ring.remainingPercent ?? ring.usedPercent ?? 0) : (ring.usedPercent ?? 0) }
    private var symbol: String { ring.currency == "USD" ? "$" : "¥" }

    var body: some View {
        HStack(spacing: 12) {
            RingArc(ring: ring, lineWidth: 4)
                .frame(width: 26, height: 26)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(ring.label).font(.system(size: 13, weight: .semibold))
                    Spacer()
                    Text(headline).font(.system(size: 13, weight: .bold, design: .rounded))
                        .foregroundStyle(Palette.color(ring.accent))
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Palette.color(ring.accent).opacity(0.16))
                        Capsule().fill(Palette.color(ring.accent))
                            .frame(width: geo.size.width * CGFloat(pct) / 100)
                    }
                }
                .frame(height: 6)
                Text(detail).font(.system(size: 10)).foregroundStyle(.secondary)
            }
        }
    }

    private var headline: String {
        if isBalance, let rem = ring.remaining { return "\(symbol)\(String(format: "%.0f", rem))" }
        return "\(pct)%"
    }

    private var detail: String {
        if isBalance, let rem = ring.remaining { return "\(symbol)\(String(format: "%.2f", rem)) left" }
        if ring.kind == "budget", let spent = ring.spentUsd { return "$\(String(format: "%.2f", spent)) spent" }
        if let reset = ring.resetsAt {
            let s = Double(reset) - Date().timeIntervalSince1970
            if s <= 0 { return "\(ring.usedPercent ?? 0)% used" }
            let m = Int(s / 60)
            if m >= 1440 { return "resets in \(m / 1440)d" }
            if m >= 60 { return "resets in \(m / 60)h \(m % 60)m" }
            return "resets in \(m)m"
        }
        return "\(pct)%"
    }
}
