import SwiftUI

struct RingView: View {
    let ring: TRRing
    var lineWidth: CGFloat = 6
    var showCenter: Bool = true
    var diameter: CGFloat? = nil

    private var pct: Int? {
        if ring.kind == "balance" { return ring.remainingPercent ?? ring.usedPercent }
        return ring.usedPercent
    }

    private var fraction: Double {
        guard let p = pct else { return 0 }
        return Double(min(max(p, 0), 100)) / 100.0
    }

    private var unknown: Bool { pct == nil || ring.status == "unknown" }

    var body: some View {
        ZStack {
            Circle().stroke(TRPalette.color(ring.accent).opacity(0.18), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: unknown ? 0 : fraction)
                .stroke(unknown ? Color.gray : TRPalette.color(ring.accent),
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
            if showCenter {
                VStack(spacing: 1) {
                    if unknown {
                        Text("--").font(.system(size: 13, weight: .bold, design: .rounded))
                    } else {
                        Text("\(pct ?? 0)").font(.system(size: 14, weight: .bold, design: .rounded))
                        Text("%").font(.system(size: 8, weight: .semibold))
                    }
                }
            }
        }
        .frame(width: diameter, height: diameter)
    }
}

struct RingStackView: View {
    let rings: [TRRing]
    var outerDiameter: CGFloat = 96

    var body: some View {
        let shown = Array(rings.prefix(3))
        let gap: CGFloat = 9
        let lineWidth: CGFloat = 6
        return ZStack {
            ForEach(Array(shown.enumerated()), id: \.element.id) { idx, ring in
                RingView(ring: ring, lineWidth: lineWidth, showCenter: false,
                         diameter: outerDiameter - CGFloat(idx) * 2 * (lineWidth + gap))
            }
        }
        .frame(width: outerDiameter, height: outerDiameter)
    }
}

struct BarRow: View {
    let ring: TRRing

    private var isBalance: Bool { ring.kind == "balance" }
    private var pct: Int? { isBalance ? (ring.remainingPercent ?? ring.usedPercent) : ring.usedPercent }
    private var unknown: Bool { pct == nil || ring.status == "unknown" }
    private var fraction: CGFloat {
        guard let p = pct else { return 0 }
        return CGFloat(min(max(p, 0), 100)) / 100.0
    }
    private var symbol: String { (ring.currency == "USD") ? "$" : "¥" }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(ring.label).font(.system(size: 13, weight: .semibold))
                Spacer()
                Text(pct == nil ? "--" : "\(pct ?? 0)%")
                    .font(.system(size: 13, weight: .bold, design: .rounded))
                    .foregroundStyle(unknown ? .secondary : TRPalette.color(ring.accent))
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(TRPalette.color(ring.accent).opacity(0.18))
                    Capsule().fill(unknown ? Color.gray : TRPalette.color(ring.accent))
                        .frame(width: geo.size.width * (unknown ? 0 : fraction))
                }
            }
            .frame(height: 8)
            Text(detail).font(.system(size: 10)).foregroundStyle(.secondary)
        }
    }

    private var detail: String {
        if unknown {
            if isBalance { return "paste key to show" }
            return "no data"
        }
        if isBalance, let rem = ring.remaining {
            return "\(symbol)\(String(format: "%.2f", rem)) left"
        }
        if ring.kind == "budget", let spent = ring.spentUsd {
            return "$\(String(format: "%.2f", spent)) spent this month"
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
