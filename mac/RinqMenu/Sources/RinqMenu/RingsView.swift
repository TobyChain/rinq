import SwiftUI

struct RingsView: View {
    let rings: [Ring]
    var alerts: [QuotaAlert] = []
    var diameter: CGFloat = 190

    var body: some View {
        let visibleRings = rings.filter(\.hasQuotaValue)
        // Adapt the ring thickness/gap to how many there are so any number
        // fits inside the outer diameter.
        let n = max(visibleRings.count, 1)
        let lineWidth = min(13, (diameter - 30) / (CGFloat(n) * 2.3))
        let step = lineWidth + 6
        ZStack {
            ForEach(Array(visibleRings.enumerated()), id: \.element.id) { idx, ring in
                let d = diameter - CGFloat(idx) * 2 * step
                RingArc(ring: ring, alert: alert(for: ring), lineWidth: lineWidth)
                    .frame(width: max(d, lineWidth * 2), height: max(d, lineWidth * 2))
            }
        }
        .frame(width: diameter, height: diameter)
    }

    private func alert(for ring: Ring) -> QuotaAlert? {
        alerts.first { $0.ringID == ring.id }
    }
}

struct RingArc: View {
    let ring: Ring
    var alert: QuotaAlert?
    let lineWidth: CGFloat
    @State private var pulse = false

    private var pct: Int {
        ring.fillPercent
    }

    var body: some View {
        ZStack {
            Circle().stroke(alertTrackColor.opacity(0.22), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: CGFloat(pct) / 100)
                .stroke(alertColor,
                        style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .opacity(pulse ? 0.55 : 1)
        }
        .onAppear { updatePulse(active: alert != nil) }
        .onChange(of: alert != nil) { active in updatePulse(active: active) }
    }

    private var alertColor: Color {
        if !ring.hasQuotaValue { return .secondary }
        switch alert?.level {
        case .critical: return .red
        case .warning: return .orange
        case nil: return Palette.color(ring.accent)
        }
    }

    private var alertTrackColor: Color {
        alert == nil ? Palette.color(ring.accent) : alertColor
    }

    private func updatePulse(active: Bool) {
        if active {
            pulse = false
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                pulse = true
            }
        } else {
            withAnimation(nil) { pulse = false }
        }
    }
}

struct BarRow: View {
    let ring: Ring
    var alerts: [QuotaAlert] = []
    var compact = false
    @State private var pulse = false

    private var pct: Int { ring.usedPercent ?? 0 }

    var body: some View {
        HStack(spacing: compact ? 8 : 12) {
            RingArc(ring: ring, alert: alert, lineWidth: 4)
                .frame(width: compact ? 22 : 26, height: compact ? 22 : 26)
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(ring.label)
                        .font(.system(size: compact ? 11 : 13, weight: .semibold))
                        .lineLimit(1)
                    Spacer()
                    Text(alert?.message ?? ring.usageText)
                        .font(.system(size: compact ? 10 : 13, weight: .bold, design: .rounded))
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                        .foregroundStyle(alertColor)
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(alertColor.opacity(0.16))
                        Capsule().fill(alertColor)
                            .frame(width: geo.size.width * CGFloat(pct) / 100)
                    }
                }
                .frame(height: 6)
                Text(detail)
                    .font(.system(size: compact ? 9 : 10))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(minHeight: 38)
        .padding(.vertical, alert == nil ? 0 : 4)
        .background(alertColor.opacity(pulse ? 0.14 : 0.05), in: RoundedRectangle(cornerRadius: 8))
        .onAppear { updatePulse(active: alert != nil) }
        .onChange(of: alert != nil) { active in updatePulse(active: active) }
    }

    private var alert: QuotaAlert? { alerts.first { $0.ringID == ring.id } }

    private var alertColor: Color {
        if !ring.hasQuotaValue { return .secondary }
        switch alert?.level {
        case .critical: return .red
        case .warning: return .orange
        case nil: return Palette.color(ring.accent)
        }
    }

    private var detail: String {
        if let statusDetail = ring.statusDetail { return statusDetail }
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

    private func updatePulse(active: Bool) {
        if active {
            pulse = false
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                pulse = true
            }
        } else {
            withAnimation(nil) { pulse = false }
        }
    }
}

struct AlertBanner: View {
    let alerts: [QuotaAlert]
    @State private var pulse = false

    private var highestLevel: QuotaAlertLevel {
        alerts.contains { $0.level == .critical } ? .critical : .warning
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: highestLevel == .critical ? "exclamationmark.octagon.fill" : "flame.fill")
            VStack(alignment: .leading, spacing: 2) {
                Text(highestLevel == .critical ? "Quota exhausted" : "Quota alert")
                    .font(.system(size: 11, weight: .bold))
                Text(alerts.prefix(2).map(\.message).joined(separator: " · "))
                    .font(.system(size: 10))
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
            Image(systemName: "xmark")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(.secondary)
        }
        .foregroundStyle(highestLevel == .critical ? .red : .orange)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background((highestLevel == .critical ? Color.red : Color.orange).opacity(pulse ? 0.18 : 0.08), in: RoundedRectangle(cornerRadius: 9))
        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulse)
        .onAppear { pulse = true }
    }
}
