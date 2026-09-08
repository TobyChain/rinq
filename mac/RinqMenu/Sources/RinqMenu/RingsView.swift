import SwiftUI

struct RingsView: View {
    let rings: [Ring]
    var diameter: CGFloat = 190

    var body: some View {
        // Adapt the ring thickness/gap to how many there are so any number
        // fits inside the outer diameter.
        let n = max(rings.count, 1)
        let lineWidth = min(13, (diameter - 30) / (CGFloat(n) * 2.3))
        let step = lineWidth + 6
        ZStack {
            ForEach(Array(rings.enumerated()), id: \.element.id) { idx, ring in
                let d = diameter - CGFloat(idx) * 2 * step
                RingArc(ring: ring, lineWidth: lineWidth)
                    .frame(width: max(d, lineWidth * 2), height: max(d, lineWidth * 2))
            }
        }
        .frame(width: diameter, height: diameter)
    }
}

struct RingArc: View {
    let ring: Ring
    let lineWidth: CGFloat

    private var pct: Int {
        ring.fillPercent
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

    private var pct: Int { ring.usedPercent ?? 0 }

    var body: some View {
        HStack(spacing: 12) {
            RingArc(ring: ring, lineWidth: 4)
                .frame(width: 26, height: 26)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(ring.label).font(.system(size: 13, weight: .semibold))
                    Spacer()
                    Text(ring.usageText).font(.system(size: 13, weight: .bold, design: .rounded))
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

    private var detail: String {
        if let reset = ring.resetsAt {
            let s = Double(reset) - Date().timeIntervalSince1970
            if s <= 0 { return "quota window ended" }
            let m = Int(s / 60)
            if m >= 1440 { return "resets in \(m / 1440)d" }
            if m >= 60 { return "resets in \(m / 60)h \(m % 60)m" }
            return "resets in \(m)m"
        }
        return "\(pct)%"
    }
}
