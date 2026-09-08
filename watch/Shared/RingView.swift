import SwiftUI

struct RingView: View {
    let ring: TRRing
    var lineWidth: CGFloat = 6
    var showCenter: Bool = true
    var diameter: CGFloat? = nil

    // Balance rings read like a battery (fill = remaining); window/budget
    // rings read like activity (fill = consumed).
    private var pct: Int? {
        if ring.kind == "balance" {
            return ring.remainingPercent ?? ring.usedPercent
        }
        return ring.usedPercent
    }

    private var fraction: Double {
        guard let p = pct else { return 0 }
        return Double(min(max(p, 0), 100)) / 100.0
    }

    private var unknown: Bool {
        pct == nil || ring.status == "unknown"
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(TRPalette.color(ring.accent).opacity(0.18), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: unknown ? 0 : fraction)
                .stroke(
                    unknown ? Color.gray : TRPalette.color(ring.accent),
                    style: StrokeStyle(lineWidth: lineWidth, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
            if showCenter {
                VStack(spacing: 1) {
                    if unknown {
                        Text("--").font(.system(size: 13, weight: .bold, design: .rounded))
                    } else {
                        Text("\(pct ?? 0)")
                            .font(.system(size: 14, weight: .bold, design: .rounded))
                        Text("%").font(.system(size: 8, weight: .semibold))
                    }
                }
            }
        }
        .frame(width: diameter, height: diameter)
        .accessibilityLabel("\(ring.label) \(unknown ? "unknown" : "\(pct ?? 0) percent")")
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
                RingView(
                    ring: ring,
                    lineWidth: lineWidth,
                    showCenter: false,
                    diameter: outerDiameter - CGFloat(idx) * 2 * (lineWidth + gap)
                )
            }
        }
        .frame(width: outerDiameter, height: outerDiameter)
    }
}
