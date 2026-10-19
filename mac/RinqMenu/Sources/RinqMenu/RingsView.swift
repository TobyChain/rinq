import SwiftUI

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
                .opacity(isPulsing ? 0.55 : 1)
        }
        .contentShape(Circle())
        .help(ring.hoverText)
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

    private var isPulsing: Bool { alert != nil && pulse }

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

/// One provider per row: identity and quota text on the leading side, a
/// standalone progress ring with the percentage at the trailing edge.
struct ProviderQuotaRow: View {
    let ring: Ring
    var alerts: [QuotaAlert] = []
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(ring.label)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                Text(subtitle)
                    .font(.system(size: 10))
                    .foregroundStyle(alert == nil ? .secondary : alertColor)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            Spacer(minLength: 6)
            ZStack {
                RingArc(ring: ring, alert: alert, lineWidth: 4.5)
                Text(ring.ringCenterText)
                    .font(.system(size: 9, weight: .bold, design: .rounded))
                    .foregroundStyle(alert == nil ? .primary : alertColor)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            .frame(width: 36, height: 36)
        }
        .padding(.horizontal, 10)
        .frame(height: PopoverLayout.providerRowHeight - 2)
        .padding(.vertical, 1)
        .background(alertColor.opacity(isPulsing ? 0.14 : 0.05), in: RoundedRectangle(cornerRadius: 8))
        .help(ring.hoverText)
        .onAppear { updatePulse(active: alert != nil) }
        .onChange(of: alert != nil) { active in updatePulse(active: active) }
    }

    private var alert: QuotaAlert? { alerts.first { $0.ringID == ring.id } }
    private var isPulsing: Bool { alert != nil && pulse }

    private var alertColor: Color {
        if !ring.hasQuotaValue { return .secondary }
        switch alert?.level {
        case .critical: return .red
        case .warning: return .orange
        case nil: return Palette.color(ring.accent)
        }
    }

    private var subtitle: String {
        if let alert { return alert.message }
        let detail = ring.statusDetail ?? ring.resetText ?? ""
        return detail.isEmpty ? ring.valueText : "\(ring.valueText) · \(detail)"
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
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            Text("Click anywhere")
                .font(.system(size: 9, weight: .medium))
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
